"""Phase 5 hardening switches H1-H5 (docs/PHASE5_PLAN.md §4) on top of the frozen gate.

These are *exploratory*, not the pre-registered gate: with no switch on, the gate runs exactly as tagged
`prereg-v1`. H1-H3 are gate code; H4-H5 remain transparent post-hoc rules here.

  H1 dependency-tree lock : gate/deptree.py via replay (bundle `deps`, lock `dependencies`)
  H2 runtime tools/list   : gate/proxy.check on the case's pinned vs live tool list (bundle `runtime`).
                            The live list is known by construction of the synthetic attack (derived from
                            its source), never by executing the server.
  H3 PyPI all-files lock   : gate/signals.py via replay (bundle `files`, lock `files`)
  H4 require-provenance    : the resolved version has no build provenance                -> block
  H5 command normalisation : rewrite npm exec / x / dlx / sh -c / $VAR / && chains to the
                             underlying npx launch so S1-S5 run on it

run(bundle, switches) returns the same shape as replay.run, with G (and its ablations) adjusted; the
baselines S1-L / S1-C never get hardening.
"""

from __future__ import annotations

import re

from eval import replay
from gate import command, core, proxy
from gate.findings import Finding

LAUNCH_RE = re.compile(r"(?:npx|pnpx|bunx)\b|(?:pnpm|yarn|bun)\s+(?:dlx|x)\b|"
                       r"npm\s+(?:exec|x)\b|uvx\b|pipx\s+run\b")


def normalize_command(cmd: str) -> str:
    """H5: reduce evasive command shapes to a plain `npx -y <pkg>` / `uvx <pkg>` the parser handles.

    Unwraps `sh -c "..."`, `bash -lc '...'`, `cmd /c ...`; expands a leading `VAR=pkg; ... $VAR`;
    rewrites `npm exec`/`npm x`/`-p`/`--package=` and global-install chains to a launch form.
    """
    s = cmd.strip()
    m = re.match(r"""^(?:sh|bash)\s+-\w*c\s+(['"])(.*)\1$""", s)
    if m:
        s = m.group(2).strip()
    s = re.sub(r"^cmd\s+/c\s+", "", s)
    s = re.sub(r"^env\s+\w+=\S+\s+", "", s)
    # VAR=pkg; ... $VAR  -> substitute the variable
    mv = re.match(r"^(\w+)=(\S+)\s*;\s*(.*)$", s)
    if mv:
        s = mv.group(3).replace(f"${mv.group(1)}", mv.group(2)).replace(f"${{{mv.group(1)}}}",
                                                                        mv.group(2))
    # npm install -g X && adv-notes  /  npm i X && npx adv-notes  -> treat as installing X
    mg = re.match(r"^npm\s+(?:install|i)\s+(?:-g\s+|--global\s+)?(\S+)\s*&&", s)
    if mg:
        return f"npx -y {mg.group(1)}"
    # npm exec / npm x  -> npx
    s = re.sub(r"^npm\s+(?:exec|x)\b", "npx", s)
    # -p PKG / --package=PKG  -> the package is the launch target
    mp = re.search(r"(?:-p\s+|--package=)(\S+)", s)
    if mp:
        return f"npx -y {mp.group(1)}"
    return s


def _resolved_npm_launch(cmd: str):
    for inv in command.parse(cmd):
        if inv.kind == "launch" and inv.launch is not None:
            return inv.launch
    return None


def _apply(bundle: dict, switches: set[str], decision: dict) -> dict:
    """Add hardening findings to one system's decision dict and recompute detection."""
    extra: list[Finding] = []
    pkg = bundle["package"]
    if "H4" in switches and bundle.get("lock") is not None:
        tv = bundle["versions"][-1]["version"]
        ids = bundle.get("identities") or {}
        if ids.get(tv) is None:
            extra.append(Finding("H4", "provenance_required", "block", pkg,
                                 f"{pkg}@{tv} has no build provenance and the policy requires it"))
    rt = bundle.get("runtime")
    if "H2" in switches and bundle.get("lock") is not None and rt is not None:
        extra += proxy.check(proxy.pin(rt["pinned"]), rt["live"], pkg)
    if not extra:
        return decision
    findings = [Finding(f["signal"], f["check"], f["severity"], f["package"], f["reason"])
                for f in decision["findings"]] + extra
    d = core.decide(findings).to_dict()
    d["detected"] = replay.detected(d)
    d["detected_block"] = replay.detected(d, block_only=True)
    d["enabled"] = decision.get("enabled", [])
    return d


def run(bundle: dict, switches: set[str]) -> dict:
    b = dict(bundle)
    if "H5" in switches:
        b = {**bundle, "command": normalize_command(bundle["command"])}
    res = replay.run(b, frozenset(switches) & core.HARDENING)
    # H1-H4 findings count as detections (replay.COUNTED_SIGNALS); baselines are left untouched.
    return {sid: dec if sid in replay.BASELINE_SYSTEMS else _apply(bundle, switches, dec)
            for sid, dec in res.items()}
