"""Martech/vendor detection from public signals (page HTML + network beacons).

The "technologies" surface (à la TagStack): broadens the audit beyond Google so
analysts see the whole measurement/advertising stack. Signatures live in the
`vendors` schema (YAML) — not hardcoded — so the schema-maintainer agent can add
vendors without code changes.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from core.schemas import loader


@lru_cache
def _compiled() -> list[tuple[str, str, re.Pattern[str]]]:
    out = []
    for v in loader.load("vendors").get("vendors", []):
        out.append((v["name"], v["category"], re.compile(v["pattern"], re.IGNORECASE)))
    return out


def detect(html: str, request_urls: list[str]) -> list[dict[str, Any]]:
    """Return detected vendors as [{name, category}], sorted by category/name."""
    haystack = html + "\n" + "\n".join(request_urls)
    found = [
        {"name": name, "category": cat} for name, cat, pat in _compiled() if pat.search(haystack)
    ]
    return sorted(found, key=lambda v: (v["category"], v["name"]))
