"""Parse the PUBLIC GTM container that Google serves at
`googletagmanager.com/gtm.js?id=GTM-XXXX`.

The published container carries each tag's compiled `function` (e.g. `__gaawe`)
plus its `vtp_*` parameters (event name, measurement id, ecommerce/consent
flags). That is a rich, zero-access view of what a container fires. We extract
it into a normalized summary the crawl checks reason over.

The function→type map, kept params, type groups, and id pattern are NOT
hardcoded here — they come from the `gtm_functions` schema (YAML), so they can
be updated by the schema-maintainer agent without code changes.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from core.schemas import loader


@lru_cache
def _schema() -> dict[str, Any]:
    s = loader.load("gtm_functions")
    return {
        "functions": s.get("functions", {}),
        "custom_prefix": s.get("custom_template_prefix", "__cvt_"),
        "groups": {k: set(v) for k, v in s.get("type_groups", {}).items()},
        "keep_params": set(s.get("keep_params", [])),
        "measurement_id": re.compile(s.get("measurement_id_pattern", r"\bG-[A-Z0-9]{6,}\b")),
    }


def _meta(function: str) -> tuple[str, str, str]:
    s = _schema()
    m = s["functions"].get(function)
    if m:
        return m["type"], m["vendor"], m["purpose"]
    if function.startswith(s["custom_prefix"]):
        return "cvt_template", "custom", "Custom template"
    return function.lstrip("_"), "custom", "Custom template"


def _extract_json_array(text: str, key: str) -> list | None:
    """Bracket-match the JSON array that follows `"<key>":`."""
    m = re.search(rf'"{key}"\s*:\s*\[', text)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except (json.JSONDecodeError, ValueError):
                    return None
    return None


def _scalar(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)):
        return v
    return None


def _summarize(tags: list[dict], gtm_js: str) -> dict[str, Any]:
    s = _schema()
    ga4_config, ga4_event = (
        s["groups"].get("ga4_config", set()),
        s["groups"].get("ga4_event", set()),
    )
    ads_types, fl_types = s["groups"].get("ads", set()), s["groups"].get("floodlight", set())

    events: list[str] = []
    measurement_ids: set[str] = set()
    ecommerce = user_properties = enhanced_conversions = False
    custom_html = 0
    paused_count = 0
    vendors: set[str] = set()
    type_counts: dict[str, int] = {}
    event_tag_events: list[str] = []

    for t in tags:
        typ = t["type"]
        vendors.add(t["vendor"])
        type_counts[typ] = type_counts.get(typ, 0) + 1
        p = t.get("params", {})
        if typ in ga4_event:
            name = p.get("vtp_eventName")
            if isinstance(name, str) and name:
                events.append(name)
                event_tag_events.append(name)
        if typ == "html":
            custom_html += 1
        if typ == "paused":
            paused_count += 1
        if p.get("vtp_sendEcommerceData") is True:
            ecommerce = True
        if p.get("vtp_enableUserProperties") is True:
            user_properties = True
        if p.get("vtp_enableEuid") is True or p.get("vtp_enhancedUserId") is True:
            enhanced_conversions = True
        for key in ("vtp_measurementId", "vtp_tagId", "vtp_measurementIdOverride"):
            val = p.get(key)
            if isinstance(val, str):
                measurement_ids.update(s["measurement_id"].findall(val))

    if not measurement_ids:
        measurement_ids.update(s["measurement_id"].findall(gtm_js))

    # Detect duplicate GA4 event tags (same event name fired by multiple tags)
    from collections import Counter

    event_counts = Counter(event_tag_events)
    duplicate_events = sorted(e for e, c in event_counts.items() if c > 1)

    return {
        "events": sorted(set(events)),
        "event_tag_count": sum(1 for t in tags if t["type"] in ga4_event),
        "measurement_ids": sorted(measurement_ids),
        "ecommerce": ecommerce,
        "user_properties": user_properties,
        "enhanced_conversions": enhanced_conversions,
        "custom_html_count": custom_html,
        "paused_count": paused_count,
        "duplicate_event_names": duplicate_events,
        "has_ga4": any(t["type"] in ga4_config | ga4_event for t in tags),
        "has_ads": any(t["type"] in ads_types for t in tags),
        "has_floodlight": any(t["type"] in fl_types for t in tags),
        "vendors": sorted(v for v in vendors if v != "custom"),
        "type_counts": type_counts,
    }


def _analyze_variables(gtm_js: str) -> dict[str, Any]:
    """Analyze macros (variables) in the container: total count, type breakdown,
    and how many appear unreferenced by tags."""
    raw_macros = _extract_json_array(gtm_js, "macros") or []
    total = len(raw_macros)
    if not total:
        return {"total": 0, "unreferenced_count": 0, "type_counts": {}}

    type_counts: dict[str, int] = {}
    for m in raw_macros:
        if isinstance(m, dict):
            fn = (m.get("function") or "unknown").lstrip("_")
            type_counts[fn] = type_counts.get(fn, 0) + 1

    # Count macros referenced by tags (["macro", N] pattern in the tags section)
    tags_start = gtm_js.find('"tags":')
    if tags_start >= 0:
        tags_section = gtm_js[tags_start:]
        referenced = set(int(m) for m in re.findall(r'\["macro",(\d+)\]', tags_section))
    else:
        referenced = set(range(total))

    unreferenced = total - len(referenced & set(range(total)))
    return {
        "total": total,
        "unreferenced_count": max(0, unreferenced),
        "type_counts": type_counts,
    }


def parse_container(gtm_js: str, container_id: str) -> dict[str, Any]:
    """Parse gtm.js text into a normalized, enriched container snapshot."""
    keep = _schema()["keep_params"]
    raw_tags = _extract_json_array(gtm_js, "tags") or []
    tags: list[dict[str, Any]] = []
    for t in raw_tags:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") or ""
        typ, vendor, purpose = _meta(fn)
        params = {k: _scalar(v) for k, v in t.items() if k in keep}
        tags.append(
            {"function": fn, "type": typ, "vendor": vendor, "purpose": purpose, "params": params}
        )

    return {
        "parsed": bool(raw_tags),
        "id": container_id,
        "tag_count": len(tags),
        "tags": tags,
        "variables": _analyze_variables(gtm_js),
        **_summarize(tags, gtm_js),
    }
