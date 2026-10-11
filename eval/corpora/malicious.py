"""Real-malicious corpus R-M (PREREG §3.2). Runs only inside Docker (DEVIATIONS #3).

Stages (each a container run; /data is the mcplock-mal volume, /out a host results folder that
receives only sanitized lists: ecosystem, name, version, dates, class):

  scan      --network none   parse OSV MAL- records (ossf/malicious-packages @ pinned commit) and
                             the DataDog compromised_lib index into candidate cases
  classify  network on       read registry version histories (metadata JSON only, cached in /data)
                             and apply the class rule C / N and the publication window
  sample    --network none   seeded selection: all C (cap 400), N to reach >= 200 (>= 100 N)

Usage (inside the container): python -m eval.corpora.malicious <stage> --data /data --out /out
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
from pathlib import Path

OSV_COMMIT = "1861f95ffacc04ed9d9c6049639098146030f14b"
DATADOG_COMMIT = "805fcd72db525244cae8dd32056efbd50b8b0e19"
RECORD_FLOOR = "2024-01-01"  # records published earlier concern versions published earlier
INDEX = Path(__file__).with_name("datadog_compromised_paths.txt")


def _all_versions(aff: dict) -> bool:
    """True if the affected entry covers every version (introduced 0, never fixed)."""
    evs = [ev for rg in aff.get("ranges", []) for ev in rg.get("events", [])]
    return any(ev.get("introduced") == "0" for ev in evs) and not any(
        "fixed" in ev or "last_affected" in ev or "limit" in ev for ev in evs)


def scan(data: Path, out: Path) -> None:
    root = data / "malicious-packages" / "osv" / "malicious"
    rows, skipped = [], {"pre_floor": 0, "other_ecosystem": 0, "no_versions": 0}
    for eco, osv_eco in (("npm", "npm"), ("pypi", "PyPI")):
        for f in sorted((root / eco).rglob("MAL-*.json")):
            r = json.loads(f.read_text(encoding="utf-8"))
            pub = r.get("published", "")
            if pub < RECORD_FLOOR:
                skipped["pre_floor"] += 1
                continue
            for aff in r.get("affected", []):
                pkg = aff.get("package", {})
                if pkg.get("ecosystem") != osv_eco:
                    skipped["other_ecosystem"] += 1
                    continue
                allv = _all_versions(aff)
                vs = sorted(set(aff.get("versions") or []))
                if not allv and not vs:
                    skipped["no_versions"] += 1
                rows.append({"source": "osv", "id": r["id"], "ecosystem": eco,
                             "name": pkg["name"], "published": pub,
                             "all_versions": allv, "versions": vs})
    # DataDog compromised_lib index: samples/<eco>/compromised_lib/<name>/<version>/<date>-...zip
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        parts = line.split("/")
        if len(parts) != 6 or not parts[5].endswith(".zip"):
            continue
        eco, dname, ver, fname = parts[1], parts[3], parts[4], parts[5]
        name = re.sub(r"^@([^@]+)@", r"@\1/", dname) if eco == "npm" else dname
        rows.append({"source": "datadog", "id": f"DD:{eco}:{name}@{ver}", "ecosystem": eco,
                     "name": name, "published": fname[:10], "all_versions": False,
                     "versions": [ver], "sample_path": line})
    out.mkdir(parents=True, exist_ok=True)
    with gzip.open(out / "mal_records.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in rows:
            g.write(json.dumps(r) + "\n")
    summary = {"osv_commit": OSV_COMMIT, "datadog_commit": DATADOG_COMMIT,
               "record_floor": RECORD_FLOOR, "skipped": skipped,
               "rows": {f"{s}:{e}": sum(1 for r in rows if r["source"] == s and r["ecosystem"] == e)
                        for s in ("osv", "datadog") for e in ("npm", "pypi")},
               "packages": {e: len({r["name"] for r in rows if r["ecosystem"] == e})
                            for e in ("npm", "pypi")},
               "osv_all_versions": sum(1 for r in rows if r["all_versions"])}
    (out / "scan_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary))


# ------------------------------------------------------------------ classify (network on)
WINDOW = ("2024-01-01T00:00:00+00:00", "2026-10-08T23:59:59+00:00")
C_MIN_DAYS = 7
SEED = 20261011
C_CAP = 400
N_MIN, R_MIN = 100, 200


def _use_volume_cache(data: Path) -> None:
    from census import http
    http.CACHE_DIR = data / "work" / "http"


def _iso(s: str | None) -> str | None:
    from datetime import UTC, datetime
    if not s:
        return None
    if len(s) == 10:
        s += "T00:00:00+00:00"
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC).isoformat()


def history(eco: str, name: str) -> dict:
    """{version: publish ISO time} from the registry, including versions npm still dates after
    unpublishing; {} if the registry has no record. Metadata JSON only."""
    from census import http
    from census.meta import npm_url, pypi_url
    try:
        doc = http.get_json(npm_url(name) if eco == "npm" else pypi_url(name))
    except http.HttpError as e:
        if e.status == 404:
            return {}
        raise
    if eco == "npm":
        t = dict(doc.get("time") or {})
        unpub = t.pop("unpublished", None)
        out = {v: _iso(s) for v, s in t.items() if v not in ("created", "modified") and
               isinstance(s, str)}
        if isinstance(unpub, dict):  # whole package unpublished: versions listed, times lost
            for v in unpub.get("versions") or []:
                out.setdefault(v, None)
        return out
    out = {}
    for v, files in (doc.get("releases") or {}).items():
        times = sorted(f["upload_time_iso_8601"] for f in files or [] if f.get(
            "upload_time_iso_8601"))
        out[v] = _iso(times[0]) if times else None
    return out


def _vkey(eco: str, v: str):
    from gate import s1
    return s1._vkey(eco, v)


def _norm(eco: str, name: str) -> str:
    from census import launch
    return launch.pep503(name) if eco == "pypi" else name.lower()


def classify(data: Path, out: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timedelta

    _use_volume_cache(data)
    rows = [json.loads(x) for x in gzip.open(out / "mal_records.jsonl.gz", "rt", encoding="utf-8")]
    by_pkg: dict[tuple, list] = {}
    for r in rows:
        by_pkg.setdefault((r["ecosystem"], _norm(r["ecosystem"], r["name"])), []).append(r)
    # registry histories only where class C is possible (no record says "all versions")
    need = sorted(k for k, rs in by_pkg.items() if not any(r["all_versions"] for r in rs))
    print(f"{len(need)} packages need a registry history", flush=True)

    def fetch(k):
        eco = k[0]
        name = by_pkg[k][0]["name"]
        try:
            return k, history(eco, name), None
        except Exception as e:  # recorded as lookup failure
            return k, None, f"{type(e).__name__}: {e}"

    hist, failures = {}, {}
    with ThreadPoolExecutor(8) as pool:
        for i, (k, h, err) in enumerate(pool.map(fetch, need), 1):
            if err:
                failures[f"{k[0]}:{k[1]}"] = err
            else:
                hist[k] = h
            if i % 1000 == 0:
                print(f"{i}/{len(need)} histories, {len(failures)} failures", flush=True)

    cases, dropped = {}, {"out_of_window": 0, "no_version": 0, "lookup_failed": 0}
    for k, rs in by_pkg.items():
        eco = k[0]
        if k in failures:
            dropped["lookup_failed"] += len(rs)
            continue
        h = hist.get(k, {})
        allv = any(r["all_versions"] for r in rs)
        affected = set().union(*[set(r["versions"]) for r in rs])
        for r in rs:
            if r["all_versions"]:
                listed = sorted((v for v in h), key=lambda v: _vkey(eco, v)) or r["versions"]
                version = listed[0] if listed else None
            else:
                if not r["versions"]:
                    dropped["no_version"] += 1
                    continue
                version = min(r["versions"], key=lambda v: _vkey(eco, v))
            t = h.get(version) if version else None
            t_src = "registry" if t else "record"
            t = t or _iso(r["published"])
            if not (WINDOW[0] <= t <= WINDOW[1]):
                dropped["out_of_window"] += 1
                continue
            cls = "N"
            if not allv and h:
                tt = datetime.fromisoformat(t) - timedelta(days=C_MIN_DAYS)
                if any(u not in affected and s and datetime.fromisoformat(s) <= tt
                       for u, s in h.items()):
                    cls = "C"
            key = (eco, k[1], version)
            c = cases.setdefault(key, {"ecosystem": eco, "name": r["name"], "version": version,
                                       "t": t, "t_source": t_src, "class": cls, "ids": [],
                                       "sources": [], "registry_listed": version in h,
                                       "sample_path": None})
            c["ids"].append(r["id"])
            if r["source"] not in c["sources"]:
                c["sources"].append(r["source"])
            if r.get("sample_path"):
                c["sample_path"] = r["sample_path"]
            if cls == "C":
                c["class"] = "C"
    with gzip.open(out / "mal_cases.jsonl.gz", "wt", encoding="utf-8") as g:
        for c in sorted(cases.values(), key=lambda c: (c["ecosystem"], c["name"], str(c["version"]))):
            g.write(json.dumps(c) + "\n")
    summary = {"window": WINDOW, "c_min_days": C_MIN_DAYS, "histories": len(hist),
               "lookup_failures": len(failures), "dropped": dropped,
               "cases": {f"{cl}:{e}": sum(1 for c in cases.values() if c["class"] == cl and
                                         c["ecosystem"] == e)
                         for cl in ("C", "N") for e in ("npm", "pypi")}}
    (out / "classify_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "classify_failures.json").write_text(json.dumps(failures, indent=1), encoding="utf-8")
    print(json.dumps(summary))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["scan", "classify"])
    ap.add_argument("--data", type=Path, default=Path("/data"))
    ap.add_argument("--out", type=Path, default=Path("/out"))
    a = ap.parse_args()
    {"scan": scan, "classify": classify}[a.stage](a.data, a.out)


if __name__ == "__main__":
    main()
