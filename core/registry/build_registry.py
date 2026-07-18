"""Generate checkpoints.yaml from docs/audit-entries.csv.

Run once (and after CSV edits): `python -m core.registry.build_registry`.
The generated YAML is committed and is the runtime source of truth; this script
only regenerates it. Derived fields (id/source/automation/collector) use
heuristics on the CSV's "Automation Endpoint" text and are safe to hand-edit
in the YAML afterwards.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "docs" / "audit-entries.csv"
YAML_PATH = Path(__file__).resolve().parent / "checkpoints.yaml"

TOOL_SLUG = {
    "GA4": "ga4",
    "GTM": "gtm",
    "GTM SS": "gtm_ss",
    "Google Ads": "google_ads",
    "BigQuery": "bigquery",
    "Reporting": "reporting",
}

# phrases in the endpoint column that mean "no API / UI-only / manual"
UI_ONLY = re.compile(
    r"not exposed|ui-only|not via api|document manually|verify in ui|manual",
    re.IGNORECASE,
)
# phrases that mean "checkable from a public crawl / network inspection"
CRAWL_HINTS = re.compile(
    r"crawl|source|network|inspect network|view-source|tag assistant",
    re.IGNORECASE,
)


def _slug(text: str, maxlen: int = 48) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:maxlen].rstrip("_")


def _collector(tool: str, endpoint: str, category: str) -> str | None:
    e = endpoint.lower()
    if tool == "GA4":
        if "data api" in e or "runreport" in e or "runrealtime" in e:
            return "ga4_data"
        if "admin api" in e:
            return "ga4_admin"
        if "bigquery" in e:
            return "bigquery"
        if CRAWL_HINTS.search(endpoint):
            return "crawl"
        return "ga4_admin"
    if tool == "GTM":
        if CRAWL_HINTS.search(endpoint) and "gtm api" not in e:
            return "crawl"
        return "gtm"
    if tool == "GTM SS":
        return "gcp_infra"
    if tool == "Google Ads":
        return "google_ads"
    if tool == "BigQuery":
        return "bigquery"
    return None


def _source_and_automation(endpoint: str) -> tuple[str, str]:
    if UI_ONLY.search(endpoint):
        return "ui", "manual"
    if CRAWL_HINTS.search(endpoint) and "api" not in endpoint.lower():
        return "crawl", "auto"
    if "api" in endpoint.lower():
        return "api", "auto"
    return "ui", "semi"


def build() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tool = (row["Tool"] or "").strip()
            checkpoint = (row["Checkpoint"] or "").strip()
            endpoint = (row["Automation Endpoint"] or "").strip()
            category = (row["Category"] or "").strip()
            if not checkpoint:
                continue

            base = f"{TOOL_SLUG.get(tool, _slug(tool))}.{_slug(checkpoint)}"
            cid = base
            n = 2
            while cid in seen:
                cid = f"{base}_{n}"
                n += 1
            seen.add(cid)

            collector = _collector(tool, endpoint, category)
            source, automation = _source_and_automation(endpoint)
            if collector == "crawl":
                # a checkpoint served by the public crawl collector is, by
                # definition, a crawl-source check
                source, automation = "crawl", "auto"
            rows.append(
                {
                    "id": cid,
                    "category": category,
                    "tool": tool,
                    "description": (row["Description"] or "").strip(),
                    "how_to_check": (row["How to Check"] or "").strip(),
                    "source": source,
                    "automation": automation,
                    "collector": collector,
                    "api_ref": endpoint,
                    "severity": (row["Severity"] or "").strip().lower() or "medium",
                }
            )
    return rows


def main() -> None:
    rows = build()
    with YAML_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            {"checkpoints": rows},
            f,
            sort_keys=False,
            allow_unicode=True,
            width=100,
        )
    print(f"Wrote {len(rows)} checkpoints to {YAML_PATH}")


if __name__ == "__main__":
    main()
