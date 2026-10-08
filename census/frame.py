"""Collect the sampling frame: F1 (official MCP registry) and F2 (GitHub MCP configs).

Usage:
    python -m census.frame f1
    python -m census.frame f2
    python -m census.frame build
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from census import http, launch, provenance

OUT = Path("results/census/frame")
REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers"

F2_QUERIES = [
    "filename:.mcp.json npx", "filename:.mcp.json uvx",
    "filename:claude_desktop_config.json npx", "filename:claude_desktop_config.json uvx",
    "filename:mcp.json path:.vscode npx", "filename:mcp.json path:.vscode uvx",
    "filename:mcp.json path:.cursor npx", "filename:mcp.json path:.cursor uvx",
]
SEARCH_GAP = 6.6  # code search: 10 requests/min
MAX_SIZE = 384_000  # GitHub code search indexes files < 384 KB


# ---------------------------------------------------------------- F1
def collect_f1() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, cursor, pages = [], None, 0
    while True:
        url = f"{REGISTRY}?limit=100&version=latest"
        if cursor:
            url += "&cursor=" + quote(cursor, safe="")
        data = http.get_json(url, cache=False)
        pages += 1
        for item in data.get("servers", []):
            srv = item.get("server", {})
            meta = item.get("_meta", {}).get("io.modelcontextprotocol.registry/official", {})
            for pkg in srv.get("packages") or []:
                rt = (pkg.get("registryType") or "").lower()
                if rt not in {"npm", "pypi"}:
                    continue
                ident = pkg.get("identifier", "")
                rows.append({
                    "source": "F1",
                    "server": srv.get("name"),
                    "server_version": srv.get("version"),
                    "status": meta.get("status"),
                    "ecosystem": rt,
                    "package": ident.lower() if rt == "npm" else launch.pep503(ident),
                    "identifier": ident,
                    "pkg_version": pkg.get("version"),
                    "runtime_hint": pkg.get("runtimeHint"),
                    "transport": (pkg.get("transport") or {}).get("type"),
                    "package_arguments": pkg.get("packageArguments"),
                    "runtime_arguments": pkg.get("runtimeArguments"),
                    "environment_variables": pkg.get("environmentVariables"),
                    "repository": (srv.get("repository") or {}).get("url"),
                })
        cursor = data.get("metadata", {}).get("nextCursor")
        if not cursor:
            break
    out = OUT / "f1_registry.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    provenance.write(out, params={"url": REGISTRY, "pages": pages, "rows": len(rows)})
    print(f"F1: {pages} pages, {len(rows)} npm/pypi package rows -> {out}")
    return out


# ---------------------------------------------------------------- F2
def _gh_token() -> str:
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


class Searcher:
    def __init__(self):
        self.headers = {"Authorization": "Bearer " + _gh_token(),
                        "Accept": "application/vnd.github.text-match+json",
                        "X-GitHub-Api-Version": "2022-11-28"}
        self.last = 0.0
        self.calls = 0

    def search(self, q: str, page: int = 1, per_page: int = 100) -> dict:
        url = (f"https://api.github.com/search/code?q={quote(q)}&per_page={per_page}"
               f"&page={page}")
        body_p, meta_p = http._paths(url)
        if not meta_p.exists():
            gap = self.last + SEARCH_GAP - time.monotonic()
            if gap > 0:
                time.sleep(gap)
            self.last = time.monotonic()
            self.calls += 1
        for attempt in range(6):
            try:
                return http.get_json(url, headers=self.headers)
            except http.HttpError as e:
                if e.status in (403, 422) and attempt < 5:
                    time.sleep(60)
                    continue
                raise
        raise RuntimeError(url)


def _partitions(s: Searcher, q: str, lo: int, hi: int, out: list) -> None:
    total = s.search(f"{q} size:{lo}..{hi}", per_page=1).get("total_count", 0)
    if total == 0:
        return
    if total <= 1000 or hi - lo < 8:
        out.append((lo, hi, total))
        return
    mid = (lo + hi) // 2
    _partitions(s, q, lo, mid, out)
    _partitions(s, q, mid + 1, hi, out)


def collect_f2() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    s = Searcher()
    hits: dict[tuple[str, str], dict] = {}
    log = []
    for q in F2_QUERIES:
        parts: list = []
        _partitions(s, q, 0, MAX_SIZE, parts)
        got = 0
        for lo, hi, total in parts:
            for page in range(1, min(10, (total + 99) // 100) + 1):
                data = s.search(f"{q} size:{lo}..{hi}", page=page)
                items = data.get("items", [])
                for it in items:
                    repo = it["repository"]
                    key = (repo["full_name"], it["path"])
                    frags = "\n".join(tm.get("fragment", "") for tm in it.get("text_matches", []))
                    ref = parse_qs(urlparse(it.get("url", "")).query).get("ref", [""])[0]
                    rec = hits.setdefault(key, {"repo": repo["full_name"], "path": it["path"],
                                                "ref": ref, "fork": repo.get("fork", False),
                                                "fragments": [], "queries": []})
                    rec["fragments"].append(frags)
                    rec["queries"].append(q)
                got += len(items)
                if len(items) < 100:
                    break
        log.append({"query": q, "partitions": len(parts),
                    "reported_total": sum(p[2] for p in parts), "items_retrieved": got})
        print(f"F2 {q!r}: {len(parts)} partitions, {got} items, {s.calls} search calls so far",
              flush=True)

    # Parse launches: snippet first, raw file when the snippet yields nothing.
    raw_fetches = 0
    for rec in hits.values():
        text = "\n".join(rec["fragments"])
        launches = launch.parse_fragment(text)
        mode = "fragment"
        if not launches and rec["ref"]:
            raw = (f"https://raw.githubusercontent.com/{rec['repo']}/{rec['ref']}/"
                   f"{quote(rec['path'])}")
            try:
                launches = launch.parse_config_text(http.get(raw))
                mode = "raw"
                raw_fetches += 1
            except http.HttpError:
                mode = "raw_failed"
        rec["launches"] = [lt.__dict__ for lt in launches]
        rec["parse_mode"] = mode
        del rec["fragments"]

    out = OUT / "f2_github.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for rec in hits.values():
            f.write(json.dumps(rec) + "\n")
    (OUT / "f2_query_log.json").write_text(json.dumps(log, indent=2))
    provenance.write(out, params={"queries": F2_QUERIES, "search_calls": s.calls,
                                  "raw_fetches": raw_fetches, "files": len(hits)},
                     note="GitHub code search results with text-match snippets; "
                          "raw file fetched only when the snippet did not parse.")
    print(f"F2: {len(hits)} files, {raw_fetches} raw fetches -> {out}")
    return out


# ---------------------------------------------------------------- frame
def build() -> Path:
    f1 = [json.loads(x) for x in open(OUT / "f1_registry.jsonl", encoding="utf-8")]
    f2 = [json.loads(x) for x in open(OUT / "f2_github.jsonl", encoding="utf-8")]
    frame: dict[tuple[str, str], dict] = {}

    def entry(eco, pkg):
        return frame.setdefault((eco, pkg), {
            "ecosystem": eco, "package": pkg, "in_f1": False, "f1_servers": [],
            "f2_files_unpinned": 0, "f2_files_pinned": 0, "f2_repos": set(), "f1_launch": None})

    for r in f1:
        if r["status"] not in (None, "active"):
            continue
        e = entry(r["ecosystem"], r["package"])
        e["in_f1"] = True
        e["f1_servers"].append(r["server"])
        if e["f1_launch"] is None:
            e["f1_launch"] = {k: r[k] for k in ("identifier", "runtime_hint", "package_arguments",
                                                "runtime_arguments", "environment_variables")}
    for rec in f2:
        if rec.get("fork"):
            continue
        seen = set()
        for lt in rec["launches"]:
            key = (lt["ecosystem"], lt["package"], lt["pinned"])
            if key in seen:
                continue
            seen.add(key)
            e = entry(lt["ecosystem"], lt["package"])
            e["f2_files_pinned" if lt["pinned"] else "f2_files_unpinned"] += 1
            e["f2_repos"].add(rec["repo"])

    rows = []
    for e in frame.values():
        e["f2_repos"] = len(e["f2_repos"])
        e["f1_servers"] = sorted(set(e["f1_servers"]))
        # Frame criterion: seen launched unpinned on GitHub, or listed in the registry
        # with an npx/uvx-style runtime (registry launch lines are not version-checked).
        e["in_frame"] = e["f2_files_unpinned"] > 0 or e["in_f1"]
        rows.append(e)
    rows.sort(key=lambda r: (r["ecosystem"], r["package"]))
    day = time.strftime("%Y-%m-%d")
    out = OUT / f"frame_{day}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    eco = defaultdict(int)
    for r in rows:
        if r["in_frame"]:
            eco[r["ecosystem"]] += 1
    provenance.write(out, inputs=[OUT / "f1_registry.jsonl", OUT / "f2_github.jsonl"],
                     params={"in_frame_by_ecosystem": dict(eco), "total_rows": len(rows)})
    print(f"frame: {len(rows)} packages, in frame {dict(eco)} -> {out}")
    return out


if __name__ == "__main__":
    {"f1": collect_f1, "f2": collect_f2, "build": build}[sys.argv[1]]()
