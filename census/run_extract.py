"""Fetch, verify, extract and statically analyse every selected version.

Usage: python -m census.run_extract <versions.jsonl>
Writes extractions.jsonl (one row per version) and suspicious.jsonl (manual-review queue).
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

from census import extract_js, extract_py, provenance, tarballs
from census.tooldefs import dedupe, tools_hash

# Heuristic patterns for the "stop and report" rule (tool-poisoning / exfiltration text).
SUSPICIOUS = re.compile(
    r"ignore (all |any )?(previous|prior) instructions|<important>|do not (tell|inform|mention)"
    r" (to )?the user|don't tell the user|without (telling|informing) the user|\.ssh/|id_rsa|"
    r"\.aws/credentials|exfiltrat|send (it|them|the contents) to http|base64[- ]encode.{0,40}(key|token)"
    r"|<(system|instructions?)>|before using this tool,? (you must )?read",
    re.I)


def _key(eco: str, pkg: str, v: dict) -> str:
    safe = pkg.replace("/", "__")
    if eco == "npm":
        return f"npm/{safe}/{v['version']}.tgz"
    return f"pypi/{safe}/{v['version']}/{v['filename']}"


def fetch_one(args) -> dict:
    eco, pkg, v = args
    key = _key(eco, pkg, v)
    try:
        if eco == "npm":
            path, integ = tarballs.fetch(v["archive_url"], key, integrity=v.get("integrity"),
                                         shasum=v.get("shasum"))
        else:
            path, integ = tarballs.fetch(v["archive_url"], key, sha256=v.get("sha256"))
        return {"ok": True, "path": str(path), "key": key, "integrity": integ}
    except tarballs.IntegrityError as e:
        return {"ok": False, "status": "integrity_error", "error": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "status": "fetch_error", "error": repr(e)[:300]}


def extract_one(args) -> dict:
    eco, pkg, version, fetched = args
    base = {"ecosystem": eco, "package": pkg, "version": version}
    if not fetched["ok"]:
        return {**base, "status": fetched["status"], "error": fetched["error"], "n_tools": 0}
    try:
        key = fetched["key"]
        src = tarballs.extract(Path(fetched["path"]), key.rsplit(".tgz", 1)[0])
        ex = extract_js if eco == "npm" else extract_py
        raw, info = ex.extract_dir(src)
        valid = [t for t in raw if t.is_valid()]
        tools, conflicts = dedupe(valid)
        tools.sort(key=lambda t: t.name)
        text = " ".join(f"{t.name} {t.description or ''}" for t in tools)
        hits = sorted({m.group(0).lower() for m in SUSPICIOUS.finditer(text)})
        return {**base, "status": "ok", "integrity": fetched["integrity"],
                "n_tools": len(tools), "n_raw_candidates": len(raw), "dup_conflicts": conflicts,
                "kinds": sorted({t.kind for t in tools}),
                "tools": [t.canonical() for t in tools],
                "tools_hash": tools_hash(tools) if tools else None,
                "info": info, "suspicious": hits}
    except Exception:  # noqa: BLE001
        return {**base, "status": "extract_error", "error": traceback.format_exc()[-500:],
                "n_tools": 0}


def run(versions_path: str) -> Path:
    rows = [json.loads(x) for x in open(versions_path, encoding="utf-8")]
    jobs = [(r["ecosystem"], r["package"], v) for r in rows for v in r["versions"]]
    with ThreadPoolExecutor(6) as tex:
        fetched = list(tex.map(fetch_one, jobs))
    with ProcessPoolExecutor(6) as pex:
        results = list(pex.map(extract_one, [(e, p, v["version"], f) for (e, p, v), f
                                             in zip(jobs, fetched, strict=True)], chunksize=4))
    out = Path(versions_path).with_name("extractions.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    sus = [r for r in results if r.get("suspicious")]
    with open(out.with_name("suspicious.jsonl"), "w", encoding="utf-8") as f:
        for r in sus:
            f.write(json.dumps({k: r[k] for k in ("ecosystem", "package", "version", "suspicious")})
                    + "\n")
    from collections import Counter
    c = Counter(r["status"] for r in results)
    provenance.write(out, inputs=[Path(versions_path)],
                     params={"status_counts": dict(c), "suspicious_versions": len(sus)})
    print(f"extract: {dict(c)}; suspicious versions: {len(sus)} -> {out}")
    return out


if __name__ == "__main__":
    run(sys.argv[1])
