"""S2-S5: compare what a launch/install would fetch now against its MCP-Lock entry.

S2 provenance continuity, S3 publisher change (npm), S4 new install script, S5 tool-definition
drift, plus an integrity check when the version is unchanged. Never executes package code.
"""

from __future__ import annotations

import re

from census import extract_js, extract_py, tarballs
from census import versions as V
from census.run_extract import _key
from census.tooldefs import dedupe, tools_hash
from gate.findings import Finding
from lockfile import identity

CI_PUBLISHER = re.compile(r"github actions|npm-oidc|^github-actions", re.I)


def _is_ci(name: str | None) -> bool:
    return bool(name) and bool(CI_PUBLISHER.search(name))


def resolve(eco: str, pkg: str, pinned: str | None) -> dict | None:
    """Version metadata that the launch/install would fetch now (pinned, else latest stable)."""
    vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
    if not vs:
        return None
    if pinned:
        return next((v for v in vs if v["version"] == pinned.lstrip("v")), None)
    stable = [v for v in vs if not v["prerelease"]]
    return (stable or vs)[-1]


def _integrity(eco: str, v: dict) -> str | None:
    if eco == "npm":
        return v.get("integrity") or (f"sha1-{v['shasum']}" if v.get("shasum") else None)
    return f"sha256-{v['sha256']}" if v.get("sha256") else None


def _identity(eco: str, pkg: str, v: dict) -> dict | None:
    if eco == "npm":
        return identity.npm_identity(v.get("attestation_url"))
    return identity.pypi_identity(pkg, v["version"], v["filename"])


def static_tools(eco: str, pkg: str, v: dict) -> tuple[str | None, list[str]]:
    key = _key(eco, pkg, v)
    if eco == "npm":
        archive, _ = tarballs.fetch(v["archive_url"], key, integrity=v.get("integrity"),
                                    shasum=v.get("shasum"))
    else:
        archive, _ = tarballs.fetch(v["archive_url"], key, sha256=v.get("sha256"))
    src = tarballs.extract(archive, key.rsplit(".tgz", 1)[0])
    raw, _ = (extract_js if eco == "npm" else extract_py).extract_dir(src)
    tools, _ = dedupe([t for t in raw if t.is_valid()])
    return ("sha256:" + tools_hash(tools) if tools else None), sorted(t.name for t in tools)


def check(eco: str, pkg: str, pinned: str | None, entry: dict | None,
          enabled: set[str] = frozenset({"S2", "S3", "S4", "S5"})) -> list[Finding]:
    f: list[Finding] = []
    target = resolve(eco, pkg, pinned)
    if target is None:
        return [Finding("gate", "unresolvable", "block", pkg,
                        f"{pkg}{'@' + pinned if pinned else ''} cannot be resolved on {eco}")]
    tv = target["version"]
    if entry is None:
        return [Finding("gate", "unlocked", "warn", pkg,
                        f"{pkg}@{tv} is not in mcp-lock.json; review it and run `mcplock lock`")]
    lv = entry["version"]
    if tv == lv:
        if entry.get("integrity") and _integrity(eco, target) and \
                _integrity(eco, target) != entry["integrity"]:
            f.append(Finding("gate", "integrity_mismatch", "block", pkg,
                             f"{pkg}@{tv} archive digest differs from the lock"))
        return f
    f.append(Finding("gate", "version_drift", "info", pkg, f"{pkg} resolves to {tv}, locked {lv}"))
    # S2: provenance continuity
    if "S2" in enabled and entry.get("provenance"):
        new_id = _identity(eco, pkg, target)
        old = entry["provenance"]
        if new_id is None:
            f.append(Finding("S2", "provenance_lost", "block", pkg,
                             f"{pkg}@{tv} has no build provenance; {lv} was built by "
                             f"{old.get('sourceRepository')} {old.get('workflowPath')}"))
        elif new_id["digest"] != old.get("digest"):
            f.append(Finding("S2", "builder_changed", "block", pkg,
                             f"{pkg}@{tv} was built by {new_id.get('sourceRepository')} "
                             f"{new_id.get('workflowPath')}, locked build identity was "
                             f"{old.get('sourceRepository')} {old.get('workflowPath')}"))
    # S3: publisher change (npm only; PyPI has no per-release uploader)
    if "S3" in enabled and eco == "npm" and entry.get("publisher"):
        old_pub = entry["publisher"].get("publisher")
        maint = set(entry["publisher"].get("maintainers") or [])
        new_pub = target.get("publisher")
        if new_pub and not _is_ci(new_pub):
            if _is_ci(old_pub):
                f.append(Finding("S3", "ci_to_human", "warn", pkg,
                                 f"{pkg}@{tv} was published manually by '{new_pub}'; {lv} came "
                                 f"from CI"))
            elif new_pub not in maint and new_pub != old_pub:
                f.append(Finding("S3", "new_publisher", "warn", pkg,
                                 f"{pkg}@{tv} was published by '{new_pub}', not a locked "
                                 f"maintainer"))
    # S4: new install script (npm lifecycle; PyPI: sdist-only release runs build code)
    if "S4" in enabled:
        if eco == "npm":
            new = sorted(set(target.get("install_scripts") or {}) - set(entry.get("installScripts")
                                                                         or []))
            if new:
                f.append(Finding("S4", "new_install_script", "block", pkg,
                                 f"{pkg}@{tv} adds install script(s) {', '.join(new)}"))
        elif target.get("packagetype") == "sdist" and str(entry.get("archive", "")).endswith(".whl"):
            f.append(Finding("S4", "sdist_build", "warn", pkg,
                             f"{pkg}@{tv} ships only an sdist (runs build code); {lv} was a wheel"))
    # S5: tool-definition drift
    if "S5" in enabled and (entry.get("tools") or {}).get("method") == "static":
        try:
            h, names = static_tools(eco, pkg, target)
        except (tarballs.IntegrityError, tarballs.TooLarge) as e:
            f.append(Finding("S5", "tools_unverifiable", "warn", pkg, f"{pkg}@{tv}: {e}"))
            return f
        old_h = entry["tools"].get("hash")
        if h != old_h:
            old_names = set(entry["tools"].get("names") or [])
            added = sorted(set(names) - old_names)
            removed = sorted(old_names - set(names))
            what = []
            if added:
                what.append("adds " + ", ".join(added[:5]) + ("…" if len(added) > 5 else ""))
            if removed:
                what.append("removes " + ", ".join(removed[:5]) + ("…" if len(removed) > 5 else ""))
            if not what:
                what.append("changes tool descriptions or input schemas")
            f.append(Finding("S5", "tool_drift", "warn", pkg,
                             f"{pkg}@{tv} {'; '.join(what)} (locked {lv})"))
    return f
