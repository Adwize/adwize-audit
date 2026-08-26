"""Pure signal extraction from rendered HTML and captured requests.

All functions here are stateless and unit-testable with dict/string fixtures —
no browser, no network, no side effects. The crawl collector calls these after
rendering pages; checks consume the resulting signal dict.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from core.collectors import vendors
from core.schemas import loader

GTM_SNIPPET = re.compile(r"googletagmanager\.com/gtm\.js\?id=(GTM-[A-Z0-9]+)")
GTAG_JS = re.compile(r"googletagmanager\.com/gtag/js\?id=(G-[A-Z0-9]+|UA-\d+-\d+|AW-\d+)")
GTM_NOSCRIPT = re.compile(
    r"<noscript[^>]*>.*?googletagmanager\.com/ns\.html\?id=(GTM-[A-Z0-9]+)",
    re.DOTALL | re.IGNORECASE,
)
DATALAYER_INIT = re.compile(r"dataLayer\s*=\s*\[")
DATALAYER_PUSH = re.compile(r"dataLayer\.push\s*\(")
CONSENT_MODE = re.compile(r"gtag\s*\(\s*['\"]consent['\"]")
THIRD_PARTY_SCRIPT = re.compile(r'<script[^>]+src=["\']https?://([^"\'/?#]+)', re.IGNORECASE)
GA_COLLECT = re.compile(r"/g/collect|google-analytics\.com/(?:g/)?collect|/mp/collect")
HREF = re.compile(r'<a\s[^>]*href=["\']([^"\'#]+)["\']', re.IGNORECASE)


@lru_cache
def _cmp_schema() -> dict[str, Any]:
    return loader.load("cmp")


@lru_cache
def _cmp_detectors() -> list[tuple[str, re.Pattern[str]]]:
    return [
        (c["name"], re.compile(c["detect"], re.IGNORECASE)) for c in _cmp_schema().get("cmps", [])
    ]


@lru_cache
def _pii() -> tuple[re.Pattern[str], re.Pattern[str]]:
    s = loader.load("pii")
    return re.compile(s["email_pattern"]), re.compile(s["param_key_pattern"], re.IGNORECASE)


@lru_cache
def _pii_host_patterns() -> tuple[re.Pattern[str], re.Pattern[str]]:
    s = loader.load("pii")
    return (
        re.compile(s["analytics_host_pattern"], re.IGNORECASE),
        re.compile(s["crm_host_pattern"], re.IGNORECASE),
    )


def pii_host_bucket(host: str) -> str:
    """analytics = pixel/TOS issue; crm = typical form post; other = review."""
    analytics, crm = _pii_host_patterns()
    if analytics.search(host):
        return "analytics"
    if crm.search(host):
        return "crm"
    return "other"


def _network_events(collect_hits: list[str]) -> list[str]:
    events: list[str] = []
    for u in collect_hits:
        events.extend(parse_qs(urlsplit(u).query).get("en", []))
    return events


def _pii_in_requests(request_urls: list[str]) -> list[dict[str, Any]]:
    email, param_key = _pii()
    by_host: dict[str, set[str]] = {}
    for u in request_urls:
        dec = unquote(u)
        kinds: set[str] = set()
        if email.search(dec):
            kinds.add("email")
        if param_key.search(dec):
            kinds.add("param")
        if not kinds:
            continue
        by_host.setdefault(urlsplit(u).netloc, set()).update(kinds)
    hits: list[dict[str, Any]] = []
    for host in sorted(by_host)[:10]:
        hits.append(
            {
                "host": host,
                "kinds": sorted(by_host[host]),
                "bucket": pii_host_bucket(host),
            }
        )
    return hits


def _aggregate_containers(containers: dict[str, dict]) -> dict[str, Any]:
    def union(key: str) -> list:
        s: set = set()
        for c in containers.values():
            s.update(c.get(key, []) or [])
        return sorted(s)

    total_vars = sum(c.get("variables", {}).get("total", 0) for c in containers.values())
    unreferenced_vars = sum(
        c.get("variables", {}).get("unreferenced_count", 0) for c in containers.values()
    )

    return {
        "events": union("events"),
        "measurement_ids": union("measurement_ids"),
        "ecommerce": any(c.get("ecommerce") for c in containers.values()),
        "user_properties": any(c.get("user_properties") for c in containers.values()),
        "enhanced_conversions": any(c.get("enhanced_conversions") for c in containers.values()),
        "custom_html_count": sum(c.get("custom_html_count", 0) for c in containers.values()),
        "paused_count": sum(c.get("paused_count", 0) for c in containers.values()),
        "duplicate_event_names": union("duplicate_event_names"),
        "variable_count": total_vars,
        "unreferenced_variable_count": unreferenced_vars,
        "has_floodlight": any(c.get("has_floodlight") for c in containers.values()),
        "has_ads": any(c.get("has_ads") for c in containers.values()),
        "has_ga4": any(c.get("has_ga4") for c in containers.values()),
        "vendors": union("vendors"),
    }


def extract_signals(
    html: str,
    request_urls: list[str],
    containers: dict[str, dict[str, Any]],
    cookies: list[dict[str, Any]] | None = None,
    consent: dict[str, Any] | None = None,
    datalayer_runtime: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure extraction of tag signals from a rendered page + captured requests."""
    cookies = cookies or []
    datalayer_runtime = datalayer_runtime or {}
    gtm_ids = sorted(set(GTM_SNIPPET.findall(html)) | set(containers.keys()))
    gtag_ids = GTAG_JS.findall(html)
    ga4 = sorted({g for g in gtag_ids if g.startswith("G-")})
    ads = sorted({g for g in gtag_ids if g.startswith("AW-")})
    ua = sorted({g for g in gtag_ids if g.startswith("UA-")})

    gtm_pos = html.find("googletagmanager.com/gtm.js")
    body_pos = html.lower().find("<body")
    gtm_in_head = gtm_pos >= 0 and (body_pos < 0 or gtm_pos < body_pos)

    init = DATALAYER_INIT.search(html)
    push = DATALAYER_PUSH.search(html)
    push_before_gtm = bool(push and gtm_pos >= 0 and push.start() < gtm_pos)

    cmps = [name for name, pat in _cmp_detectors() if pat.search(html)]
    noscript_ids = GTM_NOSCRIPT.findall(html)

    domains: set[str] = set()
    for d in THIRD_PARTY_SCRIPT.findall(html):
        domains.add(".".join(d.split(".")[-2:]))

    collect_hits = [u for u in request_urls if GA_COLLECT.search(u)]
    pii_hits = _pii_in_requests(request_urls)
    gcs_seen = any(("gcs=" in u or "gcd=" in u) for u in collect_hits)
    server_side_urls = [
        u
        for u in collect_hits
        if "google-analytics.com" not in u and "googletagmanager.com" not in u
    ]
    linker_seen = "_gl=" in html or any("_gl=" in u for u in request_urls)
    third_party_cookies = [c for c in cookies if not c.get("first_party", True)]
    consent = consent or {}

    return {
        "tag_ids": {"ga4": ga4, "ads": ads, "ua": ua, "gtm": gtm_ids},
        "gtm_in_head": gtm_in_head,
        "datalayer": {
            "init": bool(init),
            "push": bool(push),
            "push_before_gtm": push_before_gtm,
            "exists": bool(datalayer_runtime.get("exists")),
            "length": int(datalayer_runtime.get("length", 0)),
        },
        "consent": {
            "consent_mode": bool(CONSENT_MODE.search(html)),
            "cmps": cmps,
            "signals_seen": gcs_seen,
            "accepted": consent.get("accepted", False),
            "accepted_cmp": consent.get("cmp"),
        },
        "noscript": {"present": bool(noscript_ids), "ids": sorted(set(noscript_ids))},
        "cross_domain": {"linker_seen": linker_seen},
        "third_party_domains": sorted(domains),
        "network": {
            "collect_hits": len(collect_hits),
            "gcs_seen": gcs_seen,
            "server_side": bool(server_side_urls),
            "server_side_urls": sorted(set(server_side_urls))[:10],
            "firing_events": sorted(set(_network_events(collect_hits))),
            "pii_hosts": [h["host"] for h in pii_hits],
            "pii_hits": pii_hits,
        },
        "cookies": {"total": len(cookies), "third_party": len(third_party_cookies)},
        "vendors": vendors.detect(html, request_urls),
        "containers": containers,
        "container_summary": _aggregate_containers(containers),
    }


def _host(netloc: str) -> str:
    return netloc.removeprefix("www.").lower()


def _normalize_url(url: str) -> str:
    return url if url.startswith(("http://", "https://")) else f"https://{url}"


_PAGE_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("checkout", ("checkout", "caisse", "kasse", "pago", "commande")),
    ("cart", ("cart", "basket", "panier", "warenkorb", "/bag")),
    ("product", ("/product", "/products/", "/p/", "/dp/", "/item", "/retreat", "/listing")),
    ("contact", ("contact", "kontakt", "contacto")),
    ("category", ("/category", "/collections", "/categor", "/c/", "/shop")),
    ("search", ("/search", "/s/", "q=", "recherche")),
    ("pricing", ("pricing", "/plans", "/tarifs")),
]


def discover_links(start_url: str, html: str, limit: int) -> list[str]:
    """Pick up to `limit` same-HOST internal URLs to crawl, preferring key page
    types (checkout/cart/product/contact/...) then filling with other links."""

    start = urlsplit(_normalize_url(start_url))
    start_host = _host(start.netloc)
    seen_paths = {start.path or "/"}
    candidates: list[str] = []
    for href in HREF.findall(html):
        if href.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        u = urlsplit(urljoin(_normalize_url(start_url), href))
        if u.scheme not in ("http", "https") or _host(u.netloc) != start_host:
            continue
        path = u.path or "/"
        if path in seen_paths:
            continue
        seen_paths.add(path)
        candidates.append(u.geturl())

    picked: list[str] = []
    for _label, kws in _PAGE_KEYWORDS:
        for c in candidates:
            if c not in picked and any(k in c.lower() for k in kws):
                picked.append(c)
                break
    for c in candidates:
        if len(picked) >= limit:
            break
        if c not in picked:
            picked.append(c)
    return picked[:limit]


def _union(sigs: list[dict], *path: str) -> list:
    acc: set = set()
    for sig in sigs:
        node: Any = sig
        for key in path:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        if isinstance(node, list):
            acc.update(node)
    return sorted(acc)


_BUCKET_RANK = {"other": 0, "crm": 1, "analytics": 2}


def _merge_pii_hits(sigs: list[dict]) -> list[dict[str, Any]]:
    by_host: dict[str, dict[str, Any]] = {}
    for sig in sigs:
        net = sig.get("network", {}) or {}
        hits = net.get("pii_hits")
        if hits:
            raw_hits = hits
        else:
            raw_hits = [
                {"host": h, "kinds": [], "bucket": pii_host_bucket(h)}
                for h in (net.get("pii_hosts") or [])
            ]
        for hit in raw_hits:
            host = hit.get("host") or ""
            if not host:
                continue
            existing = by_host.setdefault(host, {"host": host, "kinds": set(), "bucket": "other"})
            existing["kinds"].update(hit.get("kinds") or [])
            bucket = hit.get("bucket") or pii_host_bucket(host)
            if _BUCKET_RANK.get(bucket, 0) > _BUCKET_RANK.get(existing["bucket"], 0):
                existing["bucket"] = bucket
    return [
        {
            "host": host,
            "kinds": sorted(by_host[host]["kinds"]),
            "bucket": by_host[host]["bucket"],
        }
        for host in sorted(by_host)[:10]
    ]


def merge_signals(sigs: list[dict], containers: dict, pages: list[dict]) -> dict[str, Any]:
    """Aggregate per-page signal dicts into one site-level snapshot."""
    with_gtm = [s for s in sigs if s.get("tag_ids", {}).get("gtm")]
    vendors_by_name = {v["name"]: v for s in sigs for v in s.get("vendors", [])}
    return {
        "tag_ids": {k: _union(sigs, "tag_ids", k) for k in ("ga4", "ads", "ua", "gtm")},
        "gtm_in_head": all(s.get("gtm_in_head") for s in with_gtm) if with_gtm else False,
        "datalayer": {
            "init": any(s.get("datalayer", {}).get("init") for s in sigs),
            "push": any(s.get("datalayer", {}).get("push") for s in sigs),
            "push_before_gtm": any(s.get("datalayer", {}).get("push_before_gtm") for s in sigs),
            "exists": any(s.get("datalayer", {}).get("exists") for s in sigs),
            "length": max((s.get("datalayer", {}).get("length", 0) for s in sigs), default=0),
        },
        "consent": {
            "consent_mode": any(s.get("consent", {}).get("consent_mode") for s in sigs),
            "cmps": _union(sigs, "consent", "cmps"),
            "signals_seen": any(s.get("consent", {}).get("signals_seen") for s in sigs),
            "accepted": any(s.get("consent", {}).get("accepted") for s in sigs),
            "accepted_cmp": next(
                (
                    s["consent"]["accepted_cmp"]
                    for s in sigs
                    if s.get("consent", {}).get("accepted_cmp")
                ),
                None,
            ),
        },
        "noscript": {
            "present": any(s.get("noscript", {}).get("present") for s in sigs),
            "ids": _union(sigs, "noscript", "ids"),
        },
        "cross_domain": {
            "linker_seen": any(s.get("cross_domain", {}).get("linker_seen") for s in sigs)
        },
        "third_party_domains": _union(sigs, "third_party_domains"),
        "network": {
            "collect_hits": sum(s.get("network", {}).get("collect_hits", 0) for s in sigs),
            "gcs_seen": any(s.get("network", {}).get("gcs_seen") for s in sigs),
            "server_side": any(s.get("network", {}).get("server_side") for s in sigs),
            "server_side_urls": _union(sigs, "network", "server_side_urls"),
            "firing_events": _union(sigs, "network", "firing_events"),
            "pii_hosts": _union(sigs, "network", "pii_hosts"),
            "pii_hits": _merge_pii_hits(sigs),
        },
        "cookies": {
            "total": max((s.get("cookies", {}).get("total", 0) for s in sigs), default=0),
            "third_party": max(
                (s.get("cookies", {}).get("third_party", 0) for s in sigs), default=0
            ),
        },
        "vendors": sorted(vendors_by_name.values(), key=lambda v: (v["category"], v["name"])),
        "containers": containers,
        "container_summary": _aggregate_containers(containers),
        "pages": pages,
        "pages_scanned": len(pages),
    }
