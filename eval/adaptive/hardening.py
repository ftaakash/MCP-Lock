"""Phase 5 hardening switches H1-H5 (docs/PHASE5_PLAN.md §4), as overlays on the frozen gate.

These are *exploratory* proposals, not the pre-registered gate. Each is a transparent post-hoc rule
that adds findings to G's decision; the frozen gate code is never modified. Ground truth that static
analysis cannot see (the live tool list, a dependency's continuity, a release's extra files) is carried
in bundle["hardening"], known by construction of the synthetic attack, never by executing anything.

  H1 dependency-tree lock : a locked dependency's continuity identity breaks            -> block
  H2 runtime tools/list   : the server's live tool list differs maliciously from lock   -> block
  H3 PyPI all-files lock   : the release gained a file the lock does not cover            -> block
  H4 require-provenance    : the resolved version has no build provenance                -> block
  H5 command normalisation : rewrite npm exec / x / dlx / sh -c / $VAR / && chains to the
                             underlying npx launch so S1-S5 run on it

run(bundle, switches) returns the same shape as replay.run, with G (and its ablations) adjusted.
"""

from __future__ import annotations

import re

from eval import replay
from gate import command, core
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
    h = bundle.get("hardening") or {}
    extra: list[Finding] = []
    pkg = bundle["package"]
    if "H4" in switches and bundle.get("lock") is not None:
        tv = bundle["versions"][-1]["version"]
        ids = bundle.get("identities") or {}
        if ids.get(tv) is None:
            extra.append(Finding("H4", "provenance_required", "block", pkg,
                                 f"{pkg}@{tv} has no build provenance and the policy requires it"))
    if "H1" in switches and h.get("dep_break"):
        extra.append(Finding("H1", "dependency_continuity", "block", pkg,
                             f"a locked dependency of {pkg} changed its build identity / publisher"))
    if "H2" in switches and (h.get("runtime_poison") or h.get("no_version_change")):
        extra.append(Finding("H2", "runtime_tool_drift", "block", pkg,
                             f"{pkg} live tool list differs from the locked runtime hash"))
    if "H3" in switches and h.get("pypi_extra_file"):
        extra.append(Finding("H3", "unlocked_file", "block", pkg,
                             f"{pkg} release gained a file not covered by the lock's hashes"))
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
    res = replay.run(b)
    # H2/H3/H4 count as detections too; "detected" here means G would block/warn the attack.
    return {sid: _apply(bundle, switches, dec) for sid, dec in res.items()}
