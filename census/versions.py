"""Version histories for sampled packages, and the version sets used by G1 and G2 (plan §4-5).

G1 set: the K=10 most recent versions (by version precedence; all if fewer).
G2 set: every version published inside the 90-day window plus its immediate predecessor
(capped at 40 window versions per package; capping is recorded).
Per version we record archive URL + digest, publish time, publisher/maintainers (npm),
install scripts (npm), attestation presence, and pre-release flag.

Usage: python -m census.versions <sample.jsonl>
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from packaging.version import InvalidVersion, Version

from census import http, provenance
from census.meta import npm_url, pypi_url

K = 10
WINDOW_START = datetime(2026, 7, 10, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 8, 23, 59, 59, tzinfo=UTC)
WINDOW_CAP = 40
INSTALL_SCRIPTS = ("preinstall", "install", "postinstall", "prepare")


def _ts(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)


def _semver_key(v: str):
    core, _, pre = v.lstrip("v").partition("-")
    core = core.split("+")[0]
    try:
        nums = tuple(int(x) for x in core.split("."))
    except ValueError:
        nums = (0,)
    pre_key = (1,) if not pre else (0, tuple((0, int(p)) if p.isdigit() else (1, p)
                                             for p in pre.split(".")))
    return nums, pre_key


def npm_versions(pkg: str) -> list[dict]:
    doc = http.get_json(npm_url(pkg))
    times = doc.get("time") or {}
    out = []
    for v, meta in (doc.get("versions") or {}).items():
        dist = meta.get("dist") or {}
        scripts = meta.get("scripts") or {}
        out.append({
            "version": v, "published": times.get(v),
            "prerelease": "-" in v,
            "archive_url": dist.get("tarball"), "integrity": dist.get("integrity"),
            "shasum": dist.get("shasum"),
            "has_attestation": bool(dist.get("attestations")),
            "attestation_url": (dist.get("attestations") or {}).get("url"),
            "publisher": (meta.get("_npmUser") or {}).get("name"),
            "maintainers": sorted(m.get("name", "") for m in meta.get("maintainers") or []),
            "install_scripts": {k: scripts[k] for k in INSTALL_SCRIPTS if k in scripts},
            "deprecated": bool(meta.get("deprecated")),
            "dependencies_on_mcp_sdk": (meta.get("dependencies") or {}).get(
                "@modelcontextprotocol/sdk"),
        })
    out.sort(key=lambda r: _semver_key(r["version"]))
    return out


def _pick_file(files: list[dict]) -> dict | None:
    live = [f for f in files if not f.get("yanked")]
    for pred in (lambda f: f["filename"].endswith("-none-any.whl"),
                 lambda f: f["packagetype"] == "bdist_wheel",
                 lambda f: f["packagetype"] == "sdist"):
        cands = sorted((f for f in live if pred(f)), key=lambda f: f["filename"])
        if cands:
            return cands[0]
    return None


def pypi_versions(pkg: str) -> list[dict]:
    doc = http.get_json(pypi_url(pkg))
    out = []
    for v, files in (doc.get("releases") or {}).items():
        f = _pick_file(files or [])
        if f is None:
            continue
        try:
            pre = Version(v).is_prerelease
        except InvalidVersion:
            pre = False
        times = sorted(x["upload_time_iso_8601"] for x in files if x.get("upload_time_iso_8601"))
        out.append({"version": v, "published": times[0] if times else None, "prerelease": pre,
                    "archive_url": f["url"], "filename": f["filename"],
                    "sha256": f["digests"].get("sha256"), "packagetype": f["packagetype"]})

    def key(r):
        try:
            return (0, Version(r["version"]))
        except InvalidVersion:
            return (-1, r["version"])

    out.sort(key=key)
    return out


def select(versions: list[dict]) -> tuple[list[dict], dict]:
    g1 = {v["version"] for v in versions[-K:]}
    in_window = [i for i, v in enumerate(versions)
                 if (t := _ts(v["published"])) and WINDOW_START <= t <= WINDOW_END]
    capped = len(in_window) > WINDOW_CAP
    in_window = in_window[-WINDOW_CAP:]
    g2 = set()
    for i in in_window:
        g2.add(versions[i]["version"])
        if i > 0:
            g2.add(versions[i - 1]["version"])
    chosen = [dict(v, in_g1=v["version"] in g1, in_g2=v["version"] in g2,
                   in_window=v["version"] in {versions[i]["version"] for i in in_window},
                   order=idx)
              for idx, v in enumerate(versions) if v["version"] in g1 | g2]
    return chosen, {"n_versions_total": len(versions), "n_window_versions": len(in_window),
                    "window_capped": capped}


def _provenance_detail(eco: str, pkg: str, v: dict) -> dict | None:
    try:
        if eco == "npm" and v.get("attestation_url"):
            doc = http.get_json(v["attestation_url"])
            for att in doc.get("attestations", []):
                if "slsa" in att.get("predicateType", ""):
                    return {"predicateType": att["predicateType"]}
            return {"predicateType": None}
        if eco == "pypi":
            url = f"https://pypi.org/integrity/{pkg}/{v['version']}/{v['filename']}/provenance"
            http.get_json(url, headers={"Accept": "application/vnd.pypi.integrity.v1+json"})
            return {"pypi_provenance": True}
    except http.HttpError as e:
        if eco == "pypi" and e.status == 404:
            return {"pypi_provenance": False}
        return {"error": e.status}
    return None


def run(sample_path: str) -> Path:
    sample = [json.loads(x) for x in open(sample_path, encoding="utf-8")]

    def work(s):
        eco, pkg = s["ecosystem"], s["package"]
        try:
            vs = npm_versions(pkg) if eco == "npm" else pypi_versions(pkg)
        except http.HttpError as e:
            return {**s, "error": f"HTTP {e.status}", "versions": []}
        chosen, info = select(vs)
        for v in chosen:
            v["provenance"] = _provenance_detail(eco, pkg, v)
        return {**s, **info, "versions": chosen}

    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(work, sample))
    out = Path(sample_path).with_name("versions.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    nv = sum(len(r["versions"]) for r in rows)
    provenance.write(out, inputs=[Path(sample_path)],
                     params={"K": K, "window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
                             "window_cap": WINDOW_CAP, "versions_selected": nv})
    print(f"versions: {len(rows)} packages, {nv} versions -> {out}")
    return out


if __name__ == "__main__":
    run(sys.argv[1])
