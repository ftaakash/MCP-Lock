"""H1 (exploratory, docs/PHASE5_PLAN.md §4): lock the resolved npm dependency tree and check its continuity.

`npx -y pkg@1.0.0` pins the server's own archive, but npm resolves every dependency range afresh, so a
dependency can change under a locked server (E9). The lock therefore records every node of the tree the
server resolved to at lock time, and the gate re-resolves the tree and applies the S2-S4 rules per node:

  same name@version, different archive digest            -> block  dep_integrity_mismatch
  new version of a locked dependency:
    locked version had provenance, new one has none      -> block  dep_provenance_lost
    different continuity identity                         -> block  dep_builder_changed
    published manually after CI, or by a non-maintainer   -> warn   dep_ci_to_human / dep_new_publisher
    adds an install script                                -> block  dep_new_install_script
  dependency not in the lock that runs an install script  -> block  dep_new_install_script
  dependency not in the lock otherwise                    -> info   dep_added

Resolution follows npm: `dependencies`, `optionalDependencies` and non-optional `peerDependencies`, each range
resolved to its highest satisfying stable version (npm prefers the `latest` tag when it satisfies; the tag's
history is not recorded, so as-of resolution uses the highest stable match). Never executes package code.
"""

from __future__ import annotations

import re
from collections import deque
from datetime import datetime

from census import http
from census.meta import npm_url
from gate import semver
from gate.findings import Finding
from lockfile import identity

MAX_NODES = 3000
CI_PUBLISHER = re.compile(r"github actions|npm-oidc|^github-actions", re.I)
INSTALL_SCRIPTS = ("preinstall", "install", "postinstall")


def _ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def _person(x) -> str | None:
    """npm user/maintainer: {"name": ...} in current packuments, "name <email>" in old ones."""
    if isinstance(x, dict):
        return x.get("name")
    return x.split("<")[0].strip() or None if isinstance(x, str) else None


def _dict(x) -> dict:
    return x if isinstance(x, dict) else {}


def _node(meta: dict, published: str | None) -> dict:
    deps = dict(_dict(meta.get("optionalDependencies")))
    peer_opt = _dict(meta.get("peerDependenciesMeta"))
    for k, r in _dict(meta.get("peerDependencies")).items():
        if not _dict(peer_opt.get(k)).get("optional"):
            deps.setdefault(k, r)
    deps.update(_dict(meta.get("dependencies")))
    scripts = _dict(meta.get("scripts"))
    inst = sorted(k for k in INSTALL_SCRIPTS if k in scripts)
    if meta.get("gypfile") and "install" not in inst:
        inst = sorted(inst + ["install"])
    dist = _dict(meta.get("dist"))
    return {"version": meta.get("version"), "published": published,
            "integrity": dist.get("integrity") or (f"sha1-{dist['shasum']}" if dist.get("shasum") else None),
            "attestation_url": _dict(dist.get("attestations")).get("url"),
            "publisher": _person(meta.get("_npmUser")),
            "maintainers": sorted(n for m in meta.get("maintainers") or [] if (n := _person(m))),
            "install_scripts": inst, "deps": deps}


def versions(pkg: str, as_of: datetime | None = None) -> dict[str, dict]:
    """{version: node} for pkg from the npm packument, optionally only versions published by as_of."""
    doc = http.get_json(npm_url(pkg))
    times = doc.get("time") or {}
    out = {}
    for v, meta in (doc.get("versions") or {}).items():
        t = times.get(v)
        if as_of is not None and (t is None or _ts(t) > as_of):
            continue
        out[v] = _node(meta, t)
    return out


def _identity(node: dict) -> dict | None:
    try:
        return identity.npm_identity(node.get("attestation_url"))
    except http.HttpError as e:
        if e.status == 404:  # attestation advertised but not served: treated as no provenance
            return None
        raise


def _target(name: str, rng: str) -> tuple[str, str]:
    """Handle npm aliases: `"x": "npm:real@^1"` installs `real`."""
    if rng.startswith("npm:"):
        spec = rng[4:]
        at = spec.find("@", 1)  # skip a scope's leading "@"
        return (spec, "*") if at < 0 else (spec[:at], spec[at + 1:] or "*")
    return name, rng


def resolve(pkg: str, version: str, as_of: datetime | None = None) -> tuple[dict[str, dict], list[dict]]:
    """Tree of pkg@version: ({"name@version": node}, unresolved [{name, range, reason}]). Root excluded."""
    cache: dict[str, dict[str, dict]] = {}

    def vs(name):
        if name not in cache:
            try:
                cache[name] = versions(name, as_of)
            except http.HttpError as e:
                cache[name] = {"__error__": {"status": e.status}}
        return cache[name]

    root = vs(pkg).get(version)
    if root is None:
        return {}, [{"name": pkg, "range": version, "reason": "root version not found"}]
    nodes: dict[str, dict] = {}
    unresolved = []
    seen_req = set()
    q = deque(root["deps"].items())
    while q and len(nodes) < MAX_NODES:
        name, rng = q.popleft()
        name, rng = _target(name, str(rng))
        if (name, rng) in seen_req:
            continue
        seen_req.add((name, rng))
        avail = vs(name)
        if "__error__" in avail:
            unresolved.append({"name": name, "range": rng, "reason": f"HTTP {avail['__error__']['status']}"})
            continue
        if semver.parse_range(rng) is None:
            unresolved.append({"name": name, "range": rng, "reason": "not a registry range"})
            continue
        stable = [v for v in avail if "-" not in v]
        best = semver.max_satisfying(stable, rng) or semver.max_satisfying(list(avail), rng)
        if best is None:
            unresolved.append({"name": name, "range": rng, "reason": "no satisfying version"})
            continue
        key = f"{name}@{best}"
        if key in nodes:
            continue
        nodes[key] = avail[best]
        q.extend(avail[best]["deps"].items())
    if q:
        unresolved.append({"name": "*", "range": "*", "reason": f"tree truncated at {MAX_NODES} nodes"})
    return nodes, unresolved


def lock_tree(pkg: str, version: str, as_of: datetime | None = None) -> dict:
    """The lock's `dependencies` field: one record per resolved node, with its build identity."""
    nodes, unresolved = resolve(pkg, version, as_of)
    out = {}
    for key, n in sorted(nodes.items()):
        out[key] = {"integrity": n["integrity"],
                    "provenance": _identity(n) if n.get("attestation_url") else None,
                    "publisher": n["publisher"], "maintainers": n["maintainers"],
                    "installScripts": n["install_scripts"]}
    return {"nodes": out, "unresolved": unresolved}


def _split(key: str) -> tuple[str, str]:
    name, _, ver = key.rpartition("@")
    return name, ver


def _is_ci(name: str | None) -> bool:
    return bool(name) and bool(CI_PUBLISHER.search(name))


def check(pkg: str, version: str, locked: dict | None, as_of: datetime | None = None) -> list[Finding]:
    """Compare the tree pkg@version resolves to now (or as of a past time) against the locked tree."""
    if locked is None:
        return [Finding("H1", "tree_not_locked", "info", pkg,
                        f"{pkg}: the lock has no dependency tree (re-run `mcplock lock`)")]
    lnodes = locked.get("nodes") or {}
    by_name: dict[str, list[tuple[semver.Ver, str]]] = {}
    for key in lnodes:
        n, v = _split(key)
        if (pv := semver.parse(v)) is not None:
            by_name.setdefault(n, []).append((pv, key))
    nodes, _ = resolve(pkg, version, as_of)
    f: list[Finding] = []
    for key, node in sorted(nodes.items()):
        name, ver = _split(key)
        if key in lnodes:
            old = lnodes[key].get("integrity")
            if old and node["integrity"] and old != node["integrity"]:
                f.append(Finding("H1", "dep_integrity_mismatch", "block", pkg,
                                 f"dependency {key} archive digest differs from the lock"))
            continue
        if name not in by_name:
            if node["install_scripts"]:
                f.append(Finding("H1", "dep_new_install_script", "block", pkg,
                                 f"new dependency {key} runs install script(s) "
                                 f"{', '.join(node['install_scripts'])}"))
            else:
                f.append(Finding("H1", "dep_added", "info", pkg, f"new dependency {key}"))
            continue
        # baseline: the highest locked version of this dependency
        base_key = max(by_name[name], key=lambda x: x[0].key())[1]
        base = lnodes[base_key]
        if base.get("provenance"):
            if not node.get("attestation_url"):
                f.append(Finding("H1", "dep_provenance_lost", "block", pkg,
                                 f"dependency {key} has no build provenance; {base_key} was built by "
                                 f"{base['provenance'].get('sourceRepository')}"))
            else:
                new_id = _identity(node)
                if new_id is None or new_id.get("digest") != base["provenance"].get("digest"):
                    f.append(Finding("H1", "dep_builder_changed", "block", pkg,
                                     f"dependency {key} was built by "
                                     f"{(new_id or {}).get('sourceRepository')}, locked {base_key} by "
                                     f"{base['provenance'].get('sourceRepository')}"))
        new_pub, old_pub = node.get("publisher"), base.get("publisher")
        if new_pub and not _is_ci(new_pub):
            if _is_ci(old_pub):
                f.append(Finding("H1", "dep_ci_to_human", "warn", pkg,
                                 f"dependency {key} was published manually by '{new_pub}'; "
                                 f"{base_key} came from CI"))
            elif new_pub != old_pub and new_pub not in set(base.get("maintainers") or []):
                f.append(Finding("H1", "dep_new_publisher", "warn", pkg,
                                 f"dependency {key} was published by '{new_pub}', not a maintainer "
                                 f"of {base_key}"))
        added = sorted(set(node["install_scripts"]) - set(base.get("installScripts") or []))
        if added:
            f.append(Finding("H1", "dep_new_install_script", "block", pkg,
                             f"dependency {key} adds install script(s) {', '.join(added)}"))
    return f
