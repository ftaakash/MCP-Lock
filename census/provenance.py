"""Write a provenance JSON (command, commit, timestamp, input hashes) next to every result."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path


def git_commit() -> str:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_hash(p: Path) -> tuple[str, str]:
    if not p.exists() and Path(str(p) + ".gz").exists():
        p = Path(str(p) + ".gz")
    return str(p).replace("\\", "/"), sha256_file(p)


def write(result_path: Path, *, inputs: list[Path] = (), params: dict | None = None,
          note: str = "") -> Path:
    result_path = Path(result_path)
    prov = {
        "result": str(result_path).replace("\\", "/"),
        "result_sha256": sha256_file(result_path) if result_path.is_file() else None,
        "command": " ".join([Path(sys.executable).name, *sys.argv]),
        "commit": git_commit(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": sys.version.split()[0],
        "inputs": dict(_input_hash(Path(p)) for p in inputs),
        "params": params or {},
        "note": note,
    }
    out = result_path.with_name(result_path.name + ".provenance.json")
    out.write_text(json.dumps(prov, indent=2))
    return out


def open_text(path) -> object:
    """Open a results file, falling back to its .gz copy (large files are committed gzipped)."""
    import gzip
    path = Path(path)
    if path.exists():
        return open(path, encoding="utf-8")
    return gzip.open(str(path) + ".gz", "rt", encoding="utf-8")
