"""Minimal npm semver range matching, enough to resolve dependency ranges the way npm does.

Supports exact versions, `^`, `~`, x-ranges (`1.x`, `1.2.*`, `*`, ``), comparators (`>=`, `<`, ...),
hyphen ranges (`1.2 - 2.3.4`), whitespace AND and `||` OR. Pre-releases only match a comparator set that
names a pre-release on the same `major.minor.patch` (node-semver's default, includePrerelease off).
Anything else (git URLs, `file:`, tarball URLs, `workspace:`) is not a registry range: parse_range -> None.
"""

from __future__ import annotations

import re

_NUM = r"0|[1-9]\d*"
_VER = re.compile(rf"^v?=?\s*({_NUM})\.({_NUM})\.({_NUM})(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_PARTIAL = re.compile(r"^v?=?\s*([0-9]+|[xX*])?(?:\.([0-9]+|[xX*]))?(?:\.([0-9]+|[xX*]))?"
                      r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")
_INF = 10**9


class Ver(tuple):
    """(major, minor, patch, pre) with npm precedence; pre is () for a release."""

    def __new__(cls, major, minor, patch, pre=()):
        return super().__new__(cls, (major, minor, patch, tuple(pre)))

    def key(self):
        pre = self[3]
        return (self[0], self[1], self[2], (1,) if not pre else
                (0, tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre)))

    def __lt__(self, o): return self.key() < o.key()
    def __le__(self, o): return self.key() <= o.key()
    def __gt__(self, o): return self.key() > o.key()
    def __ge__(self, o): return self.key() >= o.key()
    def __eq__(self, o): return isinstance(o, tuple) and self.key() == Ver(*o).key()
    def __hash__(self): return hash(self.key())


def parse(v: str) -> Ver | None:
    m = _VER.match(v.strip())
    if not m:
        return None
    return Ver(int(m[1]), int(m[2]), int(m[3]), tuple(m[4].split(".")) if m[4] else ())


def _wild(x):
    return x is None or x in ("x", "X", "*")


def _partial(s: str):
    m = _PARTIAL.match(s)
    if not m or not s:
        return None
    parts = [None if _wild(p) else int(p) for p in m.groups()[:3]]
    # once a part is a wildcard, everything after it is too
    for i in range(1, 3):
        if parts[i - 1] is None:
            parts[i] = None
    return parts, (tuple(m[4].split(".")) if m[4] and parts[2] is not None else ())


def _expand(tok: str) -> list[tuple[str, Ver]] | None:
    """One range token -> list of (op, version) comparators."""
    m = re.match(r"^(\^|~>?|>=|<=|>|<|=)?\s*(.*)$", tok)
    op, rest = m[1] or "", m[2]
    p = _partial(rest) if rest not in ("", "*", "x", "X") else ([None, None, None], ())
    if p is None:
        return None
    (M, m_, pt), pre = p
    if M is None:
        return [] if op in ("", "=", ">=", "<=", "^", "~", "~>") else [("<", Ver(0, 0, 0, ("0",)))]
    if op == "^":
        lo = Ver(M, m_ or 0, pt or 0, pre)
        if M > 0 or m_ is None:
            hi = Ver(M + 1, 0, 0, ("0",))
        elif m_ > 0 or pt is None:
            hi = Ver(0, m_ + 1, 0, ("0",))
        else:
            hi = Ver(0, 0, pt + 1, ("0",))
        return [(">=", lo), ("<", hi)]
    if op in ("~", "~>"):
        lo = Ver(M, m_ or 0, pt or 0, pre)
        hi = Ver(M + 1, 0, 0, ("0",)) if m_ is None else Ver(M, m_ + 1, 0, ("0",))
        return [(">=", lo), ("<", hi)]
    if m_ is None or pt is None:  # x-range with a comparator or bare partial
        lo = Ver(M, m_ or 0, 0)
        hi = Ver(M + 1, 0, 0, ("0",)) if m_ is None else Ver(M, m_ + 1, 0, ("0",))
        if op in ("", "="):
            return [(">=", lo), ("<", hi)]
        if op == ">":
            return [(">=", hi)]
        if op == ">=":
            return [(">=", lo)]
        if op == "<":
            return [("<", lo)]
        return [("<", hi)]  # <=
    return [(op or "=", Ver(M, m_, pt, pre))]


def parse_range(rng: str) -> list[list[tuple[str, Ver]]] | None:
    """Range string -> OR-list of AND-sets of comparators, or None if not a registry range."""
    rng = (rng or "").strip()
    if rng in ("", "latest"):
        rng = "*"
    if re.search(r"[:/#]", rng):  # git, file:, http(s):, workspace:, github shorthand
        return None
    out = []
    for part in rng.split("||"):
        part = part.strip()
        hy = re.match(r"^(\S+)\s+-\s+(\S+)$", part)
        if hy:
            lo, hi = _partial(hy[1]), _partial(hy[2])
            if lo is None or hi is None:
                return None
            (a, b, c), pre = lo
            comps = [(">=", Ver(a or 0, b or 0, c or 0, pre))]
            (a, b, c), pre = hi
            if a is not None:
                comps.append(("<=", Ver(a, b, c, pre)) if c is not None else
                             ("<", Ver(a + 1, 0, 0, ("0",)) if b is None else Ver(a, b + 1, 0, ("0",))))
            out.append(comps)
            continue
        part = re.sub(r"(\^|~>?|>=|<=|>|<|=)\s+", r"\1", part)
        comps = []
        for tok in part.split() or ["*"]:
            e = _expand(tok)
            if e is None:
                return None
            comps += e
        out.append(comps)
    return out


def _test(v: Ver, op: str, c: Ver) -> bool:
    return {"=": v == c, ">": v > c, ">=": v >= c, "<": v < c, "<=": v <= c}[op]


def satisfies(version: str, rng: str) -> bool:
    v = parse(version)
    sets = parse_range(rng)
    if v is None or sets is None:
        return False
    for comps in sets:
        if not all(_test(v, op, c) for op, c in comps):
            continue
        if not v[3]:
            return True
        # pre-release: only if some comparator names a pre-release on the same tuple
        if any(c[3] and c[:3] == v[:3] for _, c in comps):
            return True
    return False


def max_satisfying(versions: list[str], rng: str) -> str | None:
    ok = [(parse(v), v) for v in versions if satisfies(v, rng)]
    return max(ok, key=lambda x: x[0].key())[1] if ok else None
