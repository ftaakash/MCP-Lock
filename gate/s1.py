"""S1: reimplementation of the Bagmar & Saraf (arXiv:2607.15143) pre-install hook, extended to npm.

The paper's code is not public; this follows Appendix I. Two variants:
  literal     exactly what Appendix I states (substring URL match, P = top-1,000, only the command
              line and -r files are read, `make` is opaque).
  charitable  every ambiguity resolved in the baseline's favour (host-equality URL match, larger P
              with popular-name exemption, reads pyproject.toml / package.json / Makefile / .npmrc,
              env index variables, --find-links, nested -r files).
All differences are switches in S1Config so each one is reported with results.
See docs/BASELINE_REPLICATION.md for the deviation log.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

from census import http, launch
from census.meta import npm_url
from gate import command
from gate.findings import Finding

DATA = Path(__file__).parent / "data"
PYPI_TRUSTED = ("pypi.org", "files.pythonhosted.org", "test.pypi.org")
NPM_TRUSTED = ("registry.npmjs.org",)
NPM_TRUSTED_CHARITABLE = ("registry.npmjs.org", "registry.yarnpkg.com")
PIP_ENV_SOURCES = ("PIP_INDEX_URL", "PIP_EXTRA_INDEX_URL", "PIP_FIND_LINKS")
NPM_ENV_SOURCES = ("NPM_CONFIG_REGISTRY", "npm_config_registry")
NPM_ENV_CONFIG = ("NPM_CONFIG_USERCONFIG", "npm_config_userconfig", "NPM_CONFIG_GLOBALCONFIG",
                  "npm_config_globalconfig")


@dataclass
class S1Config:
    variant: str = "literal"
    p_size: int = 1000
    exempt_popular: int = 0  # names ranked within this many are never typosquats (0 = off)
    url_match: str = "substring"  # or "host"
    read_manifests: bool = False  # pyproject.toml / package.json for `pip install .` / `npm install`
    expand_make: bool = False
    read_npmrc: bool = False
    env_sources: bool = False  # PIP_INDEX_URL & co. / npm_config_registry as sources
    find_links: bool = False
    nested_requirements: bool = False
    name_check_requirement_files: bool = False
    check_launches: bool = False  # treat npx/uvx launches as installs (the paper hooks pip only)
    age_days: int = 30
    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def literal(cls, **kw):
        return cls(**kw)

    @classmethod
    def charitable(cls, **kw):
        base = dict(variant="charitable", p_size=5000, exempt_popular=15000, url_match="host",
                    read_manifests=True, expand_make=True, read_npmrc=True, env_sources=True,
                    find_links=True, nested_requirements=True, name_check_requirement_files=True,
                    check_launches=True)
        base.update(kw)
        return cls(**base)


# ------------------------------------------------------------------ name helpers
def _sepnorm(s: str) -> str:
    return re.sub(r"[-_.]+", "", s.lower())


def _lev1(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b, strict=True)) == 1
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]


def _transposition(a: str, b: str) -> bool:
    if len(a) != len(b) or a == b:
        return False
    d = [i for i in range(len(a)) if a[i] != b[i]]
    return len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]]


_LISTS: dict[str, list[str]] = {}


def popular(eco: str) -> list[str]:
    if eco not in _LISTS:
        f = DATA / ("top_pypi.json" if eco == "pypi" else "top_npm.json")
        _LISTS[eco] = json.loads(f.read_text(encoding="utf-8"))["names"]
    return _LISTS[eco]


def _norm_name(eco: str, name: str) -> str:
    return launch.pep503(name) if eco == "pypi" else name.lower()


def name_proximity(eco: str, name: str, cfg: S1Config) -> str | None:
    """Return the popular package `name` is confusable with, if any."""
    n = _norm_name(eco, name)
    ranked = popular(eco)
    if cfg.exempt_popular and n in {_norm_name(eco, x) for x in ranked[:cfg.exempt_popular]}:
        return None
    for q in ranked[:cfg.p_size]:
        qn = _norm_name(eco, q)
        if qn == n:
            continue
        if _lev1(n, qn) or _transposition(n, qn) or (_sepnorm(n) == _sepnorm(qn)):
            return q
    return None


# ------------------------------------------------------------------ registry metadata
def _npm_existed_before(name: str, cutoff: datetime) -> bool:
    """True if the package had downloads in the 30 days before `cutoff` (so it existed then)."""
    start = (cutoff - timedelta(days=30)).strftime("%Y-%m-%d")
    end = cutoff.strftime("%Y-%m-%d")
    try:
        d = http.get_json(f"https://api.npmjs.org/downloads/point/{start}:{end}/"
                          + name.replace("/", "%2F"))
    except http.HttpError:
        return False
    return (d.get("downloads") or 0) > 0


def registry_info(eco: str, name: str, now: datetime | None = None, age_days: int = 30) -> dict:
    """{'exists': bool, 'first_release': datetime|None}; lookup errors -> {'error': status}.

    Kept cheap because it runs on every install: PyPI uses the JSON simple API (per-file upload
    times). npm uses the abbreviated packument for existence; creation time is needed only when
    the package changed inside the age window and had no downloads before it, and only then is the
    (possibly tens of MB) full packument fetched. `first_release` is None when the package is
    known to be older than the window.
    """
    try:
        if eco == "pypi":
            doc = http.get_json(f"https://pypi.org/simple/{launch.pep503(name)}/",
                                headers={"Accept": "application/vnd.pypi.simple.v1+json"})
            files = doc.get("files") or []
            if not files:
                return {"exists": False}
            times = [f["upload-time"] for f in files if f.get("upload-time")]
        else:
            abbr = http.get_json(npm_url(name) + "?abbreviated",
                                 headers={"Accept": "application/vnd.npm.install-v1+json"})
            if not abbr.get("versions"):
                return {"exists": False}
            modified = abbr.get("modified")
            if now and modified:
                age = now - datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if age > timedelta(days=age_days):
                    return {"exists": True, "first_release": None}  # cannot be newer than modified
            if now and _npm_existed_before(name, now - timedelta(days=age_days)):
                return {"exists": True, "first_release": None}
            doc = http.get_json(npm_url(name))
            created = (doc.get("time") or {}).get("created")
            times = [created] if created else []
    except http.HttpError as e:
        return {"exists": False} if e.status == 404 else {"error": e.status}
    first = min((datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times), default=None)
    return {"exists": True, "first_release": first}


def _vkey(eco: str, v: str):
    if eco == "pypi":
        try:
            return (0, Version(v))
        except InvalidVersion:
            return (-1, v)
    from census.versions import _semver_key
    return _semver_key(v)


def osv_fixable(eco: str, name: str, version: str) -> list[dict]:
    """Advisories affecting name@version that have a fixed release > version (Appendix I)."""
    osv_eco = "PyPI" if eco == "pypi" else "npm"
    try:
        res = http.post_json("https://api.osv.dev/v1/query",
                             {"package": {"name": name, "ecosystem": osv_eco}, "version": version})
    except http.HttpError:
        return []
    out = []
    for vuln in res.get("vulns", []):
        fixes = []
        for aff in vuln.get("affected", []):
            pkg = aff.get("package", {})
            if pkg.get("ecosystem") != osv_eco or _norm_name(eco, pkg.get("name", "")) != \
                    _norm_name(eco, name):
                continue
            for rng in aff.get("ranges", []):
                for ev in rng.get("events", []):
                    if "fixed" in ev and _vkey(eco, ev["fixed"]) > _vkey(eco, version):
                        fixes.append(ev["fixed"])
        if fixes:
            out.append({"id": vuln["id"], "lowest_fix": min(fixes, key=lambda f: _vkey(eco, f))})
    return out


# ------------------------------------------------------------------ spec parsing
def pypi_spec(spec: str) -> tuple[str | None, str | None]:
    try:
        req = Requirement(spec)
    except InvalidRequirement:
        return None, None
    pins = [s.version for s in req.specifier if s.operator in ("==", "===") and "*" not in s.version]
    return req.name, (pins[0] if pins else None)


def npm_spec(spec: str) -> tuple[str | None, str | None]:
    name, ver = launch.split_npm_spec(spec)
    if not launch.NPM_NAME.match(name):
        return None, None
    return name, (ver.lstrip("v=") if ver and launch.SEMVER_EXACT.match(ver.lstrip("=")) else None)


def _url_trusted(url: str, trusted: tuple[str, ...], mode: str) -> bool:
    if mode == "substring":
        return any(t in url for t in trusted)
    p = urlparse(url if "://" in url else "https://" + url)
    return p.scheme == "https" and (p.hostname or "") in trusted


# ------------------------------------------------------------------ project files (charitable)
def _read_requirements(path: Path, cfg: S1Config, seen: set) -> dict:
    out = {"specs": [], "index": [], "trusted_hosts": [], "find_links": []}
    if path in seen or not path.is_file():
        return out
    seen.add(path)
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(" #")[0].strip()
        if not line or line.startswith("#"):
            continue
        toks = line.split(None, 1)
        flag, val = toks[0], (toks[1].strip() if len(toks) > 1 else "")
        if "=" in flag and flag.startswith("--"):
            flag, val = flag.split("=", 1)
        if flag in ("-i", "--index-url", "--extra-index-url"):
            out["index"].append(val)
        elif flag == "--trusted-host":
            out["trusted_hosts"].append(val)
        elif flag in ("-f", "--find-links") and cfg.find_links:
            out["find_links"].append(val)
        elif flag in ("-r", "--requirement", "-c", "--constraint"):
            if cfg.nested_requirements:
                sub = _read_requirements((path.parent / val).resolve(), cfg, seen)
                for k in out:
                    out[k] += sub[k]
        elif not line.startswith("-"):
            out["specs"].append(line)
    return out


def _pyproject_deps(cwd: Path) -> list[str]:
    f = cwd / "pyproject.toml"
    if not f.is_file():
        return []
    try:
        doc = tomllib.loads(f.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return []
    deps = list((doc.get("project") or {}).get("dependencies") or [])
    poetry = ((doc.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    deps += [k for k in poetry if k.lower() != "python"]
    return deps


def _package_json_deps(cwd: Path) -> list[str]:
    f = cwd / "package.json"
    if not f.is_file():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    out = []
    for sec in ("dependencies", "devDependencies", "optionalDependencies"):
        for k, v in (doc.get(sec) or {}).items():
            out.append(f"{k}@{v}" if isinstance(v, str) and launch.SEMVER_EXACT.match(v.lstrip("="))
                       else k)
    return out


def _npmrc_registries(cwd: Path) -> list[str]:
    f = cwd / ".npmrc"
    if not f.is_file():
        return []
    return [line.split("=", 1)[1].strip()
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
            if re.match(r"^\s*(@[^:]+:)?registry\s*=", line)]


def expand_make(cwd: Path, target: str | None, env: dict) -> list[command.Invocation]:
    """Expand the recipe of a Makefile target into the invocations it runs (simple make subset)."""
    f = cwd / "Makefile"
    if not f.is_file():
        return []
    lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
    variables = dict(env)
    for line in lines:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*[:?]?=\s*(.*)$", line)
        if m and not line.startswith("\t"):
            variables[m.group(1)] = m.group(2).strip()
    exported = {k: v for k, v in variables.items()
                if any(re.match(rf"^\s*export\s+{k}\b", ln) for ln in lines)}
    targets: dict[str, tuple[list[str], list[str]]] = {}
    cur = None
    for line in lines:
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:(?!=)\s*(.*)$", line)
        if m:
            cur = m.group(1)
            targets[cur] = (m.group(2).split(), [])
        elif line.startswith("\t") and cur:
            targets[cur][1].append(line.strip().lstrip("@-"))
    name = target or next(iter(targets), None)
    out: list[command.Invocation] = []

    def run(t, depth=0):
        if t not in targets or depth > 5:
            return
        deps, recipe = targets[t]
        for d in deps:
            run(d, depth + 1)
        for cmd_line in recipe:
            expanded = re.sub(r"\$[({]([A-Za-z_][A-Za-z0-9_]*)[)}]",
                              lambda m: variables.get(m.group(1), ""), cmd_line)
            for inv in command.parse(expanded):
                inv.env = {**exported, **inv.env}
                out.append(inv)

    if name:
        run(name)
    return out


# ------------------------------------------------------------------ the gate
def check(cmd: str, cwd: Path, cfg: S1Config) -> list[Finding]:
    findings: list[Finding] = []
    for inv in command.parse(cmd):
        findings += check_invocation(inv, Path(cwd), cfg)
    return findings


def check_invocation(inv: command.Invocation, cwd: Path, cfg: S1Config) -> list[Finding]:
    if inv.kind == "make":
        if not cfg.expand_make:
            return []
        out = []
        for sub in expand_make(cwd, inv.make_target, inv.env):
            out += check_invocation(sub, cwd, cfg)
        return out
    if inv.kind == "launch" and not cfg.check_launches:
        return []
    eco = inv.ecosystem
    f: list[Finding] = []

    def add(check_name, pkg, reason):
        f.append(Finding("S1", check_name, "block", pkg, reason))

    trusted = PYPI_TRUSTED if eco == "pypi" else (
        NPM_TRUSTED_CHARITABLE if cfg.variant == "charitable" else NPM_TRUSTED)
    # (6) config poisoning
    if eco == "pypi" and "PIP_CONFIG_FILE" in inv.env:
        add("config_poisoning", None, f"PIP_CONFIG_FILE={inv.env['PIP_CONFIG_FILE']} repoints pip")
    if eco == "npm" and any(k in inv.env for k in NPM_ENV_CONFIG):
        k = next(k for k in NPM_ENV_CONFIG if k in inv.env)
        add("config_poisoning", None, f"{k}={inv.env[k]} repoints npm configuration")
    # (4) source trust
    sources = list(inv.index_urls) + list(inv.extra_index_urls)
    if cfg.find_links:
        sources += inv.find_links
    if cfg.env_sources:
        keys = PIP_ENV_SOURCES if eco == "pypi" else NPM_ENV_SOURCES
        sources += [inv.env[k] for k in keys if k in inv.env]
    if eco == "npm" and cfg.read_npmrc:
        sources += _npmrc_registries(cwd)
    for u in sources:
        if not _url_trusted(u, trusted, cfg.url_match):
            add("untrusted_source", None, f"untrusted package source {u}")
    for h in inv.trusted_hosts:
        add("trusted_host", None, f"--trusted-host {h} disables TLS verification")
    # (5) hidden directives in -r files
    specs = list(inv.specs)
    pins_from_files: list[str] = []
    for rf in inv.req_files + (inv.constraint_files if cfg.nested_requirements else []):
        r = _read_requirements((cwd / rf).resolve(), cfg, set())
        for u in r["index"] + r["find_links"]:
            add("hidden_source", None, f"{rf} redirects the index to {u}")
        for h in r["trusted_hosts"]:
            add("hidden_source", None, f"{rf} sets --trusted-host {h}")
        pins_from_files += r["specs"]
        if cfg.name_check_requirement_files:
            specs += r["specs"]
    # manifests (charitable): pip install . / -e . / npm install with no args
    if cfg.read_manifests:
        if eco == "pypi" and any(t in (".", "./") for t in inv.local_targets):
            specs += _pyproject_deps(cwd)
        if eco == "npm" and inv.from_manifest:
            specs += _package_json_deps(cwd)
    # (1)-(3) per package, (7) per pin
    seen = set()
    for s in specs:
        name, pin = pypi_spec(s) if eco == "pypi" else npm_spec(s)
        if not name or name in seen:
            continue
        seen.add(name)
        q = name_proximity(eco, name, cfg)
        if q:
            add("name_proximity", name, f"'{name}' is confusable with popular package '{q}'")
        info = registry_info(eco, name, cfg.now, cfg.age_days)
        if info.get("exists") is False:
            add("absent", name, f"'{name}' does not exist on {eco}")
        elif info.get("first_release") and cfg.now - info["first_release"] < timedelta(
                days=cfg.age_days):
            add("new_package", name, f"'{name}' was first published "
                                     f"{(cfg.now - info['first_release']).days} days ago")
        if pin:
            for v in osv_fixable(eco, name, pin):
                add("vulnerable_pin", name, f"{name}=={pin} has {v['id']}; fixed in "
                                            f"{v['lowest_fix']}")
    for s in pins_from_files:
        if cfg.name_check_requirement_files:
            continue  # already covered above
        name, pin = pypi_spec(s) if eco == "pypi" else npm_spec(s)
        if name and pin:
            for v in osv_fixable(eco, name, pin):
                add("vulnerable_pin", name, f"{name}=={pin} has {v['id']}; fixed in "
                                            f"{v['lowest_fix']}")
    return f
