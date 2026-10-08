"""Phase 2 Part M: metadata census of every eligible package (docs/CENSUS_PLAN.md).

One transition = consecutive versions (version precedence) whose newer version was published
in the 12-month window. Signals: provenance lost/gained, publisher changed, maintainer set
changed, new install script (npm); provenance lost/gained (PyPI, via the PEP 740 JSON simple API).

Usage: python -m census.metacensus <eligible_downloads.jsonl>
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from census import http, provenance
from census import versions as V

WINDOW_START = datetime(2025, 10, 8, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 8, 23, 59, 59, tzinfo=UTC)
OUT = Path("results/census/metacensus")


def _ts(s):
    return V._ts(s)


def pypi_provenance(pkg: str) -> dict[str, bool]:
    """version -> any file of that version carries a PEP 740 provenance object."""
    doc = http.get_json(f"https://pypi.org/simple/{pkg}/",
                        headers={"Accept": "application/vnd.pypi.simple.v1+json"})
    out: dict[str, bool] = {}
    for f in doc.get("files", []):
        m = re.match(r"^[A-Za-z0-9_.]+?-(\d[^-]*?)(?:-|\.tar\.gz$|\.zip$)", f["filename"])
        if not m:
            continue
        ver = m.group(1)
        out[ver] = out.get(ver, False) or bool(f.get("provenance"))
    return out


def transitions_for(eco: str, pkg: str) -> tuple[list[dict], dict]:
    vs = V.npm_versions(pkg) if eco == "npm" else V.pypi_versions(pkg)
    prov = {}
    if eco == "pypi":
        try:
            prov = pypi_provenance(pkg)
        except http.HttpError:
            prov = {}
    out = []
    for i in range(1, len(vs)):
        a, b = vs[i - 1], vs[i]
        t = _ts(b["published"])
        if not t or not (WINDOW_START <= t <= WINDOW_END):
            continue
        if eco == "npm":
            pa, pb = a["has_attestation"], b["has_attestation"]
            rec = {
                "publisher_changed": bool(a["publisher"] and b["publisher"]
                                          and a["publisher"] != b["publisher"]),
                "maintainers_changed": set(a["maintainers"]) != set(b["maintainers"]),
                "new_install_script": sorted(set(b["install_scripts"]) - set(a["install_scripts"])),
                "has_install_script": sorted(b["install_scripts"]),
            }
        else:
            norm = lambda v: re.sub(r"[-_.]+", ".", v)  # noqa: E731
            pa = prov.get(a["version"], prov.get(norm(a["version"]), False))
            pb = prov.get(b["version"], prov.get(norm(b["version"]), False))
            rec = {"publisher_changed": None, "maintainers_changed": None,
                   "new_install_script": None, "has_install_script": None}
        out.append({"e": eco, "p": pkg, "from": a["version"], "to": b["version"],
                    "published": b["published"], "pre": bool(a["prerelease"] or b["prerelease"]),
                    "prov_from": bool(pa), "prov_to": bool(pb),
                    "provenance_lost": bool(pa and not pb), "provenance_gained": bool(pb and not pa),
                    **rec})
    info = {"e": eco, "p": pkg, "n_versions": len(vs), "n_window_transitions": len(out),
            "latest_has_provenance": (vs[-1].get("has_attestation") if eco == "npm"
                                      else prov.get(vs[-1]["version"], False)) if vs else None}
    return out, info


def run(path: str) -> Path:
    rows = [json.loads(x) for x in open(path, encoding="utf-8")]

    def work(r):
        try:
            return transitions_for(r["ecosystem"], r["package"])
        except http.HttpError as e:
            return [], {"e": r["ecosystem"], "p": r["package"], "error": e.status}
        except Exception as e:  # noqa: BLE001 - one bad document must not stop the census
            return [], {"e": r["ecosystem"], "p": r["package"], "error": repr(e)[:200]}

    OUT.mkdir(parents=True, exist_ok=True)
    trans_path = OUT / "transitions.jsonl.gz"
    pkg_path = OUT / "packages.jsonl.gz"
    n_t = 0
    errors = 0
    with ThreadPoolExecutor(8) as ex, gzip.open(trans_path, "wt", encoding="utf-8") as ft, \
            gzip.open(pkg_path, "wt", encoding="utf-8") as fp:
        for k, (trs, info) in enumerate(ex.map(work, rows)):
            for t in trs:
                ft.write(json.dumps(t, sort_keys=True) + "\n")
            n_t += len(trs)
            errors += "error" in info
            fp.write(json.dumps(info, sort_keys=True) + "\n")
            if k % 1000 == 0:
                print(f"{k}/{len(rows)} packages, {n_t} transitions, {errors} errors", flush=True)
    provenance.write(trans_path, inputs=[Path(path)],
                     params={"window": [WINDOW_START.isoformat(), WINDOW_END.isoformat()],
                             "packages": len(rows), "transitions": n_t, "errors": errors})
    provenance.write(pkg_path, inputs=[Path(path)])
    print(f"metacensus: {len(rows)} packages, {n_t} transitions, {errors} errors")
    return trans_path


def summarize() -> dict:
    from census.stats import wilson

    trs = [json.loads(x) for x in gzip.open(OUT / "transitions.jsonl.gz", "rt", encoding="utf-8")]
    pk = [json.loads(x) for x in gzip.open(OUT / "packages.jsonl.gz", "rt", encoding="utf-8")]
    res: dict = {"packages": len(pk), "package_errors": sum("error" in p for p in pk),
                 "transitions": len(trs)}
    signals = ["provenance_lost", "provenance_gained", "publisher_changed", "maintainers_changed",
               "new_install_script"]
    for eco in ("npm", "pypi"):
        t = [x for x in trs if x["e"] == eco]
        p_ok = [p for p in pk if p["e"] == eco and "error" not in p]
        d = {"packages": len(p_ok), "transitions": len(t),
             "packages_with_window_transition": sum(p["n_window_transitions"] > 0 for p in p_ok),
             "latest_with_provenance": [sum(bool(p["latest_has_provenance"]) for p in p_ok),
                                        len(p_ok)]}
        d["latest_with_provenance"].append(wilson(*d["latest_with_provenance"]))
        for s in signals:
            vals = [x[s] for x in t if x[s] is not None]
            if not vals:
                continue
            k = sum(bool(v) for v in vals)
            pkgs_hit = len({x["p"] for x in t if x[s]})
            active = d["packages_with_window_transition"]
            d[s] = {"transitions": [k, len(vals), wilson(k, len(vals))],
                    "packages": [pkgs_hit, active, wilson(pkgs_hit, active)]}
        res[eco] = d
    res["new_install_script_kinds"] = dict(Counter(s for x in trs if x["e"] == "npm"
                                                   for s in (x["new_install_script"] or [])))
    dest = OUT / "summary.json"
    dest.write_text(json.dumps(res, indent=2))
    provenance.write(dest, inputs=[OUT / "transitions.jsonl.gz", OUT / "packages.jsonl.gz"])
    print(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    if sys.argv[1] == "summarize":
        summarize()
    else:
        run(sys.argv[1])
