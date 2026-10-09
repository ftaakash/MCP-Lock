"""Common finding type for all gate signals."""

from __future__ import annotations

from dataclasses import asdict, dataclass

SEVERITY_ORDER = {"info": 0, "warn": 1, "block": 2}


@dataclass(frozen=True)
class Finding:
    signal: str  # "S1".."S5", or "gate"
    check: str  # e.g. "name_proximity", "provenance_lost"
    severity: str  # "info" | "warn" | "block"
    package: str | None
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)
