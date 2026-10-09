"""Gate entry point: command -> findings -> allow / warn / block with a one-line reason."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from census import http, launch, tarballs
from gate import command, s1, signals
from gate.findings import SEVERITY_ORDER, Finding

ALL_SIGNALS = frozenset({"S1", "S2", "S3", "S4", "S5"})


def use_user_cache() -> None:
    """When running inside someone else's project, keep caches out of their working tree."""
    base = Path(os.environ.get("MCPLOCK_CACHE", Path.home() / ".cache" / "mcplock"))
    http.CACHE_DIR = base / "http"
    tarballs.TARBALLS = base / "tarballs"
    tarballs.SRC = base / "src"


@dataclass
class Decision:
    decision: str  # "allow" | "warn" | "block"
    reason: str
    findings: list[Finding]

    def to_dict(self) -> dict:
        return {"decision": self.decision, "reason": self.reason,
                "findings": [f.to_dict() for f in self.findings]}


def load_lock(path: Path | None) -> dict:
    if path is None or not Path(path).is_file():
        return {}
    lock = json.loads(Path(path).read_text(encoding="utf-8"))
    return {(e["ecosystem"], e["name"]): e for e in (lock.get("servers") or {}).values()}


def decide(findings: list[Finding]) -> Decision:
    actionable = [f for f in findings if f.severity != "info"]
    if not actionable:
        return Decision("allow", "no issues", findings)
    worst = max(actionable, key=lambda f: SEVERITY_ORDER[f.severity])
    level = worst.severity
    n = sum(1 for f in actionable if f.severity == level)
    more = f" (+{n - 1} more)" if n > 1 else ""
    return Decision(level, f"{worst.signal} {worst.check}: {worst.reason}{more}", findings)


def evaluate(cmd: str, cwd: Path, lock_path: Path | None = None,
             s1cfg: s1.S1Config | None = None, enabled: frozenset = ALL_SIGNALS) -> Decision:
    s1cfg = s1cfg or s1.S1Config.charitable()
    lock = load_lock(lock_path)
    findings: list[Finding] = []
    for inv in command.parse(cmd):
        if "S1" in enabled:
            findings += s1.check_invocation(inv, Path(cwd), s1cfg)
        if inv.kind == "launch" and inv.launch is not None and enabled & {"S2", "S3", "S4", "S5"}:
            lt = inv.launch
            if lt.ecosystem == "npm":
                _, ver = launch.split_npm_spec(lt.spec)
            else:
                _, ver = launch.split_py_spec(lt.spec)
            try:
                findings += signals.check(lt.ecosystem, lt.package, ver if lt.pinned else None,
                                          lock.get((lt.ecosystem, lt.package)), enabled)
            except http.HttpError as e:
                findings.append(Finding("gate", "lookup_failed", "warn", lt.package,
                                        f"registry lookup failed (HTTP {e.status})"))
    return decide(findings)
