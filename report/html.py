"""Full static HTML audit report — the client-facing deliverable.

Matches getadwize.com (Inter, violet/orange gradient, slate type, pill CTAs).
No JS. Google Fonts + getadwize.com links only.
"""

from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

from core.models.enums import Status
from core.models.result import AuditResult
from core.schemas import loader as schema_loader

_ORDER = {Status.FAIL: 0, Status.WARN: 1, Status.PASS: 2, Status.NA: 3}
_STATUS_LABEL = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "na": "N/A"}

_CTA_HOME = "https://getadwize.com"
_CTA_APPLY = "https://calendly.com/qt-datastarter/discovery-meeting"
_LOGO = "https://getadwize.com/static/logo/adwize-logo-hat.png"

_WORKING_IDS = (
    "crawl.gtm_installed",
    "crawl.ecommerce_funnel",
    "crawl.no_legacy_ua",
    "crawl.server_side_transport",
    "crawl.recommended_event_names",
    "crawl.single_container",
    "crawl.datalayer_present",
)

_CRIT_SHORT = {
    "crawl.no_hardcoded_ga4_duplicate": "duplicate GA4",
    "crawl.no_hardcoded_ads_duplicate": "duplicate Ads pixels",
    "crawl.no_pii_in_network": "PII in analytics URLs",
    "crawl.consent_mode_present": "missing consent",
}

_SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")

_REC_WHY = {
    "add_payment_info": "Add on the payment step so checkout reports include payment.",
    "add_shipping_info": "Add on shipping so the funnel does not drop after begin_checkout.",
    "add_to_wishlist": "Add if shoppers can save items; otherwise skip.",
    "refund": "Send from the backend when an order is refunded.",
    "login": "Needed for GA4 login reports.",
    "sign_up": "Needed for GA4 new-user reports.",
    "search": "Add on site search so Search term reports populate.",
    "generate_lead": "Add on quote / contact forms that are not a purchase.",
    "share": "Add only if sharing is a real conversion.",
    "add_to_cart": "Core ecommerce — without it, cart reports stay empty.",
    "begin_checkout": "Core ecommerce — start of checkout.",
    "purchase": "Core ecommerce — revenue will not show until this fires.",
    "remove_from_cart": "Completes cart analytics.",
    "view_item": "Product page views.",
    "view_item_list": "Category / collection impressions.",
    "view_cart": "Cart page views.",
    "view_promotion": "Promo / banner impressions.",
    "select_item": "Clicks on products in a list.",
    "select_promotion": "Clicks on promos.",
}
_ALIASES = {
    "login": ("log_in", "signin", "sign_in", "social_signin"),
    "sign_up": ("signup", "create_account", "register", "registration"),
    "search": ("site_search", "internal_search"),
    "generate_lead": (
        "get_in_touch",
        "get_custom_quote",
        "get_instant_quote",
        "send_instant_quote",
    ),
}

_CSS = """
:root {
  --violet:#7c3aed; --orange:#f97316; --ink:#0f172a; --muted:#64748b; --line:#e2e8f0;
  --ok:#059669; --warn:#d97706; --bad:#e11d48;
  --font:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --mono:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body {
  margin:0; color:var(--ink); font-family:var(--font); line-height:1.55;
  background:#fff;
  -webkit-font-smoothing:antialiased;
}
::selection { background:#ede9fe; color:#4c1d95; }
a { color:var(--violet); }
.nav {
  position:sticky; top:0; z-index:20;
  background:rgba(255,255,255,.82); backdrop-filter:blur(12px);
  border-bottom:1px solid #f1f5f9;
}
.nav-inner {
  max-width:920px; margin:0 auto; padding:.9rem 1.5rem;
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
}
.brand { display:flex; align-items:center; gap:.6rem; text-decoration:none; color:var(--ink); }
.brand img { width:32px; height:32px; }
.brand strong { font-size:1.05rem; letter-spacing:-.02em; }
.nav-meta { font-size:.8rem; color:var(--muted); font-weight:500; }
.btn {
  display:inline-flex; align-items:center; justify-content:center;
  background:var(--ink); color:#fff; text-decoration:none; font-weight:600; font-size:.84rem;
  padding:.55rem 1.15rem; border-radius:999px; box-shadow:0 8px 20px -8px rgb(76 29 149 / .35);
}
.btn:hover { background:#1e293b; }
.hero {
  background:linear-gradient(180deg,#f5f0ff 0%,#fce7f3 32%,#faf5ff 58%,#fff 100%);
  padding:3rem 1.5rem 2.5rem;
}
.hero-inner { max-width:920px; margin:0 auto; }
.kicker {
  font-size:.72rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--violet); margin:0 0 .85rem;
}
.hero h1 {
  font-size:clamp(2rem,5vw,3.15rem); font-weight:800; letter-spacing:-.04em;
  line-height:1.1; margin:0 0 .75rem;
}
.gradient {
  background:linear-gradient(135deg,#7c3aed 0%,#f97316 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent;
}
.lede { font-size:1.15rem; color:#64748b; font-weight:400; max-width:38rem; margin:0 0 1.25rem; }
.meta-row { display:flex; flex-wrap:wrap; gap:.5rem .85rem; align-items:center; }
.chip {
  font-size:.75rem; font-weight:600; color:#475569; background:#fff;
  border:1px solid var(--line); border-radius:999px; padding:.28rem .7rem;
}
.chip.good { color:#047857; background:#ecfdf5; border-color:#a7f3d0; }
.chip.bad { color:#be123c; background:#fff1f2; border-color:#fecdd3; }
.why { margin:.9rem 0 0; font-size:.88rem; color:var(--muted); }
.wrap { max-width:920px; margin:0 auto; padding:0 1.5rem 3.5rem; }
.fold {
  background:#fff; border:1px solid var(--line); border-radius:1.1rem;
  margin:1rem 0; overflow:hidden;
  box-shadow:0 12px 32px -20px rgb(15 23 42 / .18);
}
.fold > summary {
  list-style:none; cursor:pointer; display:flex; align-items:center; gap:1rem;
  padding:1.15rem 1.35rem; user-select:none;
}
.fold > summary::-webkit-details-marker { display:none; }
.fold-title { font-weight:700; font-size:1.05rem; letter-spacing:-.02em; flex:1; }
.fold-hint { font-size:.8rem; color:var(--muted); font-weight:500; }
.chev {
  width:1.6rem; height:1.6rem; border-radius:999px; border:1px solid var(--line);
  background:#f8fafc; flex-shrink:0; position:relative;
}
.chev:before {
  content:""; position:absolute; inset:.48rem; border-right:2px solid #64748b;
  border-bottom:2px solid #64748b; transform:rotate(45deg) translateY(-2px);
}
.fold[open] > summary { border-bottom:1px solid #f1f5f9; }
.fold[open] .chev:before { transform:rotate(225deg) translateY(-1px); }
.fold-body { padding:1.2rem 1.35rem 1.45rem; }
.issue {
  display:grid; grid-template-columns:6.5rem 1fr; gap:1rem; align-items:start;
  padding:1rem 0; border-bottom:1px solid #f1f5f9;
}
.issue:last-child { border-bottom:0; padding-bottom:0; }
.issue:first-child { padding-top:0; }
.sev {
  font-size:.68rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
  padding-top:.2rem;
}
.sev.critical, .sev.high { color:var(--bad); }
.sev.medium { color:var(--warn); }
.sev.low { color:#64748b; }
.issue h3 { margin:0 0 .25rem; font-size:.98rem; letter-spacing:-.01em; }
.issue p { margin:0; font-size:.88rem; color:var(--muted); }
.working { list-style:none; margin:1.1rem 0 0; padding:1.1rem 0 0; border-top:1px solid #f1f5f9; }
.working li { display:flex; gap:.65rem; padding:.35rem 0; font-size:.9rem; }
.tick {
  width:1.15rem; height:1.15rem; border-radius:999px; background:#ecfdf5; color:#059669;
  display:inline-flex; align-items:center; justify-content:center; font-size:.7rem; flex-shrink:0;
  margin-top:.1rem;
}
.banner {
  margin:1.5rem 0 1.75rem; padding:1.6rem 1.5rem;
  background:#0f172a; color:#fff; border-radius:1.25rem; position:relative; overflow:hidden;
}
.banner:before {
  content:""; position:absolute; width:280px; height:280px; right:-60px; top:-90px;
  background:radial-gradient(circle,rgb(139 92 246 / .28),transparent 70%);
}
.banner .inner { position:relative; }
.banner .kicker { color:#c4b5fd; }
.banner h2 { margin:.2rem 0 .5rem; font-size:1.35rem; letter-spacing:-.03em; }
.banner p { margin:0 0 1rem; color:#94a3b8; font-size:.92rem; max-width:34rem; }
.banner .btn { background:#fff; color:var(--ink); box-shadow:none; }
.banner .btn:hover { background:#f8fafc; }
.chips { display:flex; flex-wrap:wrap; gap:.5rem; }
.source {
  display:inline-flex; align-items:center; gap:.5rem;
  background:#f8fafc; border:1px solid var(--line); border-radius:.7rem;
  padding:.55rem .8rem; font-size:.85rem; font-weight:600;
}
.source span.dot { width:.45rem; height:.45rem; border-radius:50%; background:var(--violet); }
.note {
  font-size:.88rem; color:var(--muted); margin:0 0 1.15rem; max-width:40rem;
}
.subh { font-size:.8rem; font-weight:700; letter-spacing:.06em; text-transform:uppercase;
        color:#64748b; margin:1.35rem 0 .55rem; }
.subh:first-child { margin-top:0; }
.gap { width:100%; border-collapse:collapse; font-size:.88rem; }
.gap th { font-size:.72rem; text-transform:uppercase; letter-spacing:.04em; color:#94a3b8;
          font-weight:600; padding:.4rem .5rem .4rem 0; border-bottom:1px solid var(--line); }
.gap td { padding:.65rem .5rem .65rem 0; border-bottom:1px solid #f1f5f9; vertical-align:top; }
.gap tr:last-child td { border-bottom:0; }
.gap code { font-family:var(--mono); font-size:.8rem; font-weight:600; }
.st { font-size:.72rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase;
      white-space:nowrap; }
.st.in { color:#047857; }
.st.out { color:var(--bad); }
.st.fix { color:var(--warn); }
.events { border:1px solid var(--line); border-radius:.9rem; overflow:hidden; margin-top:.4rem; }
.events details { border-bottom:1px solid #f1f5f9; }
.events details:last-child { border-bottom:0; }
.events summary {
  list-style:none; cursor:pointer; display:flex; justify-content:space-between;
  align-items:center; gap:1rem; padding:.7rem 1rem; font-size:.88rem; color:var(--muted);
}
.events summary::-webkit-details-marker { display:none; }
.events code { font-family:var(--mono); font-size:.8rem; font-weight:600; color:var(--ink); }
.muted { color:var(--muted); }
.analysis h3 { margin-top:1.1rem; }
.analysis ul { margin:.3rem 0 .3rem 1.1rem; padding:0; }
.finding {
  border:1px solid var(--line); border-radius:.75rem; padding:.75rem .9rem; margin:.55rem 0; background:#f8fafc;
}
.finding .top { display:flex; justify-content:space-between; gap:1rem; }
.finding .title { font-weight:600; }
.finding code, .id { font-family:var(--mono); font-size:.78rem; }
.detail, .fix { margin:.3rem 0 0; font-size:.88rem; }
table { border-collapse:collapse; width:100%; font-size:.85rem; margin-top:.5rem; }
th,td { text-align:left; padding:.4rem .5rem; border-bottom:1px solid var(--line); }
.overflow { overflow-x:auto; }
footer {
  max-width:920px; margin:0 auto; padding:1.25rem 1.5rem 2.5rem;
  color:var(--muted); font-size:.78rem;
  display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap;
  border-top:1px solid #f1f5f9;
}
footer a { color:var(--violet); text-decoration:none; font-weight:600; }
@media (max-width:640px) {
  .issue { grid-template-columns:1fr; gap:.2rem; }
  .fold-hint { display:none; }
  .nav-meta { display:none; }
}
@media print {
  .nav { position:static; }
  .hero { background:#fff; padding:1rem 0; }
  .banner { background:#fff; color:#000; border:1px solid #000; }
  .banner p, .banner .kicker { color:#333; }
  .fold .fold-body { display:block !important; }
  .btn { box-shadow:none; }
}
"""


def _host(url: str) -> str:
    host = urlsplit(url if "://" in url else f"https://{url}").netloc
    return host.removeprefix("www.") or url


def _esc(s: object) -> str:
    return html.escape(str(s or ""))


def _strip_letter_grades(text: str) -> str:
    """Client HTML does not show A–E grades; drop them from analyst copy too."""
    text = re.sub(r"\b[Gg]rade\s+[A-E]\b", "", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def _first_sentence(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    m = re.match(r"(.+?[.!?])(?:\s|$)", text)
    return (m.group(1) if m else text)[:280]


def _exec_brief(brief: str) -> str:
    m = re.search(r"##\s*Executive summary\s*(.+?)(?:\n##\s|\Z)", brief, re.S | re.I)
    return (m.group(1) if m else brief).strip()


def _headline(result: AuditResult) -> str:
    n = sum(1 for f in result.findings if f.status in (Status.FAIL, Status.WARN))
    fallback = f"{n} issue{'s' if n != 1 else ''} to fix on this property."
    if not result.summary:
        return fallback
    brief = _strip_letter_grades(_exec_brief(result.summary))
    sent = _first_sentence(brief)
    if sent and re.search(r"\d+/100", sent):
        rest = re.sub(r"^.+?[.!?]\s*", "", brief, count=1)
        sent = _first_sentence(rest) or sent
    return sent or fallback


def _why_grade(result: AuditResult) -> str:
    penalties = result.scores.penalties or []
    crit = [p for p in penalties if p.status == "fail" and p.severity == "critical"]
    if not crit:
        if result.scores.overall >= 90:
            return "No critical issues — remaining items are hygiene and polish."
        return (
            f"Health score {result.scores.overall}/100 after "
            f"{len(penalties)} scored finding{'s' if len(penalties) != 1 else ''}."
        )
    labels = [
        _CRIT_SHORT.get(p.checkpoint_id, p.checkpoint_id.split(".")[-1].replace("_", " "))
        for p in crit
    ]
    n = len(crit)
    noun = "issue" if n == 1 else "issues"
    floor = (
        " brought the score to 0"
        if result.scores.overall == 0
        else f" drove the {result.scores.overall}/100 score"
    )
    return f"{n} critical {noun} ({', '.join(labels)}){floor}."


def _sig(result: AuditResult) -> dict:
    return result.snapshots[0].data if result.snapshots else {}


def _finding_by_id(result: AuditResult, checkpoint_id: str):
    return next((f for f in result.findings if f.checkpoint_id == checkpoint_id), None)


def _status_chips(result: AuditResult) -> str:
    sig = _sig(result)
    ss = bool(sig.get("network", {}).get("server_side"))
    consent_f = _finding_by_id(result, "crawl.consent_mode_present")
    consent_ok = bool(consent_f and consent_f.status == Status.PASS)
    cmp_ok = bool(sig.get("consent", {}).get("cmps"))
    bits = []
    for label, on in (("Server-side tagging", ss), ("Consent Mode", consent_ok), ("CMP", cmp_ok)):
        cls = "good" if on else "bad"
        bits.append(f'<span class="chip {cls}">{_esc(label)}</span>')
    return "".join(bits)


def _md_to_html(text: str) -> str:
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
        f'<span class="title">{_STATUS_LABEL[cls]} — {_esc(f.title)}</span>',
        f'<span class="sev {_esc(f.severity.value)}">{_esc(f.severity.value)}</span>',
        "</div>",
        f'<div class="muted id"><code>{_esc(f.checkpoint_id)}</code> · {_esc(f.category)}</div>',
    ]
    if f.detail:
        bits.append(f'<p class="detail">{_esc(f.detail)}</p>')
    if f.affected_items:
        bits.append(f'<p class="fix"><em>Affected:</em> {_esc(_affected(f.affected_items))}</p>')
    if f.remediation_hint:
        bits.append(f'<p class="fix"><em>How to check / fix:</em> {_esc(f.remediation_hint)}</p>')
    bits.append("</div>")
    return "\n".join(bits)


def _issue_row(f) -> str:
    sev = f.severity.value
    desc = f.detail or f.remediation_hint or ""
    return (
        f'<article class="issue">'
        f'<div class="sev {sev}">{_esc(sev)}</div>'
        f"<div><h3>{_esc(f.title)}</h3><p>{_esc(desc)}</p></div>"
        "</article>"
    )


def _fold(title: str, hint: str, body: str, *, opened: bool = False) -> str:
    op = " open" if opened else ""
    return (
        f'<details class="fold"{op}>'
        f"<summary><span class='fold-title'>{title}</span>"
        f"<span class='fold-hint'>{hint}</span><span class='chev' aria-hidden='true'></span></summary>"
        f'<div class="fold-body">{body}</div></details>'
    )


def _cta() -> str:
    return f"""<aside class="banner">
  <div class="inner">
    <p class="kicker">Keep it clean</p>
    <h2>Catch the next break before GA4 does.</h2>
    <p>Adwize monitors your collection layer in real time — duplicate pixels, consent drift, missing events — and tells you why it broke.</p>
    <a class="btn" href="{_CTA_APPLY}">Request invite</a>
  </div>
</aside>"""


def _tech_items(result: AuditResult) -> list[dict]:
    sig = _sig(result)
    vendors = list(sig.get("vendors") or [])
    cs = sig.get("container_summary", {})
    extras: list[dict] = []
    if cs.get("custom_html_count"):
        extras.append({"name": "Custom HTML", "meta": f"{cs['custom_html_count']} tags"})
    if sig.get("network", {}).get("server_side"):
        extras.append({"name": "Server-side GTM", "meta": "first-party"})
    if cs.get("paused_count"):
        extras.append({"name": "Paused tags", "meta": str(cs["paused_count"])})
    return vendors + extras


def _technologies(result: AuditResult) -> str:
    items = _tech_items(result)
    if not items:
        return ""
    chips = "".join(
        f'<span class="source"><span class="dot"></span>{_esc(v["name"])}</span>' for v in items
    )
    n = len(items)
    hint = f"{n} vendor{'s' if n != 1 else ''} observed on the public crawl"
    return _fold("Stack", hint, f'<div class="chips">{chips}</div>')


def _alias_for(missing: str, configured: set[str]) -> str | None:
    for cand in _ALIASES.get(missing, ()):
        if cand in configured:
            return cand
    return None


def _st(kind: str, label: str) -> str:
    return f'<span class="st {kind}">{_esc(label)}</span>'


def _gap_row(name: str, status_html: str, action: str) -> str:
    return (
        f"<tr><td><code>{_esc(name)}</code></td><td>{status_html}</td><td>{_esc(action)}</td></tr>"
    )


def _tracking_plan(result: AuditResult) -> str:
    sig = _sig(result)
    cs = sig.get("container_summary", {})
    events = list(cs.get("events") or [])
    if not events:
        return ""
    schema = schema_loader.load("ga4_events")
    recommended = list(schema.get("recommended") or [])
    funnel = list(schema.get("ecommerce_funnel") or [])
    configured = set(events)
    dupes = list(cs.get("duplicate_event_names") or [])
    bad_names = [e for e in events if not _SNAKE_CASE.match(e)]

    parts: list[str] = [
        '<p class="note">These are event <em>names configured in GTM</em>, not a guarantee they fire '
        "on the live site. Use this as a gap list: what to add, rename, or ignore.</p>"
    ]

    missing_funnel = 0
    if cs.get("ecommerce") or (configured & set(funnel)):
        rows = []
        for e in funnel:
            if e in configured:
                rows.append(_gap_row(e, _st("in", "In GTM"), "No action."))
            else:
                missing_funnel += 1
                rows.append(_gap_row(e, _st("out", "Missing"), _REC_WHY.get(e, "Add this event.")))
        parts.append('<p class="subh">Checkout funnel</p>')
        parts.append(
            "<table class='gap'><thead><tr><th>Event</th><th>Status</th><th>What to do</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    rec_rows = []
    n_missing = 0
    funnel_set = set(funnel)
    for e in recommended:
        if e in funnel_set or e in configured:
            continue
        n_missing += 1
        alias = _alias_for(e, configured)
        if alias:
            rec_rows.append(
                _gap_row(
                    e,
                    _st("fix", "Rename"),
                    f"You already send {alias}. Rename it to {e} so GA4 standard reports pick it up.",
                )
            )
        else:
            rec_rows.append(
                _gap_row(e, _st("out", "Missing"), _REC_WHY.get(e, "Add if it applies."))
            )
    present_rec = [e for e in recommended if e in configured]
    if rec_rows:
        parts.append('<p class="subh">Google recommended — gaps</p>')
        parts.append(
            '<p class="note">These names unlock GA4’s built-in reports. Custom names '
            "(hp_quote_click, …) never will.</p>"
        )
        parts.append(
            "<table class='gap'><thead><tr><th>Event</th><th>Status</th><th>What to do</th></tr></thead>"
            f"<tbody>{''.join(rec_rows)}</tbody></table>"
        )
    if present_rec:
        chips = " ".join(f"<code>{_esc(e)}</code>" for e in present_rec)
        parts.append(
            f'<p class="note" style="margin-top:1rem">Already using recommended names: {chips}</p>'
        )

    hygiene = []
    for e in bad_names:
        hygiene.append(
            _gap_row(e, _st("fix", "Rename"), "Switch to snake_case (e.g. cart_price_update).")
        )
    for e in dupes:
        hygiene.append(
            _gap_row(
                e,
                _st("fix", "Duplicate"),
                "Two tags share this name — merge them or split triggers.",
            )
        )
    if hygiene:
        parts.append('<p class="subh">Fix these names</p>')
        parts.append(
            "<table class='gap'><thead><tr><th>Event</th><th>Status</th><th>What to do</th></tr></thead>"
            f"<tbody>{''.join(hygiene)}</tbody></table>"
        )

    custom = [e for e in events if e not in set(recommended)]
    if custom:
        items = "".join(f"<li><code>{_esc(e)}</code></li>" for e in custom)
        parts.append(
            f'<details class="events"><summary>{len(custom)} custom events — no Google report mapping</summary>'
            f'<ul class="working" style="border:0;margin:0;padding:.2rem 1rem 1rem">{items}</ul></details>'
        )

    n_actions = missing_funnel + n_missing + len(hygiene)
    hint = f"{n_actions} action{'s' if n_actions != 1 else ''} · {len(events)} names in GTM"
    return _fold("Events", hint, "".join(parts))


def _appendix(result: AuditResult, findings: list) -> str:
    analysis = ""
    if result.summary:
        analysis = (
            f'<h3>Analysis</h3><div class="analysis">'
            f"{_md_to_html(_strip_letter_grades(result.summary))}</div>"
        )
    elif result.analysis_status and result.analysis_status != "ran":
        analysis = f'<p class="muted">Analysis agent not run ({_esc(result.analysis_status)}).</p>'
    for name, body in (result.documents or {}).items():
        analysis += (
            f"<h3>{_esc(name.replace('_', ' ').title())}</h3>"
            f'<div class="analysis">{_md_to_html(body)}</div>'
        )
    problems = [f for f in findings if f.status in (Status.FAIL, Status.WARN)]
    issues = (
        "".join(_finding_html(f) for f in problems) if problems else "<p>No issues detected.</p>"
    )
    all_rows = "".join(
        f"<tr><td>{_STATUS_LABEL[f.status.value]}</td><td><code>{_esc(f.checkpoint_id)}</code></td>"
        f"<td>{_esc(f.severity.value)}</td><td>{_esc(f.title)}</td></tr>"
        for f in findings
    )
    sig = _sig(result)
    inv_rows = []
    pages = sig.get("pages") or []
    if pages:
        inv_rows.append(
            f"<tr><td class='muted'>Pages crawled</td>"
            f"<td>{_esc(', '.join(p['url'] for p in pages))}</td></tr>"
        )
    cats = ""
    if result.scores.by_category:
        bars = "".join(
            f"<tr><td>{_esc(cat)}</td><td>{sc}/100</td></tr>"
            for cat, sc in sorted(result.scores.by_category.items())
        )
        cats = "<h3>Scores by category</h3><table>" + bars + "</table>"
    body = f"""
    {cats}
    {analysis}
    <h3>Issues (full)</h3>
    {issues}
    <h3>All checkpoints</h3>
    <div class="overflow"><table>
      <tr><th>Status</th><th>Checkpoint</th><th>Severity</th><th>Title</th></tr>
      {all_rows}
    </table></div>
    <h3>Crawl inventory</h3>
    <div class="overflow"><table>{"".join(inv_rows)}</table></div>
    """
    return _fold("Technical notes", "Checkpoints, scoring, analyst notes", body)


def render_html(result: AuditResult, generated_at: str = "") -> str:
    r = result
    findings = sorted(
        r.findings, key=lambda f: (_ORDER[f.status], -f.severity.weight, f.checkpoint_id)
    )
    problems = [f for f in findings if f.status in (Status.FAIL, Status.WARN)]
    working = [f for f in findings if f.status == Status.PASS and f.checkpoint_id in _WORKING_IDS]
    host = _host(r.target)
    n_fail = sum(1 for f in problems if f.status == Status.FAIL)
    n_warn = sum(1 for f in problems if f.status == Status.WARN)
    gen = f"Generated {_esc(generated_at)} · " if generated_at else ""

    issue_list = (
        "".join(_issue_row(f) for f in problems)
        if problems
        else '<p class="muted">No issues detected.</p>'
    )
    working_html = ""
    if working:
        items = "".join(
            f"<li><span class='tick'>✓</span><span>{_esc(f.title)}</span></li>" for f in working
        )
        working_html = f"<p class='muted' style='margin:1.2rem 0 .2rem;font-size:.8rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase'>Already in place</p><ul class='working'>{items}</ul>"

    findings_body = issue_list + working_html
    findings_hint = f"{n_fail} to fix · {n_warn} to review" if problems else "Clean scan"
    findings_fold = _fold("Findings", findings_hint, findings_body, opened=True)

    header = f"""<nav class="nav">
  <div class="nav-inner">
    <a class="brand" href="{_CTA_HOME}">
      <img src="{_LOGO}" alt="">
      <strong>Adwize</strong>
    </a>
    <span class="nav-meta">Measurement audit</span>
    <a class="btn" href="{_CTA_APPLY}">Request invite</a>
  </div>
</nav>
<header class="hero">
  <div class="hero-inner">
    <p class="kicker">Public crawl · {_esc(r.edition)}</p>
    <h1><span class="gradient">{_esc(host)}</span></h1>
    <p class="lede">{_esc(_headline(r))}</p>
    <div class="meta-row">
      <span class="chip">{r.scores.overall}/100</span>
      {_status_chips(r)}
    </div>
    <p class="why">{_esc(_why_grade(r))}</p>
  </div>
</header>"""

    body = "\n".join(
        [
            header,
            '<div class="wrap">',
            findings_fold,
            _cta(),
            _technologies(r),
            _tracking_plan(r),
            _appendix(r, findings),
            "</div>",
            f"<footer><span>{gen}Adwize · public-source crawl</span>"
            f'<a href="{_CTA_HOME}">getadwize.com</a></footer>',
        ]
    )

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Measurement Audit — {_esc(r.target)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>{_CSS}</style>
</head><body>
{body}
</body></html>
"""
