"""Shrink and sanitise tool results before they reach the LLM.

Large payloads cost tokens and make models miscount; PII should not leave your
infrastructure unless you decide it may.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

MASK = "***"


@dataclass
class Transform:
    max_items: int = 50
    """Lists longer than this are cut; the LLM is told how many were dropped."""

    max_chars: int = 12_000
    """Hard cap on the serialised result."""

    mask_fields: list[str] = field(default_factory=list)
    """Glob patterns of keys to replace with ``***`` (e.g. ``"*phone*"``)."""

    drop_fields: list[str] = field(default_factory=list)
    """Glob patterns of keys to remove entirely."""

    def apply(self, data: Any) -> Any:
        return self._walk(data)

    def serialise(self, data: Any) -> str:
        text = json.dumps(self.apply(data), ensure_ascii=False, default=str)
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + f"... [truncated, {len(text)} chars total]"
        return text

    def _walk(self, data: Any) -> Any:
        if isinstance(data, dict):
            out: dict[str, Any] = {}
            for k, v in data.items():
                key = str(k).lower()
                if any(fnmatch(key, p.lower()) for p in self.drop_fields):
                    continue
                if any(fnmatch(key, p.lower()) for p in self.mask_fields):
                    out[k] = MASK
                else:
                    out[k] = self._walk(v)
            return out
        if isinstance(data, list):
            items = [self._walk(v) for v in data[: self.max_items]]
            if len(data) > self.max_items:
                items.append({"_truncated": f"{len(data) - self.max_items} more items omitted"})
            return items
        return data
