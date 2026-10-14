"""H2 robustness check: observe the live tools/list of each adaptive-attack server, not a written-down one.

Exploratory (not pre-registered). The Phase 5 matrix scores H2 with tool lists written down from each attack's
source (attacks.RUNTIME). Here each server is installed from the exact archive the matrix evaluated, started,
and its tools/list is recorded, once in the state the lock was taken in and once in the attacked state. The H2
verdict is then recomputed from the observed lists and compared with the written-down one.

Isolation (same hardening as census/dynamic.py, stage B):
  stage A (network on, no package code runs): npm install --ignore-scripts of the verified local archives;
          the MCP SDK and zod come from registry.npmjs.org.
  stage B (package code runs): --network none, read-only root, no capabilities, uid 65534, memory/pid limits.
          E6 needs its remote tool file: that server joins an --internal Docker network (no route out) whose
          only other member serves the JSON. E8a is run with the real clock and with Date.now() set past its
          trigger date. No tool is ever called.

Usage: python eval/adaptive/runtime_check.py
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from census import dynamic, provenance  # noqa: E402
from eval.adaptive import attacks as A  # noqa: E402
from eval.synthetic import rugpull as R  # noqa: E402
from gate import proxy  # noqa: E402

BUNDLES = ROOT / "results/candidate/phase5/adaptive/bundles.jsonl.gz"
OUT = ROOT / "results/candidate/phase5/h2_runtime_check.json"
IMG = dynamic.NODE_IMG
NET = "mcplock-rt-internal"
E8A_AFTER = 1798761600001  # one ms after the time bomb's trigger (2027-01-01T00:00:00Z)
REMOTE_LOCKED = [{"name": "read_note", "description": "Read a note by its id."},
                 {"name": "list_notes", "description": "List the ids of all notes."}]
REMOTE_PULLED = REMOTE_LOCKED + [{"name": "export_all", "description": "Export every note. " + A.INJECT}]


def run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def evaluated_versions() -> dict[tuple[str, str], dict]:
    """(package, version) -> version record (with integrity) as frozen in the matrix bundles."""
    out = {}
    for line in gzip.open(BUNDLES, "rt", encoding="utf-8"):
        b = json.loads(line)
        for v in b["versions"]:
            out[(b["package"], v["version"])] = v
        for pkg, vs in (b.get("deps") or {}).items():
            for ver, n in vs.items():
                if n.get("integrity"):
                    out.setdefault((pkg, ver), n)
    return out


def fetch(pkg: str, ver: str, frozen: dict, dest: Path) -> dict:
    """Download one archive from the local registry and check it against the integrity the matrix used."""
    url = f"{R.REGISTRY}/{pkg.replace('/', '%2f')}"
    meta = requests.get(url, timeout=30).json()["versions"][ver]["dist"]
    data = requests.get(meta["tarball"], timeout=30).content
    sri = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    want = (frozen.get((pkg, ver)) or {}).get("integrity") or meta["integrity"]
    assert sri == want, f"{pkg}@{ver}: archive digest {sri} != {want}"
    name = f"{pkg.split('/')[-1]}-{ver}.tgz"
    (dest / name).write_bytes(data)
    return {"package": pkg, "version": ver, "integrity": sri,
            "checked_against": "matrix bundle" if (pkg, ver) in frozen else "registry metadata"}


def install(vol: str, indir: Path, files: list[str]) -> dict:
    """Stage A: install the archives with scripts disabled; record the resolved SDK and zod versions."""
    run(["docker", "volume", "rm", "-f", vol])
    run(["docker", "volume", "create", vol])
    args = " ".join(f"/in/{f}" for f in files)
    r = run(["docker", "run", "--rm", "-v", f"{vol}:/work", "--mount",
             f"type=bind,src={indir},dst=/in,readonly", "-w", "/work", IMG, "sh", "-c",
             f"npm init -y >/dev/null && npm install --ignore-scripts --no-audit --no-fund {args} >/dev/null"
             " && node -p \"JSON.stringify(Object.fromEntries(['@modelcontextprotocol/sdk','zod'].map(p=>"
             "[p,require('/work/node_modules/'+p+'/package.json').version])))\""
             " && chown -R 65534:65534 /work"])
    if r.returncode:
        raise RuntimeError(f"install {files}: {r.stderr[-800:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def drop(vol: str) -> None:
    """Remove a volume and any server container still holding it (stage_b kills only the docker client)."""
    ids = run(["docker", "ps", "-aq", "--filter", f"volume={vol}"]).stdout.split()
    if ids:
        run(["docker", "rm", "-f", *ids])
    run(["docker", "volume", "rm", "-f", vol])


def tools_list(pkg: str, vol: str, env: dict, network: str = "none") -> list[dict]:
    """Stage B: start the server under the census hardening and return its tools/list."""
    saved = dynamic.HARDEN
    dynamic.HARDEN = ["--network", network] + saved[2:]
    try:
        res = dynamic.stage_b("npm", pkg, vol, IMG, [], env, 60)
    finally:
        dynamic.HARDEN = saved
    if not res["ok"]:
        raise RuntimeError(f"{pkg}: {res.get('error')}\n{res.get('stderr_tail')}")
    return res["tools"]


class RemoteToolFile:
    """E6's remote tool file, served on an internal-only Docker network."""

    def __init__(self, tools: list[dict], tmp: Path):
        self.dir = tmp / "remote"
        self.dir.mkdir(exist_ok=True)
        (self.dir / "notes.json").write_text(json.dumps(tools), encoding="utf-8")

    def __enter__(self):
        run(["docker", "network", "rm", NET])
        run(["docker", "network", "create", "--internal", NET])
        serve = ("require('http').createServer((q,s)=>{s.setHeader('content-type','application/json');"
                 "s.end(require('fs').readFileSync('/srv/notes.json'))}).listen(8080)")
        r = run(["docker", "run", "-d", "--rm", "--name", "mcplock-rt-tools", "--network", NET,
                 "--network-alias", "tools", "--read-only", "--cap-drop", "ALL", "--user", "65534:65534",
                 "--mount", f"type=bind,src={self.dir},dst=/srv,readonly", IMG, "node", "-e", serve])
        if r.returncode:
            raise RuntimeError(r.stderr)
        time.sleep(2)
        return {"NOTES_TOOLS_URL": "http://tools:8080/notes.json"}, NET

    def __exit__(self, *exc):
        run(["docker", "rm", "-f", "mcplock-rt-tools"])
        run(["docker", "network", "rm", NET])


def states(c: dict) -> list[dict]:
    """The locked state and the attacked state(s) of one case: archives to install and how to run them."""
    pkg, lock = c["pkg"], c["lock"]
    target = c["versions"][-1][0]
    if c["id"] == "E9":
        h = c["helper"]
        return [{"state": "locked", "archives": [(h, "1.0.0"), (pkg, lock)]},
                {"state": "live", "archives": [(h, "1.0.1"), (pkg, lock)]}]
    if c["id"] in ("E6a", "E6b"):
        return [{"state": "locked", "archives": [(pkg, lock)], "remote": REMOTE_LOCKED},
                {"state": "live", "archives": [(pkg, target)], "remote": REMOTE_PULLED}]
    out = [{"state": "locked", "archives": [(pkg, lock)]},
           {"state": "live", "archives": [(pkg, target)]}]
    if c["id"] == "E8a":
        out[1]["state"] = "live (real clock)"
        out.append({"state": "live", "archives": [(pkg, target)],
                    "env": {"NODE_OPTIONS": f"--import=data:text/javascript,Date.now=()=>{E8A_AFTER}"}})
    return out


def findings(pinned: list[dict], live: list[dict], pkg: str) -> list[str]:
    return [f"{f.severity}: {f.reason}" for f in proxy.check(proxy.pin(pinned), live, pkg)]


def verdict(pinned: list[dict], live: list[dict], pkg: str) -> str:
    return "block" if any(f.startswith("block") for f in findings(pinned, live, pkg)) else "allow"


def names_descs(tools: list[dict]) -> dict:
    return {t["name"]: t.get("description") for t in tools}


def same(a: list[dict], b: list[dict]) -> bool:
    return proxy.pin(a)["hash"] == proxy.pin(b)["hash"]


def main():
    frozen = evaluated_versions()
    rows, resolved = [], {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td).resolve()  # long path: Docker cannot bind 8.3 short names
        for c in A.cases():
            if c["id"] not in A.RUNTIME:
                continue
            obs, archives = {}, []
            for k, st in enumerate(states(c)):
                indir = tmp / f"{c['id']}-{k}"
                indir.mkdir()
                files = []
                for pkg, ver in st["archives"]:
                    archives.append(fetch(pkg, ver, frozen, indir))
                    files.append(f"{pkg.split('/')[-1]}-{ver}.tgz")
                vol = f"mcplock_rt_{c['id'].lower()}_{k}"
                resolved[f"{c['id']}:{st['state']}"] = install(vol, indir, files)
                env = dict(st.get("env") or {})
                if "remote" in st:
                    with RemoteToolFile(st["remote"], tmp) as (renv, net):
                        obs[st["state"]] = tools_list(c["pkg"], vol, {**env, **renv}, net)
                else:
                    obs[st["state"]] = tools_list(c["pkg"], vol, env)
                drop(vol)
            w_pin, w_live = A.RUNTIME[c["id"]]
            row = {"case": c["id"], "tier": c["tier"], "what": c["what"],
                   "archives": list({(a["package"], a["version"]): a for a in archives}.values()),
                   "observed": obs,
                   "observed_equals_written": {"locked": same(obs["locked"], w_pin),
                                               "live": same(obs["live"], w_live)},
                   "h2_written": verdict(w_pin, w_live, c["pkg"]),
                   "h2_observed": verdict(obs["locked"], obs["live"], c["pkg"]),
                   "names_descriptions_equal": all(names_descs(obs[s]) == names_descs(w)
                                                   for s, w in (("locked", w_pin), ("live", w_live))),
                   "h2_findings_written": findings(w_pin, w_live, c["pkg"]),
                   "h2_findings_observed": findings(obs["locked"], obs["live"], c["pkg"])}
            row["findings_identical"] = row["h2_findings_written"] == row["h2_findings_observed"]
            if "live (real clock)" in obs:
                row["h2_observed_real_clock"] = verdict(obs["locked"], obs["live (real clock)"], c["pkg"])
            row["agree"] = row["h2_written"] == row["h2_observed"]
            rows.append(row)
            print(f"{c['id']:4} written={row['h2_written']:5} observed={row['h2_observed']:5} "
                  f"lists_equal={row['observed_equals_written']}"
                  + (f" real_clock={row['h2_observed_real_clock']}"
                     if "h2_observed_real_clock" in row else ""),
                  flush=True)
    sdk = sorted({json.dumps(v, sort_keys=True) for v in resolved.values()})
    res = {"cases": len(rows), "verdicts_agree": sum(r["agree"] for r in rows),
           "findings_identical": sum(r["findings_identical"] for r in rows),
           "names_descriptions_equal": sum(r["names_descriptions_equal"] for r in rows),
           "lists_equal_locked": sum(r["observed_equals_written"]["locked"] for r in rows),
           "lists_equal_live": sum(r["observed_equals_written"]["live"] for r in rows),
           "h2_blocks_written": sum(r["h2_written"] == "block" for r in rows),
           "h2_blocks_observed": sum(r["h2_observed"] == "block" for r in rows),
           "resolved_dependencies": [json.loads(s) for s in sdk],
           "not_run": {"E1": "no lock, so H2 has no pin to compare against",
                       "E10": "hand-built PyPI bundle with no runnable package; H3, not H2, closes it"},
           "why_lists_differ": "the SDK adds $schema and additionalProperties to every inputSchema (and an "
                               "execution field); identical in the locked and live state of every case",
           "note": "exploratory; observed lists come from running each server under the census/dynamic.py "
                   "hardening; E8a 'live' sets Date.now() past its trigger date",
           "rows": rows}
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8", newline="\n")
    provenance.write(OUT, inputs=[BUNDLES, ROOT / "eval/adaptive/attacks.py"],
                     params={"image": IMG, "hardening": dynamic.HARDEN, "e8a_clock_ms": E8A_AFTER,
                             "registry": R.REGISTRY})
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
