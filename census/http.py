"""Read-only HTTP client with an on-disk cache and per-host rate limits.

Every response body is cached under results/census/cache/http/<host>/<sha256(url)>.
Re-running a step therefore makes no new requests unless the cache is cleared.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

CACHE_DIR = Path("results/census/cache/http")
USER_AGENT = "mcp-lock-research/0.0.1 (academic census; contact: github.com/ftaakash)"

# Minimum seconds between requests to one host.
RATE = {
    "registry.npmjs.org": 0.2,
    "api.npmjs.org": 0.3,
    "pypi.org": 0.2,
    "pypistats.org": 0.6,
    "registry.modelcontextprotocol.io": 0.3,
    "api.github.com": 0.75,
    "raw.githubusercontent.com": 0.2,
    "api.osv.dev": 0.2,
}
DEFAULT_RATE = 0.5

_lock = threading.Lock()
_last: dict[str, float] = {}
_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT


class HttpError(Exception):
    def __init__(self, url: str, status: int):
        super().__init__(f"HTTP {status} for {url}")
        self.url = url
        self.status = status


def _wait(host: str) -> None:
    gap = RATE.get(host, DEFAULT_RATE)
    with _lock:
        now = time.monotonic()
        sleep = _last.get(host, 0.0) + gap - now
        _last[host] = max(now, _last.get(host, 0.0) + gap)
    if sleep > 0:
        time.sleep(sleep)


def _paths(url: str) -> tuple[Path, Path]:
    host = urlparse(url).netloc
    key = hashlib.sha256(url.encode()).hexdigest()
    base = CACHE_DIR / host / key[:2] / key
    return base.with_suffix(".body"), base.with_suffix(".meta.json")


def get(url: str, *, headers: dict | None = None, binary: bool = False, retries: int = 5,
        cache: bool = True) -> bytes | str:
    """GET url, returning the body. Raises HttpError on non-2xx (404s are cached too)."""
    body_p, meta_p = _paths(url)
    if cache and meta_p.exists():
        meta = json.loads(meta_p.read_text())
        if meta["status"] >= 400:
            raise HttpError(url, meta["status"])
        data = body_p.read_bytes()
        return data if binary else data.decode("utf-8", errors="replace")

    host = urlparse(url).netloc
    delay = 2.0
    for attempt in range(retries):
        _wait(host)
        try:
            r = _session.get(url, headers=headers or {}, timeout=60)
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504) or (
            r.status_code == 403 and "rate limit" in r.text.lower()
        ):
            reset = r.headers.get("Retry-After") or r.headers.get("x-ratelimit-reset")
            wait = delay
            if reset and reset.isdigit():
                val = int(reset)
                wait = max(1, val - int(time.time())) if val > 10**9 else val
            time.sleep(min(wait, 120))
            delay *= 2
            continue
        break
    else:
        raise HttpError(url, r.status_code)

    meta = {"url": url, "status": r.status_code, "fetched_utc": time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "etag": r.headers.get("ETag")}
    if cache and (r.ok or r.status_code in (404, 410)):
        body_p.parent.mkdir(parents=True, exist_ok=True)
        body_p.write_bytes(r.content)
        meta_p.write_text(json.dumps(meta))
    if not r.ok:
        raise HttpError(url, r.status_code)
    return r.content if binary else r.text


def get_json(url: str, **kw):
    return json.loads(get(url, **kw))


def post_json(url: str, body: dict, cache: bool = True):
    """POST a JSON body (e.g. OSV queries); cached by URL + canonical body."""
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"))
    body_p, meta_p = _paths(url + "#" + payload)
    if cache and meta_p.exists():
        meta = json.loads(meta_p.read_text())
        if meta["status"] >= 400:
            raise HttpError(url, meta["status"])
        return json.loads(body_p.read_bytes())
    host = urlparse(url).netloc
    delay = 2.0
    for attempt in range(5):
        _wait(host)
        try:
            r = _session.post(url, data=payload, headers={"Content-Type": "application/json"},
                              timeout=60)
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(delay)
            delay *= 2
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(delay)
            delay *= 2
            continue
        break
    if cache and (r.ok or r.status_code == 404):
        body_p.parent.mkdir(parents=True, exist_ok=True)
        body_p.write_bytes(r.content)
        meta_p.write_text(json.dumps({"url": url, "body": payload, "status": r.status_code,
                                      "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                   time.gmtime())}))
    if not r.ok:
        raise HttpError(url, r.status_code)
    return r.json()
