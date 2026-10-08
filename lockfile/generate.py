"""Reference generator: MCP config (.mcp.json, claude_desktop_config.json, ...) -> mcp-lock.json.

Never executes package code: archives are fetched, digest-verified and analysed statically.

Usage: python -m lockfile.generate <config.json> [-o mcp-lock.json]
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from census import extract_js, extract_py, launch, tarballs
from census import versions as V
from census.run_extract import _key
from census.tooldefs import dedupe, tools_hash
from lockfile import identity

LOCK_VERSION = "0.1"


def _servers(text: str) -> dict[str, dict]:
    obj = json.loads(launch.strip_jsonc_comments(text))
    return launch._servers(obj)


def resolve(eco: str, pkg: str, spec_version: str | None) -> dict:
    vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
    if not vs:
        raise ValueError(f"{eco}:{pkg} has no versions")
    if spec_version:
        match = [v for v in vs if v["version"] == spec_version.lstrip("v")]
        if not match:
            raise ValueError(f"{eco}:{pkg}@{spec_version} not found")
        return match[0]
    stable = [v for v in vs if not v["prerelease"]]
    return (stable or vs)[-1]


def lock_entry(eco: str, pkg: str, version_meta: dict, runner: str, args: list[str]) -> dict:
    v = version_meta
    key = _key(eco, pkg, v)
    if eco == "npm":
        archive, integ = tarballs.fetch(v["archive_url"], key, integrity=v.get("integrity"),
                                        shasum=v.get("shasum"))
        prov = identity.npm_identity(v.get("attestation_url"))
    else:
        archive, integ = tarballs.fetch(v["archive_url"], key, sha256=v.get("sha256"))
        prov = identity.pypi_identity(pkg, v["version"], v["filename"])
    src = tarballs.extract(archive, key.rsplit(".tgz", 1)[0])
    raw, _ = (extract_js if eco == "npm" else extract_py).extract_dir(src)
    tools, _ = dedupe([t for t in raw if t.is_valid()])
    entry = {
        "ecosystem": eco, "name": pkg, "version": v["version"],
        "launch": {"runner": runner, "args": args},
        "integrity": integ,
        "archive": v["archive_url"] if eco == "npm" else v["filename"],
        "provenance": prov,
        "tools": {"hash": "sha256:" + tools_hash(tools) if tools else None,
                  "method": "static", "names": sorted(t.name for t in tools)},
    }
    if eco == "npm":
        entry["publisher"] = {"publisher": v.get("publisher"), "maintainers": v.get("maintainers")}
        entry["installScripts"] = sorted(v.get("install_scripts") or {})
    return entry


def generate(config_path: Path) -> dict:
    servers = _servers(config_path.read_text(encoding="utf-8"))
    lock = {"lockfileVersion": LOCK_VERSION,
            "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "servers": {}}
    skipped = {}
    for sid, cfg in servers.items():
        if not isinstance(cfg, dict) or not isinstance(cfg.get("command"), str):
            skipped[sid] = "not a command launch"
            continue
        args = [str(a) for a in cfg.get("args") or []]
        lt = launch.parse(cfg["command"], args)
        if lt is None:
            skipped[sid] = "not an npm/PyPI runner launch"
            continue
        if lt.ecosystem == "npm":
            _, ver = launch.split_npm_spec(lt.spec)
        else:
            _, ver = launch.split_py_spec(lt.spec)
        pinned = ver if lt.pinned else None
        meta = resolve(lt.ecosystem, lt.package, pinned)
        lock["servers"][sid] = lock_entry(lt.ecosystem, lt.package, meta, lt.runner, args)
    if skipped:
        lock["skipped"] = skipped
    return lock


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("mcp-lock.json"))
    a = ap.parse_args()
    lock = generate(a.config)
    a.output.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(f"locked {len(lock['servers'])} server(s) -> {a.output}")


if __name__ == "__main__":
    main()
