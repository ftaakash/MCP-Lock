"""Dynamic ground truth for the static extractor (plan §6). Two stages:

Stage A (network on, NO package code runs):
    npm:  npm install --ignore-scripts <pkg>@<ver>       (node:22-slim)
    pypi: pip install --only-binary=:all: --target ...   (python:3.11-slim; wheels never run code)
Stage B (package code runs, network off):
    docker run --network none --read-only --cap-drop ALL --security-opt no-new-privileges
    --user 65534 --memory 1g --pids-limit 256; MCP initialize + tools/list over stdio, then kill.
No tool is ever called.

Usage: python -m census.dynamic <pilot_dir> [n_per_ecosystem]
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

from census import provenance
from census.tooldefs import norm_ws

SEED = 20261008
NODE_IMG = "node:22-slim"
PY_IMG = "python:3.11-slim"
TIMEOUT = 30
HARDEN = ["--network", "none", "--read-only", "--cap-drop", "ALL",
          "--security-opt", "no-new-privileges", "--user", "65534:65534",
          "--memory", "1g", "--pids-limit", "256", "--tmpfs", "/tmp:rw,size=64m"]


def _run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def stage_a(eco: str, pkg: str, ver: str, vol: str) -> tuple[bool, str]:
    _run(["docker", "volume", "rm", "-f", vol])
    _run(["docker", "volume", "create", vol])
    if eco == "npm":
        cmd = ["docker", "run", "--rm", "-v", f"{vol}:/work", "-w", "/work", NODE_IMG, "sh", "-c",
               f"npm init -y >/dev/null && npm install --ignore-scripts --no-audit --no-fund "
               f"'{pkg}@{ver}' && chmod -R a+rX /work"]
    else:
        cmd = ["docker", "run", "--rm", "-v", f"{vol}:/work", PY_IMG, "sh", "-c",
               f"pip install -q --disable-pip-version-check --only-binary=:all: --target /work "
               f"'{pkg}=={ver}' && chmod -R a+rX /work"]
    try:
        r = _run(cmd, timeout=900)
    except subprocess.TimeoutExpired:
        return False, "stage A timeout"
    return r.returncode == 0, (r.stderr or r.stdout)[-400:]


NPM_ENTRY = r"""
const fs=require('fs'),path=require('path');
const pj=JSON.parse(fs.readFileSync(path.join('/work/node_modules',process.argv[1],'package.json')));
let b=pj.bin; if(typeof b==='object'){const k=Object.keys(b); b=b[k.find(x=>x===pj.name.split('/').pop())||k[0]];}
b=b||pj.main||'index.js';
process.argv=[process.argv[0],path.join('/work/node_modules',process.argv[1],b),...process.argv.slice(2)];
require(process.argv[1]);
"""

PY_ENTRY = r"""
import sys, configparser, glob, importlib, os
sys.path.insert(0, '/work')
pkg = sys.argv[1].replace('-', '_').lower()
eps = []
for f in glob.glob('/work/*.dist-info/entry_points.txt'):
    cp = configparser.ConfigParser(); cp.read(f)
    if cp.has_section('console_scripts'):
        owner = os.path.basename(os.path.dirname(f)).split('-')[0].lower()
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


def stage_b(eco: str, pkg: str, vol: str, args: list[str], env: dict) -> dict:
    envs = sum((["-e", f"{k}={v}"] for k, v in env.items()), [])
    if eco == "npm":
        cmd = ["docker", "run", "--rm", "-i", *HARDEN, *envs, "-v", f"{vol}:/work:ro",
               NODE_IMG, "node", "-e", NPM_ENTRY, pkg, *args]
    else:
        cmd = ["docker", "run", "--rm", "-i", *HARDEN, *envs, "-v", f"{vol}:/work:ro",
               "-e", "HOME=/tmp", PY_IMG, "python", "-c", PY_ENTRY, pkg, *args]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, bufsize=1)
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
            del stderr_tail[:-20]

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=err_reader, daemon=True).start()

    def send(obj):
        try:
            p.stdin.write(json.dumps(obj) + "\n")
            p.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def wait(i):
        end = time.monotonic() + TIMEOUT
        while time.monotonic() < end and i not in responses and p.poll() is None:
            time.sleep(0.1)
        return responses.get(i)

    out = {"ok": False}
    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "mcp-lock-census", "version": "0.0.1"}}})
    init = wait(1)
    if init and "result" in init:
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools, cursor, rid = [], None, 2
        while True:
            params = {"cursor": cursor} if cursor else {}
            send({"jsonrpc": "2.0", "id": rid, "method": "tools/list", "params": params})
            resp = wait(rid)
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
    out["stderr_tail"] = "".join(stderr_tail)[-600:]
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


def run(pilot: Path, per_eco: int = 20) -> Path:
    versions = [json.loads(x) for x in open(pilot / "versions.jsonl", encoding="utf-8")]
    ex = {(r["ecosystem"], r["package"], r["version"]): r
          for r in map(json.loads, open(pilot / "extractions.jsonl", encoding="utf-8"))}
    f1 = {}
    f1_path = Path("results/census/frame/f1_registry.jsonl")
    for line in open(f1_path, encoding="utf-8"):
        r = json.loads(line)
        f1.setdefault((r["ecosystem"], r["package"]), r)
    rng = np.random.default_rng(SEED)
    results = []
    for eco in ("npm", "pypi"):
        pkgs = sorted((r for r in versions if r["ecosystem"] == eco and r["versions"]),
                      key=lambda r: r["package"])
        order = rng.permutation(len(pkgs))
        validated = 0
        for attempt, i in enumerate(order):
            if validated >= per_eco:
                break
            r = pkgs[i]
            v = max(r["versions"], key=lambda v: v["order"])
            reg = f1.get((eco, r["package"]), {})
            args = [a.get("value") or a.get("default") or "/tmp"
                    for a in (reg.get("package_arguments") or [])
                    if a.get("type") == "positional"][:5]
            env = {e["name"]: e.get("default") or "dummy"
                   for e in (reg.get("environment_variables") or []) if e.get("name")}
            vol = f"mcplock_{eco}_{attempt}"
            ok_a, log_a = stage_a(eco, r["package"], v["version"], vol)
            rec = {"ecosystem": eco, "package": r["package"], "version": v["version"],
                   "attempt": attempt, "stage_a_ok": ok_a, "args": args,
                   "env_names": sorted(env)}
            if ok_a:
                b = stage_b(eco, r["package"], vol, args, env)
                rec["stage_b_ok"] = b["ok"]
                rec["stage_b_error"] = b.get("error")
                rec["stderr_tail"] = b.get("stderr_tail")
                if b["ok"]:
                    st = ex[(eco, r["package"], v["version"])]
                    rec["static_status"] = st["status"]
                    rec["compare"] = compare(st.get("tools", []), b["tools"])
                    rec["dynamic_tools"] = [{"name": t.get("name"),
                                             "description": t.get("description")}
                                            for t in b["tools"]]
                    validated += 1
            else:
                rec["stage_a_log"] = log_a
            _run(["docker", "volume", "rm", "-f", vol])
            results.append(rec)
            print(f"{eco} {r['package']}@{v['version']}: A={ok_a} B={rec.get('stage_b_ok')} "
                  f"{rec.get('compare', {}).get('name_set_equal')}", flush=True)
    out = pilot / "validation.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    provenance.write(out, inputs=[pilot / "versions.jsonl", pilot / "extractions.jsonl"],
                     params={"seed": SEED, "per_ecosystem": per_eco, "images": [NODE_IMG, PY_IMG],
                             "hardening": HARDEN, "timeout_s": TIMEOUT})
    return out


def summarize(pilot: Path) -> dict:
    """Extractor accuracy against tools/list ground truth (plan §6)."""
    from census.stats import wilson

    rows = [json.loads(x) for x in open(pilot / "validation.jsonl", encoding="utf-8")]
    ok = [r for r in rows if r.get("stage_b_ok")]
    out: dict = {"attempted": len(rows), "stage_a_failed": sum(not r["stage_a_ok"] for r in rows),
                 "stage_b_failed": sum(r["stage_a_ok"] and not r.get("stage_b_ok") for r in rows),
                 "validated": len(ok)}
    for eco in ("all", "npm", "pypi"):
        sub = [r for r in ok if eco == "all" or r["ecosystem"] == eco]
        if not sub:
            continue
        c = [r["compare"] for r in sub]
        both, ns, nd = (sum(x[k] for x in c) for k in ("n_both", "n_static", "n_dynamic"))
        dyn_pos = [x for x in c if x["n_dynamic"] > 0]
        detected = sum(1 for x in dyn_pos if x["n_static"] > 0)
        eq = sum(x["name_set_equal"] for x in c)
        desc = [x["desc_exact_match"] for x in c if x["desc_exact_match"] is not None]
        out[eco] = {
            "versions": len(sub),
            "name_precision_micro": both / ns if ns else None,
            "name_recall_micro": both / nd if nd else None,
            "name_set_equal": [eq, len(sub), wilson(eq, len(sub))],
            "g1_detection_when_server_has_tools": [detected, len(dyn_pos),
                                                   wilson(detected, len(dyn_pos))],
            "servers_with_zero_tools": sum(1 for x in c if x["n_dynamic"] == 0),
            "description_exact_match_mean": sum(desc) / len(desc) if desc else None,
        }
    (pilot / "validation_summary.json").write_text(json.dumps(out, indent=2))
    provenance.write(pilot / "validation_summary.json", inputs=[pilot / "validation.jsonl"])
    print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    if sys.argv[1] == "summarize":
        summarize(Path(sys.argv[2]))
    else:
        run(Path(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 20)
