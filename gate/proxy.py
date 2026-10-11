"""H2 (exploratory, docs/PHASE5_PLAN.md §4): pin the live tools/list of a stdio MCP server.

Static extraction cannot see tools that are built at runtime, fetched from a URL, or registered after a
date (E5, E6, E8). The proxy sits between the client and the server, forwards every JSON-RPC line, and
checks each tools/list response against the pin in the lock:

  a tool that is not pinned, or whose canonical (name, description, inputSchema) differs  -> block
  a pinned tool that is missing                                                           -> info only

A blocked tools/list is answered with a JSON-RPC error, so the client never sees the tools; tools/call for
a name that is not pinned is refused without reaching the server. The pin is per tool, so paginated
listings are checked page by page. The first run with --record writes the pin (trust on first use).

    mcplock proxy --server notes [--lock mcp-lock.json] [--record] -- npx -y pkg@1.0.0
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from census.tooldefs import canon_json, norm_ws
from gate.findings import Finding

BLOCK_CODE = -32001


def canonical(tool: dict) -> dict:
    """Same canonical form as the static tool hash (lockfile/SPEC.md §3), from a live tools/list item."""
    return {"name": tool.get("name"), "description": norm_ws(tool.get("description")),
            "schema": tool.get("inputSchema")}


def _h(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()


def pin(tools: list[dict]) -> dict:
    """Runtime pin: one digest per tool plus the hash of the whole sorted list."""
    items = {t["name"]: canon_json(canonical(t)) for t in tools}
    return {"hash": _h("\n".join(sorted(items.values()))),
            "tools": {n: _h(c) for n, c in sorted(items.items())}}


def check(pinned: dict | None, tools: list[dict], server: str, complete: bool = True) -> list[Finding]:
    """Findings for one tools/list page against the pin. `complete`: this page ends the listing."""
    if pinned is None:
        return [Finding("H2", "runtime_not_pinned", "info", server,
                        f"{server}: no runtime tool pin (run the proxy once with --record)")]
    want = pinned.get("tools") or {}
    got = pin(tools)["tools"]
    added = sorted(set(got) - set(want))
    changed = sorted(n for n in set(got) & set(want) if got[n] != want[n])
    f = []
    if added or changed:
        what = []
        if added:
            what.append("adds " + ", ".join(added[:5]) + ("…" if len(added) > 5 else ""))
        if changed:
            what.append("changes " + ", ".join(changed[:5]) + ("…" if len(changed) > 5 else ""))
        f.append(Finding("H2", "runtime_tool_drift", "block", server,
                         f"{server} live tools/list {'; '.join(what)} (differs from the runtime pin)"))
    if complete and (missing := sorted(set(want) - set(got))):
        f.append(Finding("H2", "runtime_tool_removed", "info", server,
                         f"{server} no longer lists {', '.join(missing[:5])}"))
    return f


class Proxy:
    def __init__(self, cmd: list[str], server: str, lock_path: Path, record: bool,
                 out=None, err=None):
        self.cmd, self.server, self.lock_path, self.record = cmd, server, lock_path, record
        self.out = out or sys.stdout
        self.err = err or sys.stderr
        self.pending: dict = {}  # request id -> method, for tools/list and refused tools/call
        self.seen: dict[str, dict] = {}  # tools of the listing in progress (for --record)
        self.wlock = threading.Lock()

    # lock file access -------------------------------------------------------------------------------
    def _lock(self) -> dict:
        return json.loads(self.lock_path.read_text(encoding="utf-8")) if self.lock_path.is_file() else {}

    def _entry(self, lock: dict) -> dict | None:
        return (lock.get("servers") or {}).get(self.server)

    def pinned(self) -> dict | None:
        e = self._entry(self._lock())
        return ((e or {}).get("tools") or {}).get("runtime")

    def _write_pin(self, tools: list[dict]) -> None:
        lock = self._lock()
        e = self._entry(lock)
        if e is None:
            self._log(f"cannot record: server '{self.server}' is not in {self.lock_path}")
            return
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        e.setdefault("tools", {})["runtime"] = {**pin(tools), "recorded": now}
        self.lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self._log(f"recorded runtime pin for {len(tools)} tool(s) in {self.lock_path}")

    # io ---------------------------------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        print(f"mcp-lock proxy: {msg}", file=self.err, flush=True)

    def _send(self, obj: dict) -> None:
        with self.wlock:
            self.out.write(json.dumps(obj, separators=(",", ":")) + "\n")
            self.out.flush()

    def _error(self, rid, message: str) -> None:
        self._send({"jsonrpc": "2.0", "id": rid,
                    "error": {"code": BLOCK_CODE, "message": "mcp-lock: " + message}})

    # client -> server -------------------------------------------------------------------------------
    def from_client(self, line: str) -> str | None:
        """Returns the line to forward to the server, or None if the proxy answered it itself."""
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return line
        if not isinstance(msg, dict) or "id" not in msg:
            return line
        if msg.get("method") == "tools/list":
            self.pending[msg["id"]] = "tools/list"
            if not (msg.get("params") or {}).get("cursor"):
                self.seen = {}
        elif msg.get("method") == "tools/call":
            p = self.pinned()
            name = (msg.get("params") or {}).get("name")
            if p is not None and name not in (p.get("tools") or {}):
                self._error(msg["id"], f"tool '{name}' is not in the runtime pin")
                return None
        return line

    # server -> client -------------------------------------------------------------------------------
    def from_server(self, line: str) -> str | None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return line
        if not isinstance(msg, dict) or "method" in msg or "id" not in msg:
            return line  # notifications and server-initiated requests pass through
        if self.pending.pop(msg["id"], None) != "tools/list" or "result" not in msg:
            return line
        res = msg["result"] or {}
        tools = [t for t in res.get("tools") or [] if isinstance(t, dict)]
        complete = not res.get("nextCursor")
        pinned = self.pinned()
        if pinned is None and self.record:
            self.seen.update({t.get("name"): t for t in tools})
            if complete:
                self._write_pin(list(self.seen.values()))
            return line
        findings = check(pinned, tools, self.server, complete)
        for f in findings:
            if f.severity == "info":
                self._log(f.reason)
        blocking = [f for f in findings if f.severity == "block"]
        if blocking:
            self._log("BLOCK " + blocking[0].reason)
            self._error(msg["id"], blocking[0].reason)
            return None
        return line

    def run(self, stdin=None) -> int:
        stdin = stdin or sys.stdin
        exe = shutil.which(self.cmd[0]) or self.cmd[0]
        child = subprocess.Popen([exe, *self.cmd[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 text=True, encoding="utf-8", bufsize=1)

        def pump_in():
            for line in stdin:
                fwd = self.from_client(line.rstrip("\n"))
                if fwd is not None:
                    child.stdin.write(fwd + "\n")
                    child.stdin.flush()
            child.stdin.close()

        threading.Thread(target=pump_in, daemon=True).start()
        for line in child.stdout:
            fwd = self.from_server(line.rstrip("\n"))
            if fwd is not None:
                with self.wlock:
                    self.out.write(fwd + "\n")
                    self.out.flush()
        return child.wait()


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="mcplock proxy")
    ap.add_argument("--server", required=True, help="server id in the lock (the mcpServers key)")
    ap.add_argument("--lock", type=Path, default=Path("mcp-lock.json"))
    ap.add_argument("--record", action="store_true", help="write the pin if the lock has none")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    a = ap.parse_args(argv)
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        ap.error("missing server command after --")
    return Proxy(cmd, a.server, a.lock, a.record).run()
