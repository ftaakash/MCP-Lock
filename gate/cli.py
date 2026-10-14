"""mcplock command line.

    mcplock check [--lock mcp-lock.json] [--s1 charitable|literal] [--signals S1,S2,...] -- <command>
    mcplock lock <config.json> [-o mcp-lock.json]
    mcplock hook                       (Claude Code PreToolUse hook; reads JSON on stdin)
    mcplock proxy --server ID [--lock mcp-lock.json] [--record] -- <server command>
                                       (exploratory H2: pin the live tools/list; gate/proxy.py)

`check` prints one line: ALLOW / WARN / BLOCK and the reason, then any verified safer alternative as a
`TRY:` line (or `NOTE:` for advice). Exit code 0 allow, 1 warn, 2 block; `--no-suggest` turns suggestions off.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["proxy"]:  # own parser: everything after `--` belongs to the server
        from gate import proxy
        return proxy.main(argv[1:])
    ap = argparse.ArgumentParser(prog="mcplock")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--lock", type=Path, default=Path("mcp-lock.json"))
    c.add_argument("--cwd", type=Path, default=Path("."))
    c.add_argument("--s1", choices=["charitable", "literal"], default="charitable")
    c.add_argument("--signals", default="S1,S2,S3,S4,S5")
    c.add_argument("--json", action="store_true")
    c.add_argument("--no-suggest", action="store_true", help="do not propose safer alternatives")
    c.add_argument("command", nargs=argparse.REMAINDER)
    lk = sub.add_parser("lock")
    lk.add_argument("config", type=Path)
    lk.add_argument("-o", "--output", type=Path, default=Path("mcp-lock.json"))
    sub.add_parser("hook")
    a = ap.parse_args(argv)

    if a.cmd == "hook":
        from gate import hook
        return hook.main()
    from gate import core
    core.use_user_cache()
    if a.cmd == "lock":
        from lockfile.generate import generate
        lock = generate(a.config)
        a.output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
        print(f"locked {len(lock['servers'])} server(s) -> {a.output}")
        return 0
    from gate import s1
    cmd = " ".join(x for x in a.command if x != "--")
    cfg = s1.S1Config.literal() if a.s1 == "literal" else s1.S1Config.charitable()
    enabled = frozenset(s.strip().upper() for s in a.signals.split(",") if s.strip())
    d = core.evaluate(cmd, a.cwd, a.lock, cfg, enabled, suggest=not a.no_suggest)
    if a.json:
        print(json.dumps(d.to_dict(), indent=2))
    else:
        print(f"{d.decision.upper()}: {d.reason}")
        for s in d.suggestions:
            print(f"TRY: {s.command}  ({s.because})" if s.command else f"NOTE: {s.because}")
    return {"allow": 0, "warn": 1, "block": 2}[d.decision]


if __name__ == "__main__":
    sys.exit(main())
