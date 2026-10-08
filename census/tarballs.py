"""Download package archives and extract source files safely (never executed).

npm: .tgz from the packument's dist.tarball (integrity verified against dist.integrity).
PyPI: prefer a pure wheel, else the sdist; sha256 verified against the JSON API digest.
Only text source files are extracted (js/mjs/cjs/ts/py/json), with path-traversal and
symlink members rejected and a per-file size cap.
"""

from __future__ import annotations

import base64
import hashlib
import io
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from census import http

TARBALLS = Path("results/census/cache/tarballs")
SRC = Path("results/census/cache/src")
KEEP = re.compile(r"\.(js|mjs|cjs|ts|mts|cts|py|json)$", re.I)
MAX_FILE = 8 * 1024 * 1024
SKIP_DIRS = {"node_modules", "test", "tests", "__tests__", "examples", "example", "docs",
             ".git", "coverage", "benchmark", "benchmarks", "fixtures"}


class IntegrityError(Exception):
    pass


def _safe_name(name: str) -> PurePosixPath | None:
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or not p.parts:
        return None
    if any(part in SKIP_DIRS for part in p.parts[:-1]):
        return None
    if p.name.endswith((".d.ts", ".map", ".min.js")) or p.name == "package-lock.json":
        return None
    return p


def check_integrity(data: bytes, integrity: str | None = None, sha256: str | None = None,
                    shasum: str | None = None) -> str:
    if integrity and integrity.startswith("sha512-"):
        got = base64.b64encode(hashlib.sha512(data).digest()).decode()
        if got != integrity.split("-", 1)[1]:
            raise IntegrityError("sha512 mismatch")
        return integrity
    if sha256:
        if hashlib.sha256(data).hexdigest() != sha256:
            raise IntegrityError("sha256 mismatch")
        return "sha256-" + sha256
    if shasum:
        if hashlib.sha1(data).hexdigest() != shasum:
            raise IntegrityError("sha1 mismatch")
        return "sha1-" + shasum
    return "unverified"


MAX_ARCHIVE = 150 * 1024 * 1024  # archives above this are recorded as too_large, not analysed


class TooLarge(Exception):
    pass


def _download(url: str) -> bytes:
    """Streaming download with a size cap and the shared per-host rate limit."""
    from urllib.parse import urlparse
    http._wait(urlparse(url).netloc)
    with http._session.get(url, stream=True, timeout=(30, 120)) as r:
        if r.status_code != 200:
            raise http.HttpError(url, r.status_code)
        if int(r.headers.get("Content-Length") or 0) > MAX_ARCHIVE:
            raise TooLarge(url)
        buf = bytearray()
        for chunk in r.iter_content(1 << 20):
            buf += chunk
            if len(buf) > MAX_ARCHIVE:
                raise TooLarge(url)
        return bytes(buf)


def fetch(url: str, key: str, **digests) -> tuple[Path, str]:
    dest = TARBALLS / key
    if dest.exists():
        data = dest.read_bytes()
    else:
        data = _download(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return dest, check_integrity(data, **digests)


def extract(archive: Path, key: str) -> Path:
    """Extract kept source files into SRC/key and return that directory."""
    out = SRC / key
    marker = out / ".extracted"
    if marker.exists():
        return out
    out.mkdir(parents=True, exist_ok=True)
    data = archive.read_bytes()
    if archive.name.endswith((".whl", ".zip")):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                p = _safe_name(info.filename)
                if p is None or info.is_dir() or not KEEP.search(p.name):
                    continue
                if info.file_size > MAX_FILE or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue
                _write(out, p, zf.read(info))
    else:
        mode = "r:gz" if archive.name.endswith((".tgz", ".tar.gz")) else "r:*"
        with tarfile.open(fileobj=io.BytesIO(data), mode=mode) as tf:
            for m in tf.getmembers():
                if not m.isfile():
                    continue  # skips symlinks, hardlinks, devices
                p = _safe_name(m.name)
                if p is None or not KEEP.search(p.name) or m.size > MAX_FILE:
                    continue
                f = tf.extractfile(m)
                if f:
                    _write(out, p, f.read())
    marker.write_text("ok")
    return out


def _write(root: Path, rel: PurePosixPath, data: bytes) -> None:
    dest = (root / Path(*rel.parts)).resolve()
    if not str(dest).startswith(str(root.resolve())):
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
