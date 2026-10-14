"""Offline, as-of-time replay of the frozen gate (PREREG §3.2, §3.4).

A *bundle* is a JSON object holding everything the gate would have fetched from the registries at
time `t` for one case. Building a bundle needs the network; replaying it does not. During replay
every network entry point (`census.http`) raises, and the gate's registry lookups are answered from
the bundle, so the frozen gate code (tag `prereg-v1`) runs unchanged on historical data.

Bundle fields:
  case_id, corpus, ecosystem, package, t (ISO 8601), command, cwd_files {relpath: text}
  versions        version records as census.versions returns them, already truncated to t
  lock            MCP-Lock entry or null
  registry_info   {name: {"exists": bool, "first_release": ISO|null}}
  osv             {"name@version": [{"id", "lowest_fix"}]} (advisories published <= t)
  identities      {version: identity | null}  (null = observed: no provenance)
  tools           {version: {"hash": str|null, "names": [...]} | {"too_large": true}}
  evaluable       {"S2": bool, "S3": bool, "S4": bool, "S5": bool}
  deps            {name: {version: node}} npm dependency nodes (gate/deptree.py), for H1 only
  dep_identities  {attestation_url: identity | null}, for H1 only
  files           {version: {filename: "sha256-..."}} every file of a PyPI release, for H3 only
  labels          free-form (malicious/benign, class, stratum, ...)

A signal marked not evaluable is disabled for that case (PREREG §3.2: no finding, counts as a miss).
"""

from __future__ import annotations

import contextlib
import json
import tempfile
from datetime import datetime
from pathlib import Path

from census import http, tarballs
from census import versions as V
from gate import core, deptree, s1, signals

SIGNALS_23 = ("S2", "S3", "S4", "S5")
# Findings that count as a detection (PREREG §2.1). gate unlocked / lookup_failed / unresolvable
# and info findings never count.
COUNTED_GATE_CHECKS = {"integrity_mismatch"}
# S1-S5 (PREREG §2.1) plus the exploratory Phase 5 hardening checks H1-H5.
COUNTED_SIGNALS = {"S1", "S2", "S3", "S4", "S5", "H1", "H2", "H3", "H4", "H5"}


class OfflineViolation(RuntimeError):
    pass


def _ts(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def systems(evaluable: dict, hardening: frozenset = frozenset()) -> dict[str, tuple[str, frozenset]]:
    """System id -> (S1 variant, enabled signals). G drops signals that are not evaluable.
    `hardening` (exploratory H1/H3 gate checks) is added to G and its ablations, never to S1-L/S1-C."""
    ok = frozenset(s for s in SIGNALS_23 if evaluable.get(s, True)) | hardening
    out = {"S1-L": ("literal", frozenset({"S1"})),
           "S1-C": ("charitable", frozenset({"S1"})),
           "G": ("charitable", frozenset({"S1"}) | ok)}
    for k in SIGNALS_23:
        out[f"G-{k}"] = ("charitable", frozenset({"S1"}) | (ok - {k}))
    return out


@contextlib.contextmanager
def offline(bundle: dict):
    """Answer every registry lookup from `bundle`; any real network call raises."""
    pkg, eco = bundle["package"], bundle["ecosystem"]
    # Phase 4 corpora: any lookup outside the bundle fails loudly. Only the Phase 5 command-shape
    # cases (corpus "ADV") may hit auxiliary names, which are answered conservatively and recorded.
    tolerant = bundle.get("corpus") == "ADV"
    saved = {}

    def patch(mod, name, fn):
        saved[(mod, name)] = getattr(mod, name)
        setattr(mod, name, fn)

    def no_net(*a, **k):
        raise OfflineViolation(f"network call during replay: {a[:1]}")

    def versions(name):
        if name != pkg:
            if not tolerant:
                raise OfflineViolation(f"versions for unexpected package {name}")
            # The gate parsed a different package than the attack's (e.g. an E11 `-p PKG bin` shape):
            # it never sees the real package, so it cannot resolve this one. Recorded, returns empty
            # (-> gate "unresolvable", which §2.1 does not count as a detection).
            bundle.setdefault("_aux_lookups", []).append(name)
            return []
        return [dict(v) for v in bundle["versions"]]

    def registry_info(e, name, now=None, age_days=30):
        info = (bundle.get("registry_info") or {}).get(name)
        if info is None:
            if not tolerant:
                raise OfflineViolation(f"registry_info for unexpected package {name}")
            # A multi-command shape (e.g. `npm install -g X && adv-notes`) can make S1 look up an
            # auxiliary token. Treat it as an existing, non-new package: conservative (it cannot add
            # an S1 detection) and recorded, so it never hides or fabricates a finding.
            bundle.setdefault("_aux_lookups", []).append(name)
            return {"exists": True, "first_release": None}
        return {"exists": info["exists"], "first_release": _ts(info.get("first_release"))}

    def osv_fixable(e, name, version):
        return list((bundle.get("osv") or {}).get(f"{name}@{version}", []))

    def identity(e, name, v):
        ids = bundle.get("identities") or {}
        if v["version"] not in ids:
            raise OfflineViolation(f"identity for {name}@{v['version']} not in bundle")
        return ids[v["version"]]

    def static_tools(e, name, v):
        t = (bundle.get("tools") or {}).get(v["version"])
        if t is None:
            raise OfflineViolation(f"tools for {name}@{v['version']} not in bundle")
        if t.get("too_large"):
            raise tarballs.TooLarge(f"{name}@{v['version']} archive over the size cap")
        return t["hash"], list(t["names"])

    patch(http, "get", no_net)
    patch(http, "get_json", no_net)
    patch(http, "post_json", no_net)
    patch(tarballs, "fetch", no_net)
    patch(V, "npm_versions" if eco == "npm" else "pypi_versions", versions)
    patch(s1, "registry_info", registry_info)
    patch(s1, "osv_fixable", osv_fixable)
    patch(signals, "_identity", identity)
    patch(signals, "static_tools", static_tools)

    def dep_versions(name, as_of=None):  # bundle data is already truncated to t
        if name not in (bundle.get("deps") or {}):
            raise OfflineViolation(f"dependency {name} not in bundle")
        return {v: dict(n) for v, n in bundle["deps"][name].items()}

    def dep_identity(node):
        ids = bundle.get("dep_identities") or {}
        if node.get("attestation_url") not in ids:
            raise OfflineViolation(f"identity for {node.get('attestation_url')} not in bundle")
        return ids[node["attestation_url"]]

    def pypi_files(name, version):
        files = (bundle.get("files") or {}).get(version)
        if files is None:
            raise OfflineViolation(f"file list for {name}=={version} not in bundle")
        return dict(files)

    patch(deptree, "versions", dep_versions)
    patch(deptree, "_identity", dep_identity)
    patch(signals, "pypi_files", pypi_files)
    try:
        yield
    finally:
        for (mod, name), fn in saved.items():
            setattr(mod, name, fn)


def detected(decision: dict, block_only: bool = False) -> bool:
    """PREREG §2.1: block/warn caused by at least one counted finding."""
    levels = {"block"} if block_only else {"block", "warn"}
    if decision["decision"] not in levels:
        return False
    for f in decision["findings"]:
        if f["severity"] not in levels:
            continue
        if f["signal"] in COUNTED_SIGNALS or f["check"] in COUNTED_GATE_CHECKS:
            return True
    return False


def run(bundle: dict, hardening: frozenset = frozenset(), suggest: bool = False) -> dict:
    """Evaluate one bundle with every system. Returns {system: decision dict + detection flags}.
    `suggest` adds verified safer alternatives (gate/suggest.py) to G only; decisions are unchanged."""
    t = _ts(bundle["t"])
    out = {}
    with tempfile.TemporaryDirectory() as d:
        cwd = Path(d)
        for rel, text in (bundle.get("cwd_files") or {}).items():
            p = cwd / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        lock_path = None
        if bundle.get("lock"):
            lock_path = cwd / ".mcplock-replay.json"
            lock_path.write_text(json.dumps({"lockfileVersion": 1, "servers": {
                bundle["package"]: bundle["lock"]}}), encoding="utf-8")
        with offline(bundle):
            for sid, (variant, enabled) in systems(bundle.get("evaluable") or {}, hardening).items():
                cfg = (s1.S1Config.charitable if variant == "charitable"
                       else s1.S1Config.literal)(now=t)
                dec = core.evaluate(bundle["command"], cwd, lock_path, cfg, enabled,
                                    suggest=suggest and sid == "G").to_dict()
                dec["detected"] = detected(dec)
                dec["detected_block"] = detected(dec, block_only=True)
                dec["enabled"] = sorted(enabled)
                out[sid] = dec
    return out


BASELINE_SYSTEMS = ("S1-L", "S1-C")
ROOT = Path(__file__).resolve().parents[1]


def write_split(rows: list[dict], name: str, inputs: list) -> tuple[Path, Path]:
    """Baseline and candidate results go to separate folders (PREREG §2)."""
    from census import provenance
    paths = []
    for group, keep in (("baseline", lambda s: s in BASELINE_SYSTEMS),
                        ("candidate", lambda s: s not in BASELINE_SYSTEMS)):
        out = ROOT / "results" / group / "phase4" / "runs" / f"{name}.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as g:
            for r in rows:
                g.write(json.dumps({**r, "systems": {k: v for k, v in r["systems"].items()
                                                     if keep(k)}}) + "\n")
        provenance.write(out, inputs=inputs, params={"cases": len(rows), "group": group})
        paths.append(out)
    return paths[0], paths[1]


def main():
    import argparse
    import gzip

    ap = argparse.ArgumentParser(description="Replay bundles offline with every system")
    ap.add_argument("bundles", help="bundles .jsonl(.gz)")
    ap.add_argument("name", help="run name, e.g. B or R-M or R-S")
    a = ap.parse_args()
    opener = gzip.open if a.bundles.endswith(".gz") else open
    rows = []
    with opener(a.bundles, "rt", encoding="utf-8") as f:
        for line in f:
            b = json.loads(line)
            rows.append({"case_id": b["case_id"], "corpus": b["corpus"],
                         "ecosystem": b["ecosystem"], "package": b["package"],
                         "labels": b.get("labels") or {}, "evaluable": b.get("evaluable") or {},
                         "lock_provenance": bool((b.get("lock") or {}).get("provenance")),
                         "systems": run(b)})
            if len(rows) % 500 == 0:
                print(f"{len(rows)} replayed", flush=True)
    base, cand = write_split(rows, a.name, [a.bundles])
    print(f"replayed {len(rows)} cases -> {base} | {cand}")


if __name__ == "__main__":
    main()
