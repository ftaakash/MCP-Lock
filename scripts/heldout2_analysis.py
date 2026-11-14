"""Analysis of the heldout2 extractor validation, as fixed in docs/EXTRACTOR_V3_VALIDATION_PLAN.md.

Usage:
    .venv/Scripts/python.exe scripts/heldout2_analysis.py . <scratch-dir> <v2-worktree>

<v2-worktree> is a checkout of tag extract-v2.1 (git worktree add <dir> extract-v2.1).
Archives of every validated server are fetched with digest checks into <scratch-dir> and never executed.
v3 static names come from the run records (extractor at tag extract-v3). v2 static names are computed here on the
same archives, in a subprocess that imports the v2 extractor from the worktree.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

repo, scratch, v2tree = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve()
sys.path.insert(0, str(repo))
from census import extract_js, extract_py, tarballs  # noqa: E402  (v3, for the sanity check)
from census.stats import wilson  # noqa: E402
from census.tooldefs import dedupe  # noqa: E402

tarballs.TARBALLS, tarballs.SRC = scratch / "tarballs", scratch / "src"
BOOT, BOOT_SEED = 10_000, 20261114
P2 = repo / "results/census/phase2"
PREFIX = sys.argv[4] if len(sys.argv) > 4 else "validation_heldout2_"  # dry run: validation_heldout_

V2_SCRIPT = r"""
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from census import extract_js, extract_py
from census.tooldefs import dedupe
out = {}
for line in sys.stdin:
    eco, src = json.loads(line)
    ex = extract_js if eco == "npm" else extract_py
    raw, _ = ex.extract_dir(Path(src))
    tools, _ = dedupe([t for t in raw if t.is_valid()])
    out[src] = sorted({t.name for t in tools})
print(json.dumps(out))
"""


def source_dir(eco, pkg, ver):
    safe = pkg.replace("/", "__")
    if eco == "npm":
        m = tarballs.http.get_json(f"https://registry.npmjs.org/{pkg.replace('/', '%2F')}/{ver}")
        arch, _ = tarballs.fetch(m["dist"]["tarball"], f"npm/{safe}/{ver}.tgz",
                                 integrity=m["dist"].get("integrity"))
        return tarballs.extract(arch, f"npm/{safe}/{ver}")
    fs = tarballs.http.get_json(f"https://pypi.org/pypi/{pkg}/{ver}/json")["urls"]
    preds = (lambda f: f["filename"].endswith("-none-any.whl"), lambda f: f["packagetype"] == "sdist",
             lambda f: f["packagetype"] == "bdist_wheel")
    f = next(f for p in preds for f in sorted(fs, key=lambda f: f["filename"]) if p(f))
    arch, _ = tarballs.fetch(f["url"], f"pypi/{safe}/{ver}/{f['filename']}", sha256=f["digests"]["sha256"])
    return tarballs.extract(arch, f"pypi/{safe}/{ver}/{f['filename']}")


def v3_names(eco, src):
    ex = extract_js if eco == "npm" else extract_py
    raw, _ = ex.extract_dir(src)
    tools, _ = dedupe([t for t in raw if t.is_valid()])
    return sorted({t.name for t in tools})


def micro(rows, key):
    both = sum(r[key]["both"] for r in rows)
    dyn = sum(r["n_dynamic"] for r in rows)
    st = sum(r[key]["static"] for r in rows)
    return (both / dyn if dyn else None, both / st if st else None)


def boot(rows, fn, rng):
    idx = np.arange(len(rows))
    vals = []
    for _ in range(BOOT):
        s = [rows[i] for i in rng.choice(idx, len(idx))]
        v = fn(s)
        if v is not None:
            vals.append(v)
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


recs = []
for eco in ("npm", "pypi"):
    f = P2 / f"{PREFIX}{eco}.jsonl"
    recs += [json.loads(x) for x in open(f, encoding="utf-8")]
ok = [r for r in recs if r.get("stage_b_ok")]

rows, v2_jobs, mismatch = [], [], []
for r in ok:
    eco, pkg, ver = r["ecosystem"], r["package"], r["version"]
    dyn = {t["name"] for t in r["dynamic_tools"]}
    src = source_dir(eco, pkg, ver)
    v3_local = set(v3_names(eco, src))
    c = r["compare"]
    if len(v3_local) != c["n_static"] or len(v3_local & dyn) != c["n_both"]:
        mismatch.append(pkg)  # run record and local recompute disagree: reported, record wins
    rows.append({"ecosystem": eco, "package": pkg, "version": ver, "src": str(src), "dyn": sorted(dyn),
                 "n_dynamic": c["n_dynamic"], "v3": {"static": c["n_static"], "both": c["n_both"]},
                 "v3_missed": sorted(dyn - v3_local)})
    v2_jobs.append(json.dumps([eco, str(src)]))

proc = subprocess.run([sys.executable, "-I", "-c", V2_SCRIPT, str(v2tree)], input="\n".join(v2_jobs),
                      capture_output=True, text=True, check=True)
v2 = json.loads(proc.stdout)
for row in rows:
    names = set(v2[row["src"]])
    row["v2"] = {"static": len(names), "both": len(names & set(row["dyn"]))}

rng = np.random.default_rng(BOOT_SEED)
rec3, prec3 = micro(rows, "v3")
rec2, prec2 = micro(rows, "v2")
out = {
    "plan": "docs/EXTRACTOR_V3_VALIDATION_PLAN.md",
    "status": "EXPLORATORY; fresh servers not used to build v3",
    "attempted": len([r for r in recs if not r.get("skipped")]), "validated": len(ok),
    "validated_by_eco": {e: sum(r["ecosystem"] == e for r in ok) for e in ("npm", "pypi")},
    "runtime_tools": sum(r["n_dynamic"] for r in rows),
    "v3": {"recall_micro": rec3, "recall_ci": boot(rows, lambda s: micro(s, "v3")[0], rng),
           "precision_micro": prec3, "precision_ci": boot(rows, lambda s: micro(s, "v3")[1], rng)},
    "v2": {"recall_micro": rec2, "recall_ci": boot(rows, lambda s: micro(s, "v2")[0], rng),
           "precision_micro": prec2, "precision_ci": boot(rows, lambda s: micro(s, "v2")[1], rng)},
    "v3_minus_v2_recall": {"diff": rec3 - rec2, "paired_ci": boot(
        rows, lambda s: (lambda a, b: None if a is None or b is None else a - b)(micro(s, "v3")[0],
                                                                                micro(s, "v2")[0]), rng)},
    "v3_name_set_equal": (lambda k: [k, len(rows), wilson(k, len(rows))])(
        sum(r["v3"]["both"] == r["n_dynamic"] == r["v3"]["static"] for r in rows)),
    "servers_changed_v2_to_v3": [r["package"] for r in rows if r["v2"] != r["v3"]],
    "servers_with_v3_misses": [{"package": r["package"], "missed": len(r["v3_missed"]),
                                "of": r["n_dynamic"]} for r in rows if r["v3_missed"]],
    "record_vs_local_v3_mismatch": mismatch,
}
for r in rows:
    r.pop("src")
(P2 / ("extractor_v3_heldout2.json" if PREFIX == "validation_heldout2_" else "_dryrun.json")).write_text(json.dumps({"summary": out, "servers": rows}, indent=1))
print(json.dumps(out, indent=1))
