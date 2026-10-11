"""Benign-upgrade corpus B (PREREG §3.4): select transitions, then freeze one replay bundle each.

Strata
  mcp       every Phase 2 window transition whose two versions both have statically extracted
            tools (the 6,695 transitions of rq1.json), lock = older version
  npm-top   top-1,000 npm (npm-high-impact 1.13.0), latest consecutive stable pair whose newer
            version was published on or before 2026-10-08
  pypi-top  top-500 PyPI (hugovk snapshot 2026-10-01), same rule

Replay semantics (docs/REPLAY.md): the case is the transition a -> b replayed as of b's publish
time t. The bundle holds the two version records [a, b], so the gate resolves b; a pre-release b
is launched pinned (`pkg@b` / `pkg==b`) because an unpinned launch never selects a pre-release.

Usage:
  python -m eval.corpora.benign select  results/candidate/phase4/benign
  python -m eval.corpora.benign bundle  results/candidate/phase4/benign [--workers 8]
"""

from __future__ import annotations

import argparse
import gzip
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from census import http, launch, provenance, tarballs
from census import versions as V
from census.analyze import pairs_for
from gate import s1, signals
from lockfile import identity

ROOT = Path(__file__).resolve().parents[2]
PHASE2 = ROOT / "results/census/phase2"
CUTOFF = datetime(2026, 10, 8, 23, 59, 59, tzinfo=UTC)
N_NPM, N_PYPI = 1000, 500
MAX_BYTES = 5 * 1024 ** 3  # PREREG §7: stop and ask above 5 GB of downloads



def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC) if s else None


# ------------------------------------------------------------------ stage 0: select
def select_mcp() -> list[dict]:
    versions = [json.loads(x) for x in open(PHASE2 / "versions.jsonl", encoding="utf-8")]
    ex = {(r["ecosystem"], r["package"], r["version"]): r
          for r in map(json.loads, provenance.open_text(PHASE2 / "extractions.jsonl"))}
    out = []
    for r in versions:
        for a, b in pairs_for(r, ex):
            ea = ex[(r["ecosystem"], r["package"], a["version"])]
            eb = ex[(r["ecosystem"], r["package"], b["version"])]
            if ea["n_tools"] == 0 or eb["n_tools"] == 0:
                continue  # identical filter to census/rq1.py
            out.append({"stratum": "mcp", "ecosystem": r["ecosystem"], "package": r["package"],
                        "a": a, "b": b, "tools_a": _tools(ea), "tools_b": _tools(eb)})
    return out


def _tools(e: dict) -> dict:
    h = e.get("tools_hash")
    return {"hash": f"sha256:{h}" if h else None, "names": sorted(t["name"] for t in e["tools"])}


def select_top(eco: str, n: int) -> tuple[list[dict], list[dict]]:
    names = json.load(open(ROOT / f"gate/data/top_{eco}.json", encoding="utf-8"))["names"][:n]
    out, excluded = [], []
    for name in names:
        try:
            vs = V.npm_versions(name) if eco == "npm" else V.pypi_versions(name)
        except http.HttpError as e:
            excluded.append({"package": name, "reason": f"unresolvable (HTTP {e.status})"})
            continue
        stable = [v for v in vs if not v["prerelease"] and v.get("published")
                  and _ts(v["published"]) <= CUTOFF]
        if len(stable) < 2:
            excluded.append({"package": name, "reason": "fewer than 2 stable versions"})
            continue
        out.append({"stratum": f"{eco}-top", "ecosystem": eco, "package": name,
                    "a": stable[-2], "b": stable[-1]})
    return out, excluded


# ------------------------------------------------------------------ stage 1: bundle
def _identity(eco: str, pkg: str, v: dict):
    if eco == "npm":
        return identity.npm_identity(v.get("attestation_url"))
    return identity.pypi_identity(pkg, v["version"], v["filename"])


def _static_tools(eco: str, pkg: str, v: dict) -> dict:
    """Same code path as the gate (signals.static_tools)."""
    try:
        h, names = signals.static_tools(eco, pkg, v)
    except tarballs.TooLarge:
        return {"too_large": True}
    except tarballs.IntegrityError:
        return {"integrity_error": True}
    return {"hash": h, "names": names}


def _first_release(eco: str, pkg: str, t: datetime) -> str | None:
    vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
    times = [_ts(v["published"]) for v in vs if v.get("published")]
    times = [x for x in times if x <= t]
    return min(times).isoformat() if times else None


def osv_asof(eco: str, name: str, version: str, t: datetime) -> list[dict]:
    """s1.osv_fixable restricted to advisories published at or before t (no lookahead)."""
    osv_eco = "PyPI" if eco == "pypi" else "npm"
    res = http.post_json("https://api.osv.dev/v1/query",
                         {"package": {"name": name, "ecosystem": osv_eco}, "version": version})
    out = []
    for vuln in res.get("vulns", []):
        if not vuln.get("published") or _ts(vuln["published"]) > t:
            continue
        fixes = [ev["fixed"] for aff in vuln.get("affected", [])
                 if aff.get("package", {}).get("ecosystem") == osv_eco
                 for rng in aff.get("ranges", []) for ev in rng.get("events", [])
                 if "fixed" in ev and s1._vkey(eco, ev["fixed"]) > s1._vkey(eco, version)]
        if fixes:
            out.append({"id": vuln["id"], "lowest_fix": min(fixes, key=lambda f: s1._vkey(eco, f))})
    return out


def _lock_entry(eco: str, pkg: str, a: dict, ident_a, tools_a: dict) -> dict:
    tools = ({"hash": tools_a["hash"], "method": "static", "names": tools_a["names"]}
             if "hash" in tools_a else {"hash": None, "method": "unavailable", "names": []})
    entry = {"ecosystem": eco, "name": pkg, "version": a["version"],
             "launch": {"runner": "npx" if eco == "npm" else "uvx", "args": ["-y", pkg]
                        if eco == "npm" else [pkg]},
             "integrity": signals._integrity(eco, a),
             "archive": a["archive_url"] if eco == "npm" else a["filename"],
             "provenance": ident_a, "tools": tools}
    if eco == "npm":
        entry["publisher"] = {"publisher": a.get("publisher"), "maintainers": a.get("maintainers")}
        entry["installScripts"] = sorted(a.get("install_scripts") or {})
    return entry


def build_bundle(tr: dict) -> dict:
    eco, pkg, a, b = tr["ecosystem"], tr["package"], tr["a"], tr["b"]
    t = _ts(b["published"])
    pinned = bool(b["prerelease"])
    spec = (f"{pkg}@{b['version']}" if eco == "npm" else f"{pkg}=={b['version']}") if pinned \
        else pkg
    command = f"npx -y {spec}" if eco == "npm" else f"uvx {spec}"
    evaluable = {"S2": True, "S3": True, "S4": True, "S5": True}
    failures = []
    ids = {}
    for v in (a, b):
        try:
            ids[v["version"]] = _identity(eco, pkg, v)
        except http.HttpError as e:
            failures.append(f"identity {v['version']}: HTTP {e.status}")
            evaluable["S2"] = False
    tools_a = tr.get("tools_a") or _static_tools(eco, pkg, a)
    tools_b = tr.get("tools_b") or _static_tools(eco, pkg, b)
    osv = {}
    if pinned:
        name = launch.pep503(pkg) if eco == "pypi" else pkg
        osv[f"{name}@{b['version']}"] = osv_asof(eco, pkg, b["version"], t)
    keep = ("version", "published", "prerelease", "archive_url", "integrity", "shasum",
            "has_attestation", "attestation_url", "publisher", "maintainers", "install_scripts",
            "filename", "sha256", "packagetype")
    recs = [{k: v[k] for k in keep if k in v} for v in (a, b)]
    return {
        "case_id": f"B:{tr['stratum']}:{eco}:{pkg}:{a['version']}->{b['version']}",
        "corpus": "B", "ecosystem": eco, "package": pkg, "t": t.isoformat(), "command": command,
        "versions": recs,
        "lock": _lock_entry(eco, pkg, a, ids.get(a["version"]), tools_a),
        "registry_info": {pkg: {"exists": True, "first_release": _first_release(eco, pkg, t)}},
        "osv": osv,
        "identities": {b["version"]: ids.get(b["version"])} if evaluable["S2"] else {},
        "tools": {b["version"]: tools_b},
        "evaluable": evaluable,
        "labels": {"stratum": tr["stratum"], "from": a["version"], "to": b["version"],
                   "prerelease": pinned, "lock_tools": "hash" in tools_a,
                   "lookup_failures": failures},
    }


def _write_jsonl_gz(path: Path, rows) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def cmd_select(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    mcp = select_mcp()
    npm, ex_npm = select_top("npm", N_NPM)
    pypi, ex_pypi = select_top("pypi", N_PYPI)
    rows = mcp + npm + pypi
    _write_jsonl_gz(out / "transitions.jsonl.gz", rows)
    (out / "excluded.json").write_text(json.dumps({"npm-top": ex_npm, "pypi-top": ex_pypi},
                                                  indent=1), encoding="utf-8")
    counts = {"mcp": len(mcp), "npm-top": len(npm), "pypi-top": len(pypi),
              "excluded": {"npm-top": len(ex_npm), "pypi-top": len(ex_pypi)}}
    (out / "select_summary.json").write_text(json.dumps(counts, indent=1), encoding="utf-8")
    provenance.write(out / "transitions.jsonl.gz",
                     inputs=[PHASE2 / "versions.jsonl", PHASE2 / "extractions.jsonl",
                             ROOT / "gate/data/top_npm.json", ROOT / "gate/data/top_pypi.json"],
                     params={"cutoff": CUTOFF.isoformat(), "n_npm": N_NPM, "n_pypi": N_PYPI})
    print(json.dumps(counts))


def cmd_bundle(out: Path, workers: int) -> None:
    trs = [json.loads(x) for x in gzip.open(out / "transitions.jsonl.gz", "rt", encoding="utf-8")]
    part = out / "bundles.part.jsonl"
    done = set()
    if part.exists():
        done = {json.loads(x)["case_id"] for x in open(part, encoding="utf-8")}
    todo = [tr for tr in trs if f"B:{tr['stratum']}:{tr['ecosystem']}:{tr['package']}:"
            f"{tr['a']['version']}->{tr['b']['version']}" not in done]
    print(f"{len(done)} done, {len(todo)} to build")
    errors = []
    with open(part, "a", encoding="utf-8") as f, ThreadPoolExecutor(workers) as pool:
        futs = {pool.submit(build_bundle, tr): tr for tr in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            tr = futs[fut]
            try:
                f.write(json.dumps(fut.result()) + "\n")
                f.flush()
            except Exception as e:  # recorded, never silently dropped
                errors.append({"package": tr["package"], "stratum": tr["stratum"],
                               "error": f"{type(e).__name__}: {e}"})
            if i % 200 == 0:
                size = sum(p.stat().st_size for p in tarballs.TARBALLS.rglob("*") if p.is_file())
                print(f"{i}/{len(todo)} built, {len(errors)} errors, tarball cache "
                      f"{size / 1024 ** 3:.2f} GB", flush=True)
                if size > MAX_BYTES:
                    pool.shutdown(cancel_futures=True)
                    raise SystemExit("tarball cache above 5 GB: stopping to ask (PREREG §7)")
    (out / "bundle_errors.json").write_text(json.dumps(errors, indent=1), encoding="utf-8")
    rows = [json.loads(x) for x in open(part, encoding="utf-8")]
    rows.sort(key=lambda r: r["case_id"])
    _write_jsonl_gz(out / "bundles.jsonl.gz", rows)
    provenance.write(out / "bundles.jsonl.gz", inputs=[out / "transitions.jsonl.gz"],
                     params={"bundles": len(rows), "errors": len(errors)})
    print(f"{len(rows)} bundles, {len(errors)} errors")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["select", "bundle"])
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    cmd_select(a.out) if a.stage == "select" else cmd_bundle(a.out, a.workers)


if __name__ == "__main__":
    main()
