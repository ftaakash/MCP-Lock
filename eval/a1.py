"""Settings of pre-registration addendum A1 (docs/PREREG_ADDENDUM_AGE.md).

Active only when the environment variable MCPLOCK_A1=1 is set, so every original Phase 4 command keeps its registered
behaviour. With it set: post-freeze window, fresh HTTP cache, new data pins, new seed, separate output folders.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

ACTIVE = os.environ.get("MCPLOCK_A1") == "1"

WINDOW_START = datetime(2026, 10, 9, tzinfo=UTC)
WINDOW_END = datetime(2026, 11, 7, 23, 59, 59, tzinfo=UTC)
SEED = 20261114
OSV_COMMIT = "016024d631828d2b6827bee160888f7205e42635"  # ossf/malicious-packages, fetched 2026-11-14
HTTP_CACHE = "results/census/cache_a1/http"  # fresh: the Phase 2/4 cache predates the window
CENSUS_DIR = "results/census/a1"  # versions and extractions of the 2,000 sample packages, as of now
OUT_DIR = "results/candidate/a1"
MAL_WORK = "work_a1"  # subfolder of the mcplock-mal volume
