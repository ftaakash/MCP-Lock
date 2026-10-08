"""Dynamic ground truth for the static extractor (plan §6), harness v2.

Stage A (network on, NO package code runs):
    npm:  npm install --ignore-scripts --before=<release+2d> <pkg>@<ver>      (node:22-slim)
    pypi: uv pip install --only-binary :all: --exclude-newer <release+2d>      (python:3.1x-slim,
          image chosen from the version's Requires-Python; wheels never run code)
    Dependencies are resolved as of the release date, so a server is tested against the
    dependency set it shipped with (not, e.g., a later breaking SDK major).
Env scan (network off): our own script lists environment-variable names the package reads.
Stage B (package code runs, network off):
    docker run --network none --read-only --cap-drop ALL --security-opt no-new-privileges
    --user 65534 --memory 1g --pids-limit 256, disposable writable /work volume, tmpfs /tmp;
    MCP initialize + tools/list over stdio, then kill. No tool is ever called.
    If the server does not answer initialize, retry with --stdio / stdio / --transport stdio.

Usage:
    python -m census.dynamic run <pilot_dir> --eco npm|pypi [--target 40] [--max-attempts 160]
    python -m census.dynamic summarize <pilot_dir>
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
from packaging.specifiers import InvalidSpecifier, SpecifierSet

from census import http, provenance
from census.tooldefs import norm_ws

SEED = 20261008
NODE_IMG = "node:22-slim"
PY_IMGS = {"3.12": "python:3.12-slim", "3.13": "python:3.13-slim", "3.11": "python:3.11-slim"}
PY_PREFERENCE = ["3.12", "3.13", "3.11"]
SCAN_IMG = "python:3.12-slim"
FIRST_TIMEOUT = 60
RETRY_TIMEOUT = 25
ARG_FALLBACKS = [["--stdio"], ["stdio"], ["--transport", "stdio"]]
HARDEN = ["--network", "none", "--read-only", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges", "--user", "65534:65534",
          "--memory", "1g", "--pids-limit", "256", "--tmpfs", "/tmp:rw,size=256m,mode=1777",
          "-e", "HOME=/tmp"]
# Variables never set by the harness: they switch transport/behaviour rather than configure.
ENV_SKIP = re.compile(r"^(PORT|HOST|HOME|PATH|PWD|SHELL|USER|TERM|LANG|TZ|NODE_ENV|DEBUG|CI|"
                      r"NODE_OPTIONS|PYTHON\w*|VIRTUAL_ENV|TMPDIR|TEMP|TMP)$|PORT$|TRANSPORT|"
                      r"^MCP_MODE$|^MODE$|LOG|PROXY|^HTTP|^NO_COLOR|^FORCE_COLOR|^XDG_")


def _run(cmd, timeout=900):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _cutoff(published: str | None) -> str | None:
    if not published:
        return None
    t = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(UTC)
    return (t + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _py_images(requires_python: str | None) -> list[str]:
    if not requires_python:
        return PY_PREFERENCE
    try:
        spec = SpecifierSet(requires_python)
    except InvalidSpecifier:
        return PY_PREFERENCE
    ok = [v for v in PY_PREFERENCE if spec.contains(v + ".0", prereleases=True)]
    return ok or ["3.13"]


# ------------------------------------------------------------------ stage A
def stage_a(eco: str, pkg: str, ver: str, vol: str, cutoff: str | None,
            requires_python: str | None) -> dict:
    tries = []
    if eco == "npm":
        variants = ([f"--before={cutoff}"] if cutoff else []) + [""]
        for before in variants:
            _run(["docker", "volume", "rm", "-f", vol])
            _run(["docker", "volume", "create", vol])
            cmd = ["docker", "run", "--rm", "-v", f"{vol}:/work", "-w", "/work", NODE_IMG, "sh",
                   "-c", f"npm init -y >/dev/null && npm install --ignore-scripts --no-audit "
                         f"--no-fund {before} '{pkg}@{ver}' && chown -R 65534:65534 /work"]
            r = _safe_run(cmd)
            tries.append({"image": NODE_IMG, "dep_snapshot": bool(before), "ok": r[0]})
            if r[0]:
                return {"ok": True, "image": NODE_IMG, "dep_snapshot": bool(before), "tries": tries}
        return {"ok": False, "tries": tries, "log": r[1]}
    for pyv in _py_images(requires_python):
        img = PY_IMGS[pyv]
        for snap in ([True, False] if cutoff else [False]):
            _run(["docker", "volume", "rm", "-f", vol])
            _run(["docker", "volume", "create", vol])
            excl = f"--exclude-newer {cutoff}" if snap else ""
            cmd = ["docker", "run", "--rm", "-v", f"{vol}:/work", img, "sh", "-c",
                   "pip install -q --disable-pip-version-check uv && "
                   f"uv pip install --quiet --python /usr/local/bin/python --target /work "
                   f"--only-binary :all: {excl} '{pkg}=={ver}' && chown -R 65534:65534 /work"]
            r = _safe_run(cmd)
            tries.append({"image": img, "dep_snapshot": snap, "ok": r[0]})
            if r[0]:
                return {"ok": True, "image": img, "dep_snapshot": snap, "tries": tries}
    return {"ok": False, "tries": tries, "log": r[1]}


def _safe_run(cmd) -> tuple[bool, str]:
    try:
        r = _run(cmd, timeout=900)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    return r.returncode == 0, (r.stderr or r.stdout)[-500:]


# ------------------------------------------------------------------ env scan
SCAN = r"""
import os, re, sys, glob
eco, pkg = sys.argv[1], sys.argv[2]
files = []
if eco == "npm":
    root = os.path.join("/work/node_modules", pkg)
    for d, _, fs in os.walk(root):
        if "node_modules" in d[len(root):]:
            continue
        files += [os.path.join(d, f) for f in fs if f.endswith((".js", ".mjs", ".cjs"))]
else:
    norm = re.sub(r"[-_.]+", "_", pkg).lower()
    for rec in glob.glob("/work/*.dist-info/RECORD"):
        if os.path.basename(os.path.dirname(rec)).split("-")[0].lower().replace(".", "_") == norm:
            for line in open(rec, encoding="utf-8", errors="ignore"):
                p = line.split(",")[0]
                if p.endswith(".py"):
                    files.append(os.path.join("/work", p))
pat = re.compile(r"process\.env\.([A-Z][A-Z0-9_]{2,})|process\.env\[['\"]([A-Z][A-Z0-9_]{2,})|"
                 r"environ(?:\.get)?\(?\s*\[?\s*['\"]([A-Z][A-Z0-9_]{2,})|getenv\(\s*['\"]([A-Z][A-Z0-9_]{2,})")
names = set()
for f in files[:3000]:
    try:
        txt = open(f, encoding="utf-8", errors="ignore").read()
    except OSError:
        continue
    for m in pat.finditer(txt):
        names.add(next(g for g in m.groups() if g))
print("\n".join(sorted(names)))
"""


def env_scan(eco: str, pkg: str, vol: str) -> list[str]:
    cmd = ["docker", "run", "--rm", "--network", "none", "-v", f"{vol}:/work:ro", SCAN_IMG,
           "python", "-c", SCAN, eco, pkg]
    ok, _ = True, ""
    try:
        r = _run(cmd, timeout=120)
    except subprocess.TimeoutExpired:
        return []
    names = [n for n in r.stdout.split() if n and not ENV_SKIP.search(n)] if ok else []
    return names[:40]


def dummy_value(name: str) -> str:
    if re.search(r"PATH|DIR|FILE|HOME|FOLDER|ROOT|STORE|DB$|DATABASE_PATH", name):
        return "/tmp/mcplock"
    if re.search(r"URL|URI|ENDPOINT|BASE|HOST|SERVER", name):
        return "http://127.0.0.1:9"
    return "mcplock-dummy"


# ------------------------------------------------------------------ stage B
NPM_ENTRY = r"""
const fs=require('fs'),path=require('path'),{pathToFileURL}=require('url');
const dir=path.join('/work/node_modules',process.argv[1]);
const pj=JSON.parse(fs.readFileSync(path.join(dir,'package.json')));
let b=pj.bin; if(b&&typeof b==='object'){const k=Object.keys(b);b=b[k.find(x=>x===pj.name.split('/').pop())||k[0]];}
b=b||pj.main||'index.js';
const entry=path.join(dir,b);
process.argv=[process.argv[0],entry,...process.argv.slice(2)];
try{require(entry);}catch(e){
  if(['ERR_REQUIRE_ESM','ERR_REQUIRE_ASYNC_MODULE'].includes(e.code)){import(pathToFileURL(entry).href).catch(x=>{console.error(x);process.exit(1);});}
  else{console.error(e);process.exit(1);}
}
"""

PY_ENTRY = r"""
import sys, configparser, glob, importlib, os
sys.path.insert(0, '/work')
pkg = sys.argv[1].replace('-', '_').replace('.', '_').lower()
eps = []
for f in glob.glob('/work/*.dist-info/entry_points.txt'):
    cp = configparser.ConfigParser(); cp.read(f)
    if cp.has_section('console_scripts'):
        owner = os.path.basename(os.path.dirname(f)).split('-')[0].lower().replace('.', '_')
        eps += [(owner == pkg, k, v) for k, v in cp.items('console_scripts')]
eps.sort(key=lambda e: (not e[0], e[1]))
if not eps: sys.exit('no console_scripts')
mod, _, fn = eps[0][2].partition(':')
sys.argv = [eps[0][1]] + sys.argv[2:]
obj = importlib.import_module(mod.strip())
for part in fn.strip().split('.'): obj = getattr(obj, part)
res = obj()
if hasattr(res, '__await__'):
    import asyncio; asyncio.run(res)
"""


def stage_b(eco: str, pkg: str, vol: str, image: str, args: list[str], env: dict,
            timeout: int) -> dict:
    envs = sum((["-e", f"{k}={v}"] for k, v in env.items()), [])
    if eco == "npm":
        cmd = ["docker", "run", "--rm", "-i", *HARDEN, *envs, "-v", f"{vol}:/work", image,
               "node", "-e", NPM_ENTRY, pkg, *args]
    else:
        cmd = ["docker", "run", "--rm", "-i", *HARDEN, *envs, "-v", f"{vol}:/work", image,
               "python", "-c", PY_ENTRY, pkg, *args]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1, encoding="utf-8",
                         errors="replace")
    responses: dict[int, dict] = {}
    stderr_tail: list[str] = []

    def reader():
        for line in p.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                responses[msg["id"]] = msg

    def err_reader():
        for line in p.stderr:
            stderr_tail.append(line)
            del stderr_tail[:-25]

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=err_reader, daemon=True).start()

    def send(obj):
        try:
            p.stdin.write(json.dumps(obj) + "\n")
            p.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            pass

    def wait(i, t):
        end = time.monotonic() + t
        while time.monotonic() < end and i not in responses and p.poll() is None:
            time.sleep(0.1)
        return responses.get(i)

    out = {"ok": False, "args": args}
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "mcp-lock-census", "version": "0.0.2"}}})
    init = wait(1, timeout)
    if init and "result" in init:
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor, rid = [], None, 2
        while True:
            send({"jsonrpc": "2.0", "id": rid, "method": "tools/list",
                  "params": {"cursor": cursor} if cursor else {}})
            resp = wait(rid, 30)
            if not resp or "result" not in resp:
                out["error"] = "tools/list failed" if resp else "tools/list timeout"
                break
            tools += resp["result"].get("tools", [])
            cursor = resp["result"].get("nextCursor")
            rid += 1
            if not cursor or rid > 20:
                out.update(ok=True, tools=tools)
                break
    else:
        out["error"] = "initialize failed" if init else "initialize timeout/exit"
    try:
        p.kill()
    except OSError:
        pass
    out["stderr_tail"] = "".join(stderr_tail)[-800:]
    return out


def compare(static_tools: list[dict], dyn_tools: list[dict]) -> dict:
    s = {t["name"]: norm_ws(t.get("description")) for t in static_tools}
    d = {t["name"]: norm_ws(t.get("description")) for t in dyn_tools}
    inter = set(s) & set(d)
    return {"n_static": len(s), "n_dynamic": len(d), "n_both": len(inter),
            "name_precision": len(inter) / len(s) if s else None,
            "name_recall": len(inter) / len(d) if d else None,
            "desc_exact_match": (sum(s[n] == d[n] for n in inter) / len(inter)) if inter else None,
            "name_set_equal": set(s) == set(d),
            "names_and_desc_equal": s == d,
            "static_only": sorted(set(s) - set(d))[:20], "dynamic_only": sorted(set(d) - set(s))[:20]}


# ------------------------------------------------------------------ candidates
def candidates(pilot: Path, eco: str) -> list[dict]:
    """Sample packages first (seeded order, as in harness v1), then frame reserve packages in
    their pre-drawn stratum permutation order, interleaved across terciles."""
    versions = [json.loads(x) for x in open(pilot / "versions.jsonl", encoding="utf-8")]
    ex = {(r["ecosystem"], r["package"], r["version"]): r
          for r in map(json.loads, open(pilot / "extractions.jsonl", encoding="utf-8"))}
    rng = np.random.default_rng(SEED)
    out = []
    for e in ("npm", "pypi"):  # same RNG consumption order as v1
        pkgs = sorted((r for r in versions if r["ecosystem"] == e and r["versions"]),
                      key=lambda r: r["package"])
        order = rng.permutation(len(pkgs))
        if e != eco:
            continue
        for i in order:
            r = pkgs[i]
            v = max(r["versions"], key=lambda v: v["order"])
            out.append({"ecosystem": e, "package": r["package"], "tercile": r["tercile"],
                        "source": "sample", "version": v,
                        "static": ex[(e, r["package"], v["version"])]})
    reserve = [json.loads(x) for x in open(pilot / "stratum_order.jsonl", encoding="utf-8")]
    reserve = [r for r in reserve if r["ecosystem"] == eco and r["perm_rank"] >= r["n_h"]]
    reserve.sort(key=lambda r: (r["perm_rank"], r["tercile"]))
    for r in reserve:
        out.append({"ecosystem": eco, "package": r["package"], "tercile": r["tercile"],
                    "source": "reserve", "version": None, "static": None})
    return out


def heldout_candidates(pilot: Path, sample_dir: Path, eco: str) -> list[dict]:
    """Packages of the phase-2 sample never attempted in harness v1/v2 (the development set),
    in an independently seeded order. Static results come from the frozen extractor."""
    dev = set()
    for name in ("validation_v1.jsonl", "validation_npm.jsonl", "validation_pypi.jsonl"):
        f = pilot / name
        if f.exists():
            dev |= {(r["ecosystem"], r["package"]) for r in map(json.loads, open(f, encoding="utf-8"))}
    pool = sorted((r for r in map(json.loads, open(sample_dir / "sample.jsonl", encoding="utf-8"))
                   if r["ecosystem"] == eco and (eco, r["package"]) not in dev),
                  key=lambda r: r["package"])
    order = np.random.default_rng(SEED + 1).permutation(len(pool))
    return [{"ecosystem": eco, "package": pool[i]["package"], "tercile": pool[i]["tercile"],
             "source": "heldout", "version": None, "static": None} for i in order]


def _prepare_reserve(c: dict) -> dict | None:
    """Fetch the latest version and run the static extractor (host side; no code execution)."""
    from census import versions as V
    from census.run_extract import extract_one, fetch_one
    try:
        vs = V.npm_versions(c["package"]) if c["ecosystem"] == "npm" else V.pypi_versions(
            c["package"])
    except http.HttpError:
        return None
    if not vs:
        return None
    v = dict(vs[-1], order=len(vs) - 1)
    fetched = fetch_one((c["ecosystem"], c["package"], v))
    st = extract_one((c["ecosystem"], c["package"], v["version"], fetched))
    return {**c, "version": v, "static": st}


def _requires_python(pkg: str, ver: str) -> str | None:
    try:
        return http.get_json(f"https://pypi.org/pypi/{pkg}/{ver}/json")["info"].get(
            "requires_python")
    except (http.HttpError, KeyError):
        return None


def _f1_index() -> dict:
    f1 = {}
    for line in open("results/census/frame/f1_registry.jsonl", encoding="utf-8"):
        r = json.loads(line)
        f1.setdefault((r["ecosystem"], r["package"]), r)
    return f1


def attempt(c: dict, idx: int, f1: dict) -> dict:
    if c["source"] in ("reserve", "heldout"):
        c2 = _prepare_reserve(c)
        if c2 is None:
            return {"ecosystem": c["ecosystem"], "package": c["package"], "attempt": idx,
                    "source": c["source"], "skipped": "metadata unavailable"}
        c = c2
    eco, pkg, v = c["ecosystem"], c["package"], c["version"]
    reg = f1.get((eco, pkg), {})
    base_args = [a.get("value") or a.get("default") or "/tmp/mcplock"
                 for a in (reg.get("package_arguments") or []) if a.get("type") == "positional"][:5]
    reg_env = {e["name"]: e.get("default") or dummy_value(e["name"])
               for e in (reg.get("environment_variables") or []) if e.get("name")}
    rp = _requires_python(pkg, v["version"]) if eco == "pypi" else None
    vol = f"mcplock_{eco}_{idx}"
    rec = {"ecosystem": eco, "package": pkg, "version": v["version"], "attempt": idx,
           "source": c["source"], "tercile": c["tercile"], "requires_python": rp,
           "static_status": c["static"]["status"], "static_n_tools": c["static"]["n_tools"]}
    a = stage_a(eco, pkg, v["version"], vol, _cutoff(v.get("published")), rp)
    rec.update(stage_a_ok=a["ok"], stage_a_tries=a["tries"], image=a.get("image"),
               dep_snapshot=a.get("dep_snapshot"))
    if not a["ok"]:
        rec["stage_a_log"] = a.get("log")
        _run(["docker", "volume", "rm", "-f", vol])
        return rec
    scanned = env_scan(eco, pkg, vol)
    env = {n: dummy_value(n) for n in scanned}
    env.update(reg_env)
    rec["env_names"] = sorted(env)
    tries = []
    for k, extra in enumerate([[]] + ARG_FALLBACKS):
        b = stage_b(eco, pkg, vol, a["image"], base_args + extra, env,
                    FIRST_TIMEOUT if k == 0 else RETRY_TIMEOUT)
        tries.append({"args": b["args"], "ok": b["ok"], "error": b.get("error")})
        if b["ok"] or b.get("error") == "tools/list failed":
            break
    rec["stage_b_tries"] = tries
    rec["stage_b_ok"] = b["ok"]
    rec["stage_b_error"] = b.get("error")
    rec["stderr_tail"] = b.get("stderr_tail")
    if b["ok"]:
        rec["compare"] = compare(c["static"].get("tools", []), b["tools"])
        rec["dynamic_tools"] = [{"name": t.get("name"), "description": t.get("description")}
                                for t in b["tools"]]
    _run(["docker", "volume", "rm", "-f", vol])
    return rec


def run(pilot: Path, eco: str, target: int, max_attempts: int, workers: int,
        pool_name: str = "dev", sample_dir: Path | None = None) -> Path:
    if pool_name == "heldout":
        cands = heldout_candidates(pilot, sample_dir, eco)[:max_attempts]
        out_dir, prefix = sample_dir, "validation_heldout_"
    else:
        cands = candidates(pilot, eco)[:max_attempts]
        out_dir, prefix = pilot, "validation_"
    f1 = _f1_index()
    results, validated, i = [], 0, 0
    with ThreadPoolExecutor(workers) as pool:
        while i < len(cands) and validated < target:
            batch = list(range(i, min(i + workers, len(cands))))
            for rec in pool.map(lambda k: attempt(cands[k], k, f1), batch):
                results.append(rec)
                validated += bool(rec.get("stage_b_ok"))
                print(f"[{eco} {rec['attempt']}] {rec['package']} src={rec.get('source')} "
                      f"A={rec.get('stage_a_ok')} B={rec.get('stage_b_ok')} "
                      f"eq={rec.get('compare', {}).get('name_set_equal')} validated={validated}",
                      flush=True)
            i = batch[-1] + 1
    out = out_dir / f"{prefix}{eco}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    provenance.write(out, inputs=[pilot / "versions.jsonl", pilot / "extractions.jsonl",
                                  pilot / "stratum_order.jsonl"],
                     params={"harness": "v2", "pool": pool_name, "seed": SEED, "eco": eco,
                             "target": target,
                             "max_attempts": max_attempts, "workers": workers,
                             "images": [NODE_IMG, *PY_IMGS.values()], "hardening": HARDEN,
                             "first_timeout_s": FIRST_TIMEOUT, "retry_timeout_s": RETRY_TIMEOUT,
                             "arg_fallbacks": ARG_FALLBACKS})
    return out


# ------------------------------------------------------------------ summary
def summarize(pilot: Path, prefix: str = "validation_") -> dict:
    """Extractor accuracy against tools/list ground truth, plus a selection-bias check."""
    from census.stats import wilson

    files = [pilot / f"{prefix}{e}.jsonl" for e in ("npm", "pypi") if (pilot / f"{prefix}{e}.jsonl").exists()]
    rows = []
    for p in files:
        rows += [json.loads(x) for x in open(p, encoding="utf-8")]
    rows = [r for r in rows if not r.get("skipped")]
    ok = [r for r in rows if r.get("stage_b_ok")]
    out: dict = {"harness": "v2", "attempted": len(rows),
                 "stage_a_failed": sum(not r["stage_a_ok"] for r in rows),
                 "stage_b_failed": sum(r["stage_a_ok"] and not r.get("stage_b_ok") for r in rows),
                 "validated": len(ok), "start_rate": wilson(len(ok), len(rows)),
                 "validated_needing_arg_fallback": sum(len(r["stage_b_tries"]) > 1 for r in ok),
                 "validated_without_dep_snapshot": sum(not r.get("dep_snapshot") for r in ok)}
    for eco in ("all", "npm", "pypi"):
        sub = [r for r in ok if eco == "all" or r["ecosystem"] == eco]
        att = [r for r in rows if eco == "all" or r["ecosystem"] == eco]
        if not sub:
            continue
        c = [r["compare"] for r in sub]
        both, ns, nd = (sum(x[k] for x in c) for k in ("n_both", "n_static", "n_dynamic"))
        dyn_pos = [x for x in c if x["n_dynamic"] > 0]
        detected = sum(1 for x in dyn_pos if x["n_static"] > 0)
        eq = sum(x["name_set_equal"] for x in c)
        desc = [x["desc_exact_match"] for x in c if x["desc_exact_match"] is not None]
        prec = [x["name_precision"] for x in c if x["name_precision"] is not None]
        rec_ = [x["name_recall"] for x in c if x["name_recall"] is not None]
        # selection bias: is static extractability different for servers that did not start?
        started = [r for r in att if r.get("stage_b_ok")]
        failed = [r for r in att if not r.get("stage_b_ok")]
        s_ext = sum(r["static_n_tools"] > 0 for r in started)
        f_ext = sum(r["static_n_tools"] > 0 for r in failed)
        out[eco] = {
            "attempted": len(att), "validated": len(sub),
            "start_rate": wilson(len(sub), len(att)),
            "name_precision_micro": both / ns if ns else None,
            "name_recall_micro": both / nd if nd else None,
            "name_precision_macro": sum(prec) / len(prec) if prec else None,
            "name_recall_macro": sum(rec_) / len(rec_) if rec_ else None,
            "name_set_equal": [eq, len(sub), wilson(eq, len(sub))],
            "g1_detection_when_server_has_tools": [detected, len(dyn_pos),
                                                   wilson(detected, len(dyn_pos))],
            "servers_with_zero_tools": sum(1 for x in c if x["n_dynamic"] == 0),
            "description_exact_match_mean": sum(desc) / len(desc) if desc else None,
            "bias_static_extractable_started": [s_ext, len(started), wilson(s_ext, len(started))],
            "bias_static_extractable_not_started": [f_ext, len(failed),
                                                    wilson(f_ext, len(failed))],
            "validated_by_tercile": {t: sum(r["tercile"] == t for r in sub) for t in (0, 1, 2)},
            "attempted_by_tercile": {t: sum(r["tercile"] == t for r in att) for t in (0, 1, 2)},
        }
    fails: dict[str, int] = {}
    for r in rows:
        if r.get("stage_b_ok"):
            continue
        k = "stage_a" if not r["stage_a_ok"] else (r.get("stage_b_error") or "unknown")
        fails[k] = fails.get(k, 0) + 1
    out["failure_reasons"] = fails
    dest = pilot / f"{prefix}summary.json"
    dest.write_text(json.dumps(out, indent=2))
    provenance.write(dest, inputs=files)
    print(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("pilot", type=Path)
    r.add_argument("--eco", choices=["npm", "pypi"], required=True)
    r.add_argument("--target", type=int, default=40)
    r.add_argument("--max-attempts", type=int, default=160)
    r.add_argument("--workers", type=int, default=3)
    r.add_argument("--pool", choices=["dev", "heldout"], default="dev")
    r.add_argument("--sample-dir", type=Path, default=Path("results/census/phase2"))
    s = sub.add_parser("summarize")
    s.add_argument("pilot", type=Path)
    s.add_argument("--prefix", default="validation_")
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.pilot, a.eco, a.target, a.max_attempts, a.workers, a.pool, a.sample_dir)
    else:
        summarize(a.pilot, a.prefix)


if __name__ == "__main__":
    main()
