"""Registry metadata for frame packages: eligibility (>= 2 versions) and popularity.

Usage:
    python -m census.meta eligibility <frame.jsonl>
    python -m census.meta downloads <eligibility.jsonl>
"""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

from census import http, provenance

OUT = Path("results/census/frame")

# Launchers / proxies that ship no tool definitions of their own (pre-specified, plan §2.3).
PROXIES = {
    ("npm", "mcp-remote"), ("npm", "@smithery/cli"), ("npm", "supergateway"),
    ("npm", "@modelcontextprotocol/inspector"), ("npm", "mcp-proxy"),
    ("npm", "@pulsemcp/mcp-remote"), ("npm", "@llmindset/mcp-remote"),
    ("pypi", "mcp-proxy"), ("pypi", "mcp-remote"), ("npm", "@agentdeskai/browser-tools-server"),
}
# Generic script runners that only execute a local file (`npx tsx ./server.ts`); they are not
# MCP servers. Fixed before sampling (2026-10-08) after inspecting the top F2-only launches.
RUNNERS = {
    ("npm", n) for n in ("tsx", "ts-node", "dotenv-cli", "cross-env", "env-cmd", "nodemon",
                         "concurrently", "@dotenvx/dotenvx", "dotenv", "node", "deno", "vite-node",
                         "esno", "esrun", "jiti", "bun", "npm", "pnpm", "yarn", "typescript")
} | {("pypi", n) for n in ("python", "poetry", "hatch", "pdm", "uv", "pip", "pipx")}


def npm_url(pkg: str) -> str:
    return "https://registry.npmjs.org/" + quote(pkg, safe="@")


def pypi_url(pkg: str) -> str:
    return f"https://pypi.org/pypi/{pkg}/json"


def _npm_summary(pkg: str) -> dict:
    try:
        doc = http.get_json(npm_url(pkg) + "?abbreviated",
                            headers={"Accept": "application/vnd.npm.install-v1+json"})
    except http.HttpError as e:
        return {"resolves": False, "http": e.status}
    versions = doc.get("versions") or {}
    latest = (doc.get("dist-tags") or {}).get("latest")
    dep_latest = bool(latest and versions.get(latest, {}).get("deprecated"))
    return {"resolves": bool(versions), "n_versions": len(versions), "latest": latest,
            "latest_deprecated": dep_latest, "modified": doc.get("modified")}


def _pypi_summary(pkg: str) -> dict:
    try:
        doc = http.get_json(pypi_url(pkg))
    except http.HttpError as e:
        return {"resolves": False, "http": e.status}
    rel = doc.get("releases") or {}
    live = [v for v, files in rel.items() if files and not all(f.get("yanked") for f in files)]
    return {"resolves": bool(live), "n_versions": len(live),
            "latest": (doc.get("info") or {}).get("version"), "latest_deprecated": False}


def eligibility(frame_path: str) -> Path:
    rows = [json.loads(x) for x in open(frame_path, encoding="utf-8")]
    rows = [r for r in rows if r["in_frame"]]

    def work(r):
        fn = _npm_summary if r["ecosystem"] == "npm" else _pypi_summary
        s = fn(r["package"])
        key = (r["ecosystem"], r["package"])
        proxy = key in PROXIES
        runner = key in RUNNERS
        eligible = (s.get("resolves", False) and s.get("n_versions", 0) >= 2 and not proxy
                    and not runner)
        reason = ("proxy" if proxy else "generic_runner" if runner
                  else "unresolved" if not s.get("resolves")
                  else "single_version" if s.get("n_versions", 0) < 2 else "ok")
        return {**{k: r[k] for k in ("ecosystem", "package", "in_f1", "f2_files_unpinned",
                                     "f2_repos")}, **s, "proxy": proxy,
                "eligible": eligible, "reason": reason}

    with ThreadPoolExecutor(8) as ex:
        out_rows = list(ex.map(work, rows))
    out = OUT / (Path(frame_path).stem + "_eligibility.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in out_rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    from collections import Counter
    c = Counter((r["ecosystem"], r["reason"]) for r in out_rows)
    provenance.write(out, inputs=[Path(frame_path)], params={"counts": {f"{a}:{b}": n for (a, b), n
                                                                      in sorted(c.items())}})
    print("eligibility:", dict(sorted(c.items())), "->", out)
    return out


def _with_retries(fetch_one, pkgs: list[str], workers: int) -> dict[str, int | None]:
    """fetch_one returns an int, or None on a transient failure; failures are retried
    sequentially up to 3 more passes. A package that still fails stays None (never 0)."""
    with ThreadPoolExecutor(workers) as ex:
        res = dict(zip(pkgs, ex.map(fetch_one, pkgs), strict=True))
    for attempt in range(3):
        todo = [p for p, v in res.items() if v is None]
        if not todo:
            break
        time.sleep(30 * (attempt + 1))
        for p in todo:
            res[p] = fetch_one(p)
    return res


def _npm_one(p: str) -> int | None:
    try:
        return http.get_json("https://api.npmjs.org/downloads/point/last-month/"
                             + quote(p, safe="@")).get("downloads", 0)
    except http.HttpError as e:
        return 0 if e.status == 404 else None  # 404 = package has no download stats


def _npm_downloads(pkgs: list[str]) -> dict[str, int | None]:
    res: dict[str, int | None] = {}
    unscoped = [p for p in pkgs if not p.startswith("@")]
    scoped = [p for p in pkgs if p.startswith("@")]
    for i in range(0, len(unscoped), 128):
        chunk = unscoped[i:i + 128]
        url = "https://api.npmjs.org/downloads/point/last-month/" + ",".join(chunk)
        try:
            data = http.get_json(url)
        except http.HttpError:
            data = {}
        if len(chunk) == 1:
            data = {chunk[0]: data}
        for p in chunk:
            v = data.get(p)
            if isinstance(v, dict) and "downloads" in v:
                res[p] = v["downloads"]
            else:
                scoped.append(p)  # missing from the bulk answer: ask individually
    res.update(_with_retries(_npm_one, scoped, 4))
    return res


def _pypi_one(p: str) -> int | None:
    try:
        d = http.get_json(f"https://pypistats.org/api/packages/{p}/recent")
        return (d.get("data") or {}).get("last_month", 0)
    except http.HttpError as e:
        return 0 if e.status == 404 else None


def _pypi_downloads(pkgs: list[str]) -> dict[str, int | None]:
    return _with_retries(_pypi_one, pkgs, 2)


def downloads(elig_path: str) -> Path:
    rows = [json.loads(x) for x in open(elig_path, encoding="utf-8")]
    rows = [r for r in rows if r["eligible"]]
    with ThreadPoolExecutor(2) as ex:  # different hosts and rate limits: run side by side
        f_npm = ex.submit(_npm_downloads, [r["package"] for r in rows if r["ecosystem"] == "npm"])
        f_py = ex.submit(_pypi_downloads, [r["package"] for r in rows if r["ecosystem"] == "pypi"])
        npm, pypi = f_npm.result(), f_py.result()
    for r in rows:
        v = (npm if r["ecosystem"] == "npm" else pypi).get(r["package"])
        r["downloads_failed"] = v is None
        r["downloads_last_month"] = v or 0
    out = Path(elig_path).with_name(Path(elig_path).stem.replace("_eligibility", "")
                                    + "_eligible_downloads.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    provenance.write(out, inputs=[Path(elig_path)],
                     params={"sources": ["api.npmjs.org last-month", "pypistats.org recent"],
                             "failed_lookups": sum(r["downloads_failed"] for r in rows)})
    print(f"downloads: {len(rows)} eligible packages -> {out}")
    return out


if __name__ == "__main__":
    {"eligibility": eligibility, "downloads": downloads}[sys.argv[1]](sys.argv[2])
