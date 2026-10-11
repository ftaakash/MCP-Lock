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


# ------------------------------------------------------------------ sample (network on)
def _largest_remainder(total: int, sizes: dict[str, int]) -> dict[str, int]:
    s = sum(sizes.values())
    raw = {k: total * v / s for k, v in sizes.items()} if s else {k: 0 for k in sizes}
    out = {k: int(v) for k, v in raw.items()}
    for k in sorted(raw, key=lambda k: raw[k] - out[k], reverse=True)[:total - sum(out.values())]:
        out[k] += 1
    return out


def sample(data: Path, out: Path) -> None:
    import random

    _use_volume_cache(data)
    cases = [json.loads(x) for x in gzip.open(out / "mal_cases.jsonl.gz", "rt", encoding="utf-8")]
    rng = random.Random(SEED)
    C = sorted((c for c in cases if c["class"] == "C"), key=lambda c: (c["ecosystem"], c["name"],
                                                                      str(c["version"])))
    if len(C) > C_CAP:
        py = [c for c in C if c["ecosystem"] == "pypi"]
        npm = [c for c in C if c["ecosystem"] == "npm"]
        rng.shuffle(npm)
        C = py + npm[:max(0, C_CAP - len(py))]
    n_quota = max(R_MIN - len(C), N_MIN)
    pool = {e: sorted((c for c in cases if c["class"] == "N" and c["ecosystem"] == e),
                      key=lambda c: (c["name"], str(c["version"]))) for e in ("npm", "pypi")}
    quota = _largest_remainder(n_quota, {e: len(v) for e, v in pool.items()})
    N, rejected = [], {"out_of_window_after_registry_check": 0, "lookup_failed": 0}
    for e in ("npm", "pypi"):
        cand = pool[e][:]
        rng.shuffle(cand)
        taken = 0
        for c in cand:
            if taken >= quota[e]:
                break
            try:
                h = history(e, c["name"])
            except Exception:
                rejected["lookup_failed"] += 1
                continue
            v = c["version"] or (sorted(h, key=lambda x: _vkey(e, x))[0] if h else None)
            t = (h.get(v) if v else None) or c["t"]
            if not (WINDOW[0] <= t <= WINDOW[1]):
                rejected["out_of_window_after_registry_check"] += 1
                continue
            N.append({**c, "version": v, "t": t, "t_source": "registry" if h.get(v) else c["t_source"],
                      "registry_listed": bool(v and v in h)})
            taken += 1
    with gzip.open(out / "mal_sample.jsonl.gz", "wt", encoding="utf-8") as g:
        for c in C + N:
            g.write(json.dumps(c) + "\n")
    summary = {"C_eligible": sum(c["class"] == "C" for c in cases), "C_selected": len(C),
               "C_by_ecosystem": {e: sum(c["ecosystem"] == e for c in C) for e in ("npm", "pypi")},
               "N_pool": {e: len(v) for e, v in pool.items()}, "N_quota": quota, "N_selected": len(N),
               "N_rejected": rejected, "R_M_total": len(C) + len(N), "seed": SEED}
    (out / "sample_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary))


# ------------------------------------------------------------------ fetch (network on, no parsing)
DD_RAW = ("https://raw.githubusercontent.com/DataDog/malicious-software-packages-dataset/"
          f"{DATADOG_COMMIT}/")


def _records(eco: str, name: str) -> dict:
    """{version: census.versions record} for versions the registry still lists."""
    from census import versions as V
    try:
        vs = V.npm_versions(name) if eco == "npm" else V.pypi_versions(name)
    except Exception:
        return {}
    return {v["version"]: v for v in vs}


def _ident(eco: str, name: str, rec: dict):
    from lockfile import identity
    if eco == "npm":
        return identity.npm_identity(rec.get("attestation_url"))
    return identity.pypi_identity(name, rec["version"], rec["filename"])


def fetch(data: Path, out: Path) -> None:
    """Metadata, identities and raw archives into /data/work. Archives are stored, never opened."""
    import hashlib

    from census import http, tarballs

    _use_volume_cache(data)
    arch = data / "work" / "archives"
    arch.mkdir(parents=True, exist_ok=True)
    cases = [json.loads(x) for x in gzip.open(out / "mal_sample.jsonl.gz", "rt", encoding="utf-8")]
    # every version any MAL record (OSV or DataDog) lists for a package is affected, as in classify
    affected: dict[tuple, set] = {}
    for x in map(json.loads, gzip.open(out / "mal_records.jsonl.gz", "rt", encoding="utf-8")):
        affected.setdefault((x["ecosystem"], _norm(x["ecosystem"], x["name"])), set()).update(
            x["versions"])
    rows = []
    for i, c in enumerate(cases, 1):
        eco, name, v = c["ecosystem"], c["name"], c["version"]
        recs = _records(eco, name)
        h = history(eco, name)
        row = {"case": c, "target": recs.get(v), "lock": None, "ids": {}, "archives": {},
               "first_release": min([s for s in h.values() if s and s <= c["t"]] + [c["t"]]),
               "errors": []}
        if c["class"] == "C":
            bad = affected.get((eco, _norm(eco, name)), set())
            prior = [u for u, s in h.items() if s and s < c["t"] and u in recs and u not in bad]
            prior.sort(key=lambda u: h[u])
            row["lock"] = recs[prior[-1]] if prior else None
            if row["lock"] is None:
                row["errors"].append("no listed unaffected version before t")
        for role in ("lock", "target"):
            rec = row[role]
            if rec is None:
                continue
            try:
                row["ids"][rec["version"]] = _ident(eco, name, rec)
            except Exception as e:
                row["errors"].append(f"identity {role}: {type(e).__name__}: {e}")
            key = hashlib.sha256(f"{eco}:{name}:{rec['version']}".encode()).hexdigest()[:24]
            dest = arch / f"{key}.{'tgz' if eco == 'npm' else rec['filename'].rsplit('.', 1)[-1]}"
            try:
                if not dest.exists():
                    dest.write_bytes(tarballs._download(rec["archive_url"]))
                row["archives"][role] = {"path": str(dest), "kind": "registry"}
            except (tarballs.TooLarge, http.HttpError, Exception) as e:
                row["archives"][role] = {"error": f"{type(e).__name__}"}
        if row["target"] is None and c.get("sample_path"):
            key = hashlib.sha256(c["sample_path"].encode()).hexdigest()[:24]
            dest = arch / f"{key}.ddzip"
            try:
                if not dest.exists():
                    dest.write_bytes(tarballs._download(DD_RAW + c["sample_path"]))
                row["archives"]["target"] = {"path": str(dest), "kind": "datadog"}
            except Exception as e:
                row["archives"]["target"] = {"error": f"datadog {type(e).__name__}"}
        rows.append(row)
        if i % 25 == 0:
            print(f"{i}/{len(cases)} fetched", flush=True)
    with gzip.open(data / "work" / "fetched.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in rows:
            g.write(json.dumps(r) + "\n")
    print(f"fetched {len(rows)} cases")


# ------------------------------------------------------------------ analyse (--network none)
def _dd_source(zpath: Path, dest: Path) -> tuple[Path, dict | None]:
    """Statically unpack the kept source files of a DataDog sample (encrypted zip)."""
    import zipfile

    from census import tarballs
    pj = None
    with zipfile.ZipFile(zpath) as zf:
        zf.setpassword(b"infected")
        names = [n.replace("\\", "/") for n in zf.namelist()]
        # samples sit under temp-folder prefixes; the package root is the shallowest folder that
        # holds npm's package/package.json or a Python project marker
        markers = [n for n in names if n.endswith("/package/package.json")
                   or n.rsplit("/", 1)[-1] in ("PKG-INFO", "setup.py", "pyproject.toml")]
        root = min((m.rsplit("/", 1)[0] + "/" for m in markers), key=lambda r: r.count("/"),
                   default="")
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if info.is_dir() or info.file_size > tarballs.MAX_FILE or not name.startswith(root):
                continue
            rel = name[len(root):]
            p = tarballs._safe_name(rel)
            if p is None:
                continue
            raw = zf.read(info)
            if rel == "package.json" and pj is None:
                try:
                    pj = json.loads(raw)
                except ValueError:
                    pass
            if tarballs.KEEP.search(p.name):
                tarballs._write(dest, p, raw)
    return dest, pj


def _tools_from_dir(eco: str, src: Path) -> dict:
    from census import extract_js, extract_py
    from census.tooldefs import dedupe, tools_hash
    raw, _ = (extract_js if eco == "npm" else extract_py).extract_dir(src)
    tools, _ = dedupe([t for t in raw if t.is_valid()])
    return {"hash": "sha256:" + tools_hash(tools) if tools else None,
            "names": sorted(t.name for t in tools)}


def analyse(data: Path, out: Path) -> None:
    from census import tarballs
    from census.versions import INSTALL_SCRIPTS

    rows = [json.loads(x) for x in gzip.open(data / "work" / "fetched.jsonl.gz", "rt", encoding="utf-8")]
    src_root = data / "work" / "src"
    for r in rows:
        eco = r["case"]["ecosystem"]
        r["tools"], r["dd_scripts"] = {}, None
        for role, a in r["archives"].items():
            if "path" not in a:
                continue
            p = Path(a["path"])
            dest = src_root / p.stem
            try:
                if a["kind"] == "datadog":
                    _, pj = _dd_source(p, dest)
                    if pj is not None:
                        s = pj.get("scripts") or {}
                        r["dd_scripts"] = {k: s[k] for k in INSTALL_SCRIPTS if k in s}
                        if pj.get("gypfile") and "install" not in s:
                            r["dd_scripts"]["install"] = "node-gyp rebuild (gypfile)"
                else:
                    tarballs.SRC = src_root
                    tarballs.extract(p, p.stem)
                r["tools"][role] = _tools_from_dir(eco, dest)
            except Exception as e:
                r["tools"][role] = {"error": f"{type(e).__name__}: {e}"}
    with gzip.open(data / "work" / "analysed.jsonl.gz", "wt", encoding="utf-8") as g:
        for r in rows:
            g.write(json.dumps(r) + "\n")
    print(f"analysed {len(rows)} cases")


# ------------------------------------------------------------------ assemble (--network none)
def _cmd(eco: str, name: str, form: str, pin: str | None) -> str:
    spec = name if pin is None else (f"{name}@{pin}" if eco == "npm" else f"{name}=={pin}")
    if form == "install":
        return f"npm install {spec}" if eco == "npm" else f"pip install {spec}"
    return f"npx -y {spec}" if eco == "npm" else f"uvx {spec}"


def _stub_record(eco: str, c: dict, scripts: dict | None) -> dict:
    return {"version": c["version"], "published": c["t"], "prerelease": "-" in str(c["version"]),
            "archive_url": None, "integrity": None, "shasum": None, "has_attestation": None,
            "attestation_url": None, "publisher": None, "maintainers": [],
            "install_scripts": scripts or {}, "filename": None, "sha256": None,
            "packagetype": None}


def assemble(data: Path, out: Path) -> None:
    from census import provenance
    from eval.corpora.benign import _lock_entry

    rows = [json.loads(x) for x in gzip.open(data / "work" / "analysed.jsonl.gz", "rt", encoding="utf-8")]
    bundles, excluded = [], []
    for r in rows:
        c, eco, name = r["case"], r["case"]["ecosystem"], r["case"]["name"]
        listed = r["target"] is not None
        tt = r["tools"].get("target") or {}
        target = r["target"] or _stub_record(eco, c, r["dd_scripts"])
        evaluable = {"S2": listed,
                     "S3": listed and (eco == "pypi" or bool(target.get("publisher"))),
                     "S4": listed or (eco == "npm" and r["dd_scripts"] is not None),
                     "S5": "hash" in tt}
        base = {"corpus": "R-M", "ecosystem": eco, "package": name, "t": c["t"], "osv": {},
                "registry_info": {name: {"exists": True, "first_release": r["first_release"]}},
                "identities": ({target["version"]: r["ids"].get(target["version"])}
                               if evaluable["S2"] else {}),
                "tools": {target["version"]: tt} if evaluable["S5"] else {},
                "evaluable": evaluable}
        labels = {"class": c["class"], "ids": c["ids"], "sources": c["sources"],
                  "registry_listed": listed, "archive": (r["archives"].get("target") or {}).get(
                      "kind"), "malicious": True}
        if c["class"] == "C":
            lock = r["lock"]
            if lock is None:
                excluded.append({"case": f"{eco}:{name}@{c['version']}", "reason": r["errors"]})
                continue
            lt = r["tools"].get("lock") or {}
            from gate import s1
            pin = None
            if target["prerelease"] or s1._vkey(eco, target["version"]) <= s1._vkey(eco, lock["version"]):
                pin = target["version"]  # an unpinned launch would not select it (docs/REPLAY.md)
            bundles.append({**base, "case_id": f"RM:C:{eco}:{name}@{c['version']}:launch",
                            "command": _cmd(eco, name, "launch", pin),
                            "versions": [lock, target],
                            "lock": _lock_entry(eco, name, lock, r["ids"].get(lock["version"]),
                                                lt if "hash" in lt else {}),
                            "labels": {**labels, "form": "launch", "primary": True, "pinned": bool(pin)}})
        else:
            for form, primary in (("install", True), ("launch", False)):
                bundles.append({**base, "case_id": f"RM:N:{eco}:{name}@{c['version']}:{form}",
                                "command": _cmd(eco, name, form, None),
                                "versions": [target], "lock": None,
                                "labels": {**labels, "form": form, "primary": primary}})
    with gzip.open(out / "bundles.jsonl.gz", "wt", encoding="utf-8") as g:
        for b in bundles:
            g.write(json.dumps(b) + "\n")
    (out / "assemble_excluded.json").write_text(json.dumps(excluded, indent=1), encoding="utf-8")
    ev = {s: sum(b["evaluable"][s] for b in bundles if b["labels"]["primary"]) for s in
          ("S2", "S3", "S4", "S5")}
    summary = {"bundles": len(bundles), "primary": sum(b["labels"]["primary"] for b in bundles),
               "excluded": len(excluded), "evaluable_primary": ev}
    (out / "assemble_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    provenance.write(out / "bundles.jsonl.gz", inputs=[out / "mal_sample.jsonl.gz"],
                     params={"seed": SEED, "osv_commit": OSV_COMMIT, "datadog_commit": DATADOG_COMMIT})
    print(json.dumps(summary))


def main():
    stages = {"scan": scan, "classify": classify, "sample": sample, "fetch": fetch,
              "analyse": analyse, "assemble": assemble}
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(stages))
    ap.add_argument("--data", type=Path, default=Path("/data"))
    ap.add_argument("--out", type=Path, default=Path("/out"))
    a = ap.parse_args()
    stages[a.stage](a.data, a.out)


if __name__ == "__main__":
    main()
