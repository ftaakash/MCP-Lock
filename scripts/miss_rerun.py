"""Re-run the frozen static extractor on every held-out validation server whose static and runtime
tool lists differ, and record where each missed tool name appears in the source.

Usage: .venv/Scripts/python.exe scripts/miss_rerun.py . <scratch-dir> [--all]
--all re-runs every validated server (to check that a change adds no wrong tools).
Archives are downloaded with digest checks into <scratch-dir> (never the repo) and never executed.
See docs/EXTRACTOR_MISS_ANALYSIS.md.
"""
import json, sys, re, urllib.request
from pathlib import Path
repo, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo))
from census import tarballs, extract_js, extract_py
tarballs.TARBALLS = out / "tarballs"; tarballs.SRC = out / "src"
def get(u): return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-client"}), timeout=60))
res = []
for eco in ["npm", "pypi"]:
    for l in open(repo / f"results/census/phase2/validation_heldout_{eco}.jsonl", encoding="utf-8"):
        r = json.loads(l)
        if not r.get("stage_b_ok"): continue
        c = r["compare"]
        if "--all" not in sys.argv and c["n_dynamic"] == c["n_both"] and not c["static_only"]: continue
        pkg, ver = r["package"], r["version"]; safe = pkg.replace("/", "__")
        if eco == "npm":
            m = get(f"https://registry.npmjs.org/{pkg.replace('/', '%2F')}/{ver}")
            arch, _ = tarballs.fetch(m["dist"]["tarball"], f"npm/{safe}/{ver}.tgz", integrity=m["dist"].get("integrity"))
            src = tarballs.extract(arch, f"npm/{safe}/{ver}")
        else:
            fs = get(f"https://pypi.org/pypi/{pkg}/{ver}/json")["urls"]
            f = next((f for p in (lambda f: f["filename"].endswith("-none-any.whl"), lambda f: f["packagetype"] == "sdist", lambda f: True) for f in sorted(fs, key=lambda f: f["filename"]) if p(f)))
            arch, _ = tarballs.fetch(f["url"], f"pypi/{safe}/{ver}/{f['filename']}", sha256=f["digests"]["sha256"])
            src = tarballs.extract(arch, f"pypi/{safe}/{ver}/{f['filename']}")
        ex = extract_js if eco == "npm" else extract_py
        tools, info = ex.extract_dir(src)
        names = {t.name for t in tools if t.is_valid()}
        dyn = [t["name"] for t in r["dynamic_tools"]]
        missed = [n for n in dyn if n not in names]
        # where does each missed name appear in the source?
        hits = {}
        files = [p for p in src.rglob("*") if p.is_file() and p.suffix in (".js", ".mjs", ".cjs", ".ts", ".py", ".json")]
        for n in missed[:5]:
            hits[n] = [str(p.relative_to(src)) for p in files if n in p.read_text("utf-8", "replace")][:4]
        res.append({"eco": eco, "pkg": pkg, "ver": ver, "n_dyn": len(dyn), "n_static_now": len(names),
                    "n_missed_now": len(missed), "static_only": sorted(names - set(dyn))[:10],
                    "n_files": len(files), "files": [str(p.relative_to(src)) for p in files][:15], "where": hits, "info": info})
        print(pkg, len(dyn), len(names), len(missed), flush=True)
json.dump(res, open(out / ("all.json" if "--all" in sys.argv else "miss.json"), "w"), indent=1)
