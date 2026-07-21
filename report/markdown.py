"""Full Markdown audit report — the shareable deliverable, distinct from the
concise terminal view. Built with plain Python (no template engine)."""

from __future__ import annotations

import re

from core.models.enums import Status
from core.models.result import AuditResult

_ICON = {"pass": "✅", "fail": "❌", "warn": "⚠️", "na": "➖"}
_ORDER = {Status.FAIL: 0, Status.WARN: 1, Status.PASS: 2, Status.NA: 3}


def executive_summary(brief: str) -> str:
    """Extract just the '## Executive summary' section from the analyst brief
    (for the terminal). Falls back to the whole brief if not found."""
    m = re.search(r"##\s*Executive summary\s*(.+?)(?:\n##\s|\Z)", brief, re.S | re.I)
    return m.group(1).strip() if m else brief.strip()


def render_markdown(result: AuditResult, generated_at: str = "") -> str:
    r = result
    out: list[str] = [
        f"# Measurement Audit — {r.target}",
        "",
        f"_{('Generated ' + generated_at + ' · ') if generated_at else ''}"
        f"Adwize Audit ({r.edition} edition, public-source scan)_",
        "",
        f"**Grade {r.scores.grade} — {r.scores.overall}/100**",
        "",
        "Status counts: " + ", ".join(f"{k}={v}" for k, v in r.scores.counts.items()),
    ]

    if r.scores.by_category:
        out += ["", "## Scores by category", "", "| Category | Score |", "|---|---|"]
        out += [f"| {c} | {s}/100 |" for c, s in sorted(r.scores.by_category.items())]

    if r.summary:
        out += ["", "## Analysis", "", r.summary]
    elif r.analysis_status and r.analysis_status != "ran":
        out += ["", "## Analysis", "", f"_Analysis agent not run ({r.analysis_status})._"]

    for name, body in (r.documents or {}).items():
        out += ["", f"## {name.replace('_', ' ').title()}", "", body]

    out += ["", "## Findings", ""]
    for f in sorted(
        r.findings, key=lambda f: (_ORDER[f.status], -f.severity.weight, f.checkpoint_id)
    ):
        out.append(f"### {_ICON[f.status.value]} {f.title}")
        out.append(
            f"`{f.checkpoint_id}` · {f.category} · **{f.severity.value}** · {f.status.value}"
        )
        if f.detail:
            out.append("")
            out.append(f.detail)
        if f.affected_items:
            items_str = ", ".join(
                " / ".join(f"{k}={v}" for k, v in item.items())
                if isinstance(item, dict)
                else str(item)
                for item in f.affected_items
            )
            out.append(f"- Affected: {items_str}")
        if f.remediation_hint:
            out.append(f"- How to check / fix: {f.remediation_hint}")
        out.append("")

    out += _inventory(result)
    out += _scoring_methodology()
    return "\n".join(out).rstrip() + "\n"


def _scoring_methodology() -> list[str]:
    """Appendix explaining how the score and grade are calculated."""
    return [
        "",
        "## Scoring methodology",
        "",
        "The audit starts at **100 points** and deducts penalties for each failing or warning check:",
        "",
        "| Severity | FAIL penalty | WARN penalty |",
        "|----------|-------------|-------------|",
        "| Critical | -25 | -12 |",
        "| High | -12 | -6 |",
        "| Medium | -5 | -2 |",
        "| Low | -2 | -1 |",
        "| Info | 0 | 0 |",
        "",
        "Grade bands: **A** >= 90, **B** >= 75, **C** >= 60, **D** >= 40, **E** < 40.",
        "",
        "Info-severity checks are purely informational (inventory, server-side detection) and do not affect the score.",
    ]


def _inventory(result: AuditResult) -> list[str]:
    """Measurement-inventory appendix from the crawl signals."""
    sig = result.snapshots[0].data if result.snapshots else {}
    if not sig:
        return []
    cs = sig.get("container_summary", {})
    events = cs.get("events", [])
    vendors = ", ".join(f"{v['name']} ({v['category']})" for v in sig.get("vendors", [])) or "none"
    lines = ["", "## Measurement inventory", ""]
    pages = sig.get("pages")
    if pages:
        lines.append(f"- **Pages crawled ({len(pages)}):** " + ", ".join(p["url"] for p in pages))
    lines.append(
        f"- **GTM containers:** {', '.join(sig.get('tag_ids', {}).get('gtm', [])) or 'none'}"
    )
    lines.append(f"- **Measurement IDs:** {', '.join(cs.get('measurement_ids', [])) or 'none'}")
    lines.append(f"- **Vendors detected:** {vendors}")
    lines.append(
        f"- **Ecommerce:** {cs.get('ecommerce')} · "
        f"**Enhanced conversions:** {cs.get('enhanced_conversions')} · "
        f"**Custom HTML tags:** {cs.get('custom_html_count')}"
    )
    consent = sig.get("consent", {})
    lines.append(
        f"- **Consent:** CMPs={consent.get('cmps') or 'none'}, accepted={consent.get('accepted')}"
    )
    ck = sig.get("cookies", {})
    lines.append(
        f"- **Cookies:** {ck.get('total', 0)} total, {ck.get('third_party', 0)} third-party"
    )
    if events:
        lines += [
            "",
            f"### GA4 events configured ({len(events)})",
            "",
            ", ".join(f"`{e}`" for e in events),
        ]
    return lines
