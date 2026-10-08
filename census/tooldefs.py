"""Canonical tool-definition form, hashing, and version-to-version diffs."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

OPAQUE = "$opaque"


@dataclass
class ToolDef:
    name: str
    description: str | None
    schema: object  # canonical JSON-able value, may contain OPAQUE leaves
    kind: str  # extraction pattern, e.g. "registerTool", "py_decorator"
    file: str = ""
    extra: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Plan §5: literal name AND (literal description OR resolvable schema)."""
        if not self.name:
            return False
        return bool(self.description and self.description.strip()) or has_resolved_leaf(
            self.schema)

    def canonical(self) -> dict:
        return {"name": self.name, "description": norm_ws(self.description),
                "schema": self.schema}


def norm_ws(s: str | None) -> str | None:
    return None if s is None else re.sub(r"\s+", " ", s).strip()


def has_resolved_leaf(v) -> bool:
    if v is None or v == OPAQUE:
        return False
    if isinstance(v, dict):
        return any(has_resolved_leaf(x) for k, x in v.items() if k != "$call") or (
            "$call" in v and v["$call"] not in ("", OPAQUE))
    if isinstance(v, list):
        return any(has_resolved_leaf(x) for x in v)
    return True


def canon_json(v) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def tools_hash(tools: list[ToolDef]) -> str:
    items = sorted(canon_json(t.canonical()) for t in tools)
    return hashlib.sha256("\n".join(items).encode()).hexdigest()


def dedupe(tools: list[ToolDef]) -> tuple[list[ToolDef], int]:
    """Keep one definition per tool name (first in file order); count conflicting duplicates."""
    seen: dict[str, ToolDef] = {}
    conflicts = 0
    for t in tools:
        if t.name in seen:
            if canon_json(seen[t.name].canonical()) != canon_json(t.canonical()):
                conflicts += 1
            continue
        seen[t.name] = t
    return list(seen.values()), conflicts


def diff(old: list[dict], new: list[dict]) -> dict:
    """Classify the change between two canonical tool lists (dicts from ToolDef.canonical)."""
    a = {t["name"]: t for t in old}
    b = {t["name"]: t for t in new}
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    desc = sorted(n for n in set(a) & set(b) if a[n]["description"] != b[n]["description"])
    schema = sorted(n for n in set(a) & set(b)
                    if canon_json(a[n]["schema"]) != canon_json(b[n]["schema"]))
    return {"added": added, "removed": removed, "description_changed": desc,
            "schema_changed": schema,
            "changed": bool(added or removed or desc or schema),
            "changed_names_or_desc": bool(added or removed or desc)}
