"""Claude Code PreToolUse hook.

Reads the hook JSON on stdin. For Bash calls it gates installs and MCP launches; for Write calls
to an MCP config file (.mcp.json, claude_desktop_config.json, .vscode/mcp.json, .cursor/mcp.json)
it gates every npm/PyPI server the new config would launch.

  block -> permissionDecision "deny"   (the command does not run)
  warn  -> permissionDecision "ask"    (the user sees the reason and decides)
  allow -> no output, exit 0           (normal permission flow continues)
Internal errors fail closed to "ask". Configure with a generous timeout, because a timed-out
PreToolUse hook does not block (see docs/GATE.md).
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

MCP_CONFIG_NAMES = ("mcp.json", ".mcp.json", "claude_desktop_config.json")


def _emit(decision: str, reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": decision,
                                             "permissionDecisionReason": "mcp-lock: " + reason}}))


def _commands_for(event: dict) -> list[str]:
    tool = event.get("tool_name")
    ti = event.get("tool_input") or {}
    if tool == "Bash":
        return [ti.get("command") or ""]
    if tool == "Write" and Path(ti.get("file_path") or "").name in MCP_CONFIG_NAMES:
        from census import launch
        try:
            servers = launch._servers(json.loads(launch.strip_jsonc_comments(ti.get("content") or "")))
        except json.JSONDecodeError:
            return []
        out = []
        for cfg in servers.values():
            if isinstance(cfg, dict) and isinstance(cfg.get("command"), str):
                out.append(" ".join([cfg["command"], *[json.dumps(str(a)) if " " in str(a) else str(a)
                                                       for a in cfg.get("args") or []]]))
        return out
    return []


def main() -> int:
    try:
        event = json.loads(sys.stdin.read() or "{}")
        cmds = [c for c in _commands_for(event) if c.strip()]
        if not cmds:
            return 0
        from gate import core, s1
        core.use_user_cache()
        cwd = Path(event.get("cwd") or os.getcwd())
        lock = Path(os.environ.get("MCPLOCK_LOCKFILE", cwd / "mcp-lock.json"))
        variant = os.environ.get("MCPLOCK_S1", "charitable")
        cfg = s1.S1Config.literal() if variant == "literal" else s1.S1Config.charitable()
        worst = None
        for c in cmds:
            d = core.evaluate(c, cwd, lock, cfg)
            if d.decision == "block" or (d.decision == "warn" and worst is None):
                worst = d
            if d.decision == "block":
                break
        if worst is None:
            return 0
        _emit("deny" if worst.decision == "block" else "ask", worst.reason)
        return 0
    except Exception:  # noqa: BLE001 - a security gate fails closed
        _emit("ask", "internal error, please review manually: "
                     + traceback.format_exc(limit=1).strip().splitlines()[-1])
        return 0


if __name__ == "__main__":
    sys.exit(main())
