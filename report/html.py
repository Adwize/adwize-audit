"""Full static HTML audit report — the client-facing deliverable.

Self-contained (inline CSS + inline SVG, no external requests), theme-aware
(light/dark), and print-friendly (Save-as-PDF). Neutral theme via CSS custom
properties so brand tokens (`--brand`, `--accent`, fonts) drop in later without
touching the template. Built with plain Python — no template engine, no deps.
"""

from __future__ import annotations

import html
import re
from math import pi

from core.models.enums import Status
from core.models.result import AuditResult

_ORDER = {Status.FAIL: 0, Status.WARN: 1, Status.PASS: 2, Status.NA: 3}
_STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "na": "N/A"}


def _grade_color(grade: str) -> str:
    return {"A": "var(--ok)", "B": "var(--ok)", "C": "var(--warn)",
            "D": "var(--bad)", "E": "var(--bad)"}.get(grade, "var(--muted)")


def _score_color(score: int) -> str:
    return "var(--ok)" if score >= 75 else "var(--warn)" if score >= 50 else "var(--bad)"


_CSS = """
:root {
  --brand:#1f6feb; --accent:#0969da;
  --bg:#ffffff; --fg:#1a1a1a; --muted:#6b7280; --line:#e5e7eb; --card:#f9fafb;
  --ok:#1a7f37; --warn:#bf8700; --bad:#cf222e; --info:#6b7280;
  --font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#0d1117; --fg:#e6edf3; --muted:#9198a1; --line:#30363d; --card:#161b22; }
}
* { box-sizing:border-box; }
body { background:var(--bg); color:var(--fg); font-family:var(--font); line-height:1.55;
       margin:0; padding:2.5rem 1.25rem; }
.wrap { max-width:920px; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .2rem; }
h2 { font-size:1.2rem; margin:2rem 0 .75rem; padding-bottom:.3rem; border-bottom:1px solid var(--line); }
h3 { font-size:1rem; margin:1.2rem 0 .3rem; }
.muted { color:var(--muted); }
.cover { display:flex; align-items:center; gap:1.5rem; flex-wrap:wrap; }
.cover .meta { flex:1; min-width:240px; }
.counts { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.5rem; }
.chip { font-size:.78rem; padding:.15rem .55rem; border-radius:1rem; border:1px solid var(--line);
        background:var(--card); }
.chip.fail { color:var(--bad); border-color:var(--bad); }
.chip.warn { color:var(--warn); border-color:var(--warn); }
.chip.pass { color:var(--ok); border-color:var(--ok); }
.bar-row { display:flex; align-items:center; gap:.75rem; margin:.35rem 0; }
.bar-row .label { width:150px; font-size:.85rem; text-align:right; color:var(--muted); }
.bar { flex:1; height:10px; background:var(--card); border-radius:6px; overflow:hidden; }
.bar > span { display:block; height:100%; border-radius:6px; }
.bar-row .val { width:52px; font-variant-numeric:tabular-nums; font-size:.85rem; }
.finding { border:1px solid var(--line); border-left-width:4px; border-radius:8px;
           padding:.7rem .9rem; margin:.6rem 0; background:var(--card); }
.finding.fail { border-left-color:var(--bad); }
.finding.warn { border-left-color:var(--warn); }
.finding.pass { border-left-color:var(--ok); }
.finding.na   { border-left-color:var(--muted); }
.finding .top { display:flex; justify-content:space-between; gap:1rem; align-items:baseline; }
.finding .title { font-weight:600; }
.sev { font-size:.72rem; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }
.finding code, .id { font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.8rem; }
.detail { margin:.35rem 0 0; }
.fix { margin:.35rem 0 0; font-size:.9rem; }
.analysis h3 { margin-top:1rem; }
.analysis ul { margin:.3rem 0 .3rem 1.1rem; padding:0; }
table { border-collapse:collapse; width:100%; font-size:.85rem; margin-top:.5rem; }
th,td { text-align:left; padding:.35rem .5rem; border-bottom:1px solid var(--line); }
.overflow { overflow-x:auto; }
footer { margin-top:2.5rem; padding-top:1rem; border-top:1px solid var(--line);
         color:var(--muted); font-size:.8rem; }
@media print {
  body { padding:0; color:#000; background:#fff; }
  .finding, h2 { break-inside:avoid; }
  a { color:#000; text-decoration:none; }
}
"""


def _gauge(score: int, grade: str) -> str:
    r = 52
    circ = 2 * pi * r
    dash = circ * max(0, min(100, score)) / 100
    color = _grade_color(grade)
    return f"""<svg width="132" height="132" viewBox="0 0 132 132" role="img" aria-label="Score {score} of 100">
  <circle cx="66" cy="66" r="{r}" fill="none" stroke="var(--line)" stroke-width="12"/>
  <circle cx="66" cy="66" r="{r}" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round"
    stroke-dasharray="{dash:.1f} {circ:.1f}" transform="rotate(-90 66 66)"/>
  <text x="66" y="60" text-anchor="middle" font-size="30" font-weight="700" fill="{color}">{grade}</text>
  <text x="66" y="82" text-anchor="middle" font-size="15" fill="var(--muted)">{score}/100</text>
</svg>"""


def _md_to_html(text: str) -> str:
    """Minimal, safe Markdown → HTML for the synthesizer brief (escape first,
    then headings / bullets / bold / paragraphs)."""
    out: list[str] = []
    in_list = False

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    def inline(s: str) -> str:
        s = html.escape(s)
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)

    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            close_list()
            continue
        if s.startswith("### "):
            close_list()
            out.append(f"<h4>{inline(s[4:])}</h4>")
        elif s.startswith("## "):
            close_list()
            out.append(f"<h3>{inline(s[3:])}</h3>")
        elif s.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(s[2:])}</li>")
        else:
            close_list()
            out.append(f"<p>{inline(s)}</p>")
    close_list()
    return "\n".join(out)


def _affected(items: list) -> str:
    parts = []
    for it in items:
        if isinstance(it, dict):
            parts.append(" / ".join(f"{k}={v}" for k, v in it.items()))
        else:
            parts.append(str(it))
    return ", ".join(parts)


def _finding_html(f) -> str:
    cls = f.status.value
    bits = [
        f'<div class="finding {cls}">',
        '<div class="top">',
        f'<span class="title">{_STATUS_LABEL[cls]} — {html.escape(f.title)}</span>',
        f'<span class="sev">{html.escape(f.severity.value)}</span>',
        "</div>",
        f'<div class="muted id"><code>{html.escape(f.checkpoint_id)}</code> · {html.escape(f.category)}</div>',
    ]
    if f.detail:
        bits.append(f'<p class="detail">{html.escape(f.detail)}</p>')
    if f.affected_items:
        bits.append(f'<p class="fix"><em>Affected:</em> {html.escape(_affected(f.affected_items))}</p>')
    if f.remediation_hint:
        bits.append(f'<p class="fix"><em>How to check / fix:</em> {html.escape(f.remediation_hint)}</p>')
    bits.append("</div>")
    return "\n".join(bits)


def _inventory_html(result: AuditResult) -> str:
    sig = result.snapshots[0].data if result.snapshots else {}
    if not sig:
        return ""
    cs = sig.get("container_summary", {})
    rows: list[str] = []

    def row(label, value):
        rows.append(f"<tr><td class='muted'>{label}</td><td>{html.escape(str(value))}</td></tr>")

    pages = sig.get("pages")
    if pages:
        row("Pages crawled", ", ".join(p["url"] for p in pages))
    row("GTM containers", ", ".join(sig.get("tag_ids", {}).get("gtm", [])) or "none")
    row("Measurement IDs", ", ".join(cs.get("measurement_ids", [])) or "none")
    row("Vendors", ", ".join(f"{v['name']} ({v['category']})" for v in sig.get("vendors", [])) or "none")
    row("Ecommerce / enhanced conv. / custom HTML",
        f"{cs.get('ecommerce')} / {cs.get('enhanced_conversions')} / {cs.get('custom_html_count')}")
    consent = sig.get("consent", {})
    row("Consent", f"CMPs={consent.get('cmps') or 'none'}, accepted={consent.get('accepted')}")
    ck = sig.get("cookies", {})
    row("Cookies", f"{ck.get('total', 0)} total, {ck.get('third_party', 0)} third-party")
    events = cs.get("events", [])
    inv = f"<h2>Measurement inventory</h2><div class='overflow'><table>{''.join(rows)}</table></div>"
    if events:
        inv += (f"<h3>GA4 events configured ({len(events)})</h3><p class='muted'>"
                + ", ".join(f"<code>{html.escape(e)}</code>" for e in events) + "</p>")
    return inv


def render_html(result: AuditResult, generated_at: str = "") -> str:
    r = result
    findings = sorted(r.findings, key=lambda f: (_ORDER[f.status], -f.severity.weight, f.checkpoint_id))
    problems = [f for f in findings if f.status in (Status.FAIL, Status.WARN)]

    # cover
    gen = f"Generated {html.escape(generated_at)} · " if generated_at else ""
    counts = "".join(
        f'<span class="chip {k}">{k}={v}</span>' for k, v in r.scores.counts.items()
    )
    cover = f"""<div class="cover">
  {_gauge(r.scores.overall, r.scores.grade)}
  <div class="meta">
    <h1>Measurement Audit</h1>
    <div class="muted">{html.escape(r.target)}</div>
    <div class="muted">{gen}Adwize Audit · {html.escape(r.edition)} edition</div>
    <div class="counts">{counts}</div>
  </div>
</div>"""

    # category bars
    cats = ""
    if r.scores.by_category:
        bars = []
        for cat, sc in sorted(r.scores.by_category.items()):
            bars.append(
                f'<div class="bar-row"><span class="label">{html.escape(cat)}</span>'
                f'<div class="bar"><span style="width:{sc}%;background:{_score_color(sc)}"></span></div>'
                f'<span class="val">{sc}/100</span></div>'
            )
        cats = "<h2>Scores by category</h2>" + "".join(bars)

    # analysis + doc-writer documents
    analysis = ""
    if r.summary:
        analysis = f'<h2>Analysis</h2><div class="analysis">{_md_to_html(r.summary)}</div>'
    elif r.analysis_status and r.analysis_status != "ran":
        analysis = f'<h2>Analysis</h2><p class="muted">Analysis agent not run ({html.escape(r.analysis_status)}).</p>'
    for name, body in (r.documents or {}).items():
        analysis += (f'<h2>{html.escape(name.replace("_", " ").title())}</h2>'
                     f'<div class="analysis">{_md_to_html(body)}</div>')

    # findings
    issues = "<h2>Issues</h2>" + (
        "".join(_finding_html(f) for f in problems) if problems else "<p>No issues detected. 🎉</p>"
    )
    all_rows = "".join(
        f"<tr><td>{_STATUS_LABEL[f.status.value]}</td><td><code>{html.escape(f.checkpoint_id)}</code></td>"
        f"<td>{html.escape(f.severity.value)}</td><td>{html.escape(f.title)}</td></tr>"
        for f in findings
    )
    all_table = (
        "<h2>All checkpoints</h2><div class='overflow'><table>"
        "<tr><th>Status</th><th>Checkpoint</th><th>Severity</th><th>Title</th></tr>"
        f"{all_rows}</table></div>"
    )

    body = "\n".join([cover, cats, analysis, issues, _inventory_html(r), all_table,
                      "<footer>Generated by Adwize Audit — findings derive from a "
                      f"{'public-source crawl' if r.edition == 'oss' else 'authenticated'} scan.</footer>"])

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Measurement Audit — {html.escape(r.target)}</title>
<style>{_CSS}</style>
</head><body><div class="wrap">
{body}
</div></body></html>
"""
