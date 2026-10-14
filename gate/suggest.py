"""Safer alternatives for a flagged command. Suggestions never change the gate's decision.

For each actionable finding, propose a replacement and keep it only if the gate passes the rewritten command:

  typosquat       S1 name_proximity       the popular package the name imitates
  fixed_version   S1 vulnerable_pin       the lowest release that fixes every listed advisory
  last_good       S2-S5, H1, H3,          the newest version between the locked and the resolved one that
                  integrity mismatch      passes every lock check (live registry only)
  locked_version  same                    the version in mcp-lock.json, which the user already reviewed
  similar_name    S1 absent / new_package up to three popular names within edit distance 2 (hints for an
                                          invented or slop-squatted name)
  lock_first      gate unlocked           advice only: review the server, then run `mcplock lock`

A rewritten command "passes" when the gate raises no warn/block finding on it, except `gate unlocked` (a real
package may simply not be locked yet) and S1's age rule for a package that is already in the lock (the rule
guards first use; Phase 5 age-rule sensitivity). Suggestions that cannot be checked are dropped, so the
feature can never point an agent at something the gate itself would stop.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from census import launch
from census import versions as V
from gate import command, s1, signals
from gate.findings import Finding

LOCK_CHECKS = {"S2", "S3", "S4", "S5", "H1", "H3"}
MAX_SUGGESTIONS = 3
LAST_GOOD_LIMIT = 3
FIX_STEPS = 4


@dataclass
class Suggestion:
    kind: str
    command: str | None  # runnable replacement, or None for advice
    because: str
    verified: bool

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ names
def _norm(eco: str, name: str) -> str:
    return launch.pep503(name) if eco == "pypi" else name.lower()


def _split(eco: str, spec: str) -> tuple[str, str | None]:
    return launch.split_npm_spec(spec) if eco == "npm" else launch.split_py_spec(spec)


def _spec(eco: str, name: str, version: str | None) -> str:
    if not version:
        return name
    return f"{name}@{version}" if eco == "npm" else f"{name}=={version}"


def edit_distance(a: str, b: str, cap: int = 3) -> int:
    """Optimal-string-alignment distance (transpositions count 1), stopping early above `cap`."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev2, prev = None, list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        cur = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        if min(cur) > cap:
            return cap + 1
        prev2, prev = prev, cur
    return prev[-1]


def similar_popular(eco: str, name: str, cfg: s1.S1Config, k: int = 3, max_dist: int = 2) -> list[str]:
    """Popular names close to `name`, best first (distance, then popularity rank)."""
    n = _norm(eco, name)
    scored = []
    for rank, q in enumerate(s1.popular(eco)[:cfg.p_size]):
        qn = _norm(eco, q)
        if qn == n:
            continue
        d = min(edit_distance(n, qn, max_dist), edit_distance(s1._sepnorm(n), s1._sepnorm(qn), max_dist))
        if d <= max_dist:
            scored.append((d, rank, q))
    return [q for _, _, q in sorted(scored)[:k]]


# ------------------------------------------------------------------ command rewriting
def rewrite(cmd: str, eco: str, pkg: str, new_spec: str) -> str | None:
    """Replace the token that names `pkg` with `new_spec`; None if the command does not name it."""
    out, hit = [], False
    for tok in cmd.split(" "):
        prefix = "--package=" if tok.startswith("--package=") else ""
        core = tok[len(prefix):].strip("\"'")
        quote = tok[len(prefix)] if tok[len(prefix):len(prefix) + 1] in "\"'" and tok[-1:] in "\"'" else ""
        if core and not core.startswith("-") and _norm(eco, _split(eco, core)[0]) == _norm(eco, pkg):
            out.append(f"{prefix}{quote}{new_spec}{quote}")
            hit = True
        else:
            out.append(tok)
    return " ".join(out) if hit else None


def _packages(cmd: str) -> dict[str, tuple[str, str, str | None]]:
    """normalised name -> (ecosystem, name as written, version as written) for every spec in the command."""
    out = {}
    for inv in command.parse(cmd):
        specs = list(inv.specs) + ([inv.launch.spec] if inv.launch is not None else [])
        for sp in specs:
            name, ver = _split(inv.ecosystem, sp)
            if inv.ecosystem in ("npm", "pypi") and name:
                out[_norm(inv.ecosystem, name)] = (inv.ecosystem, name, ver)
    return out


# ------------------------------------------------------------------ candidates
def _vkey(eco: str, v: str):
    return s1._vkey(eco, v)


def last_good(eco: str, pkg: str, entry: dict, target: str, enabled: frozenset) -> str | None:
    """Newest version strictly between the locked and the resolved one with no warn/block lock finding."""
    try:
        vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
    except Exception:  # noqa: BLE001 - a suggestion must never break the gate
        return None
    lo, hi = _vkey(eco, entry["version"]), _vkey(eco, target)
    between = [v["version"] for v in vs if not v["prerelease"] and lo < _vkey(eco, v["version"]) < hi]
    for v in reversed(between[-LAST_GOOD_LIMIT:]):
        try:
            fs = signals.check(eco, pkg, v, entry, enabled - {"S1"})
        except Exception:  # noqa: BLE001
            continue
        if not any(f.severity in ("warn", "block") for f in fs):
            return v
    return None


def fixed_version(eco: str, name: str, ver: str, steps: int = FIX_STEPS) -> str | None:
    """Lowest release clear of every advisory reachable from `ver`. A release that fixes the advisories on
    `ver` can carry newer ones of its own (e.g. axios 0.21.0 -> 0.33.0 -> 0.34.0), so step forward until
    OSV lists none; None if that takes more than `steps` hops."""
    v = ver
    for _ in range(steps):
        fixes = [x["lowest_fix"] for x in s1.osv_fixable(eco, name, v)]
        if not fixes:
            return v if v != ver else None
        v = max(fixes, key=lambda x: _vkey(eco, x))
    return None


def candidates(cmd: str, findings: list[Finding], lock: dict, cfg: s1.S1Config,
               enabled: frozenset) -> list[tuple[str, str, str, str | None, str]]:
    """(kind, ecosystem, package as written, replacement spec or None for advice, because), best first."""
    pk = _packages(cmd)
    out = []
    seen: set[tuple[str, str]] = set()
    for f in findings:
        if f.severity == "info" or not f.package or (f.check, f.package) in seen:
            continue
        seen.add((f.check, f.package))
        hit = pk.get(_norm("npm", f.package)) or pk.get(_norm("pypi", f.package))
        if hit is None:
            continue  # package only named in a project file: no command to rewrite
        eco, name, ver = hit
        if f.signal == "S1" and f.check == "name_proximity":
            q = s1.name_proximity(eco, name, cfg)
            if q:
                out.append(("typosquat", eco, name, q, f"'{name}' imitates the popular package '{q}'"))
        elif f.signal == "S1" and f.check == "vulnerable_pin" and ver:
            fix = fixed_version(eco, name, ver)
            if fix:
                out.append(("fixed_version", eco, name, _spec(eco, name, fix),
                            f"{name} {fix} fixes the advisories on {ver}"))
        elif f.signal == "S1" and f.check in ("absent", "new_package"):
            for q in similar_popular(eco, name, cfg):
                out.append(("similar_name", eco, name, q,
                            f"'{name}' is {'unknown' if f.check == 'absent' else 'new'}; "
                            f"did you mean the popular package '{q}'?"))
        elif f.signal in LOCK_CHECKS or (f.signal == "gate" and f.check == "integrity_mismatch"):
            out += _rollback(eco, name, ver, lock, enabled)
        elif f.signal == "gate" and f.check == "unlocked":
            out.append(("lock_first", eco, name, None,
                        f"{name} is not in mcp-lock.json: review it, then run `mcplock lock` to pin it"))
    # Any other flagged package that is locked (e.g. caught only by S1) can still roll back to its lock.
    for eco, name, ver in pk.values():
        if any(c[2] == name and c[0] in ("last_good", "locked_version") for c in out):
            continue
        if any(f.package and _norm(eco, f.package) == _norm(eco, name) and f.severity != "info"
               for f in findings):
            out += _rollback(eco, name, ver, lock, enabled)
    return out


def file_candidates(cmd: str, findings: list[Finding], cfg: s1.S1Config) -> list[tuple]:
    """Like candidates(), for packages named only in a project file (requirements.txt, package.json,
    pyproject.toml): there is no command token to rewrite, so these become verified advice."""
    ecos = {inv.ecosystem for inv in command.parse(cmd)} & {"npm", "pypi"}
    if len(ecos) != 1:
        return []
    eco = ecos.pop()
    in_cmd = _packages(cmd)
    out = []
    for f in findings:
        if f.signal != "S1" or f.severity == "info" or not f.package or _norm(eco, f.package) in in_cmd:
            continue
        name = f.package
        if f.check == "name_proximity":
            q = s1.name_proximity(eco, name, cfg)
            if q:
                out.append(("typosquat", eco, name, q, f"'{name}' imitates the popular package '{q}'"))
        elif f.check == "vulnerable_pin":
            m = re.search(re.escape(name) + r"==(\S+) has", f.reason)
            fix = fixed_version(eco, name, m.group(1)) if m else None
            if fix:
                out.append(("fixed_version", eco, name, _spec(eco, name, fix),
                            f"{name} {fix} fixes the advisories on {m.group(1)}"))
        elif f.check in ("absent", "new_package"):
            for q in similar_popular(eco, name, cfg)[:1]:
                out.append(("similar_name", eco, name, q, f"did you mean the popular package '{q}'?"))
    return out


def _standalone(eco: str, spec: str) -> str:
    return f"npm install {spec}" if eco == "npm" else f"pip install {spec}"


def _rollback(eco: str, name: str, ver: str | None, lock: dict, enabled: frozenset) -> list:
    entry = lock.get((eco, name))
    if not entry:
        return []
    target = signals.resolve(eco, name, ver)
    if target and target["version"] == entry["version"]:
        return []
    out = []
    good = last_good(eco, name, entry, target["version"], enabled) if target else None
    if good:
        out.append(("last_good", eco, name, _spec(eco, name, good),
                    f"{name} {good} is the newest version that passes every lock check"))
    out.append(("locked_version", eco, name, _spec(eco, name, entry["version"]),
                f"{name} {entry['version']} is the version you reviewed and locked"))
    return out


def passes(findings: list[Finding], lock: dict, only: str | None = None) -> bool:
    """No warn/block finding (on package `only`, if given), apart from the two exemptions above."""
    locked = {_norm(eco, n) for eco, n in lock}
    for f in findings:
        if f.severity not in ("warn", "block"):
            continue
        if only is not None and (not f.package or
                                 _norm("npm", f.package) != only and _norm("pypi", f.package) != only):
            continue
        if f.signal == "gate" and f.check == "unlocked":
            continue
        if f.signal == "S1" and f.check == "new_package" and f.package and \
                (_norm("npm", f.package) in locked or _norm("pypi", f.package) in locked):
            continue
        return False
    return True


def suggest(cmd: str, findings: list[Finding], lock: dict, verify) -> list[Suggestion]:
    """`verify(command) -> findings` re-runs the gate (without suggestions) on a rewritten command.

    Each replacement is first checked on its own package; the replacements that pass are combined into one
    command, which is offered only if the gate passes it as a whole. Alternatives for the same package follow.
    """
    advice: list[Suggestion] = []
    chosen: dict[str, tuple[str, str, str, str]] = {}  # package -> (kind, eco, spec, because)
    alternatives: list[tuple[str, str, str, str, str]] = []
    for kind, eco, name, spec, because in candidates(cmd, findings, lock, verify.cfg, verify.enabled):
        if spec is None:
            if not any(a.because == because for a in advice):
                advice.append(Suggestion(kind, None, because, False))
            continue
        key = _norm(eco, name)
        new_cmd = rewrite(cmd, eco, name, spec)
        if new_cmd is None or new_cmd == cmd:
            continue
        try:
            ok = passes(verify(new_cmd), lock, only=_norm(eco, _split(eco, spec)[0]))
        except Exception:  # noqa: BLE001 - unverifiable (e.g. offline replay): drop it
            ok = False
        if not ok:
            continue
        if key not in chosen:
            chosen[key] = (kind, eco, spec, because)
        elif spec == chosen[key][2] or any(alt[3] == spec for alt in alternatives):
            continue  # the same replacement reached through a second finding
        elif len(alternatives) < MAX_SUGGESTIONS - 1:
            alternatives.append((kind, eco, name, spec, because))
    # Packages named only in project files: verify the replacement on its own, offer it as advice.
    edits: dict[str, Suggestion] = {}
    for kind, eco, name, spec, because in file_candidates(cmd, findings, verify.cfg):
        key = _norm(eco, name)
        if key in edits:
            continue
        try:
            ok = passes(verify(_standalone(eco, spec)), lock, only=_norm(eco, _split(eco, spec)[0]))
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            edits[key] = Suggestion(kind, None, f"{because}: in your project files, change '{name}' to "
                                                f"'{spec}'", True)
    advice = list(edits.values()) + advice
    out: list[Suggestion] = []
    if chosen:
        combined = cmd
        for key, (_kind, eco, spec, _because) in chosen.items():
            name = next(n for e, n, _ in _packages(cmd).values() if _norm(e, n) == key)
            combined = rewrite(combined, eco, name, spec) or combined
        try:
            ok = passes(verify(combined), lock)
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            kinds = [c[0] for c in chosen.values()]
            out.append(Suggestion(kinds[0] if len(set(kinds)) == 1 else "combined", combined,
                                  "; ".join(c[3] for c in chosen.values()), True))
            if len(chosen) == 1:  # same package: offer the other passing alternatives too
                for kind, eco, name, spec, because in alternatives:
                    out.append(Suggestion(kind, rewrite(cmd, eco, name, spec), because, True))
    return out[:MAX_SUGGESTIONS] + advice
