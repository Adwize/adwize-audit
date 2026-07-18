"""Deterministic checks over a crawl Snapshot. NO LLM — pure, reproducible,
and unit-testable with dict fixtures. Each returns exactly one Finding so the
report shows full checkpoint coverage (pass/fail/warn/na)."""

from __future__ import annotations

import re
from functools import lru_cache

from core.models.enums import Status
from core.models.finding import Finding
from core.registry import loader
from core.schemas import loader as schema_loader

SNAKE_CASE = re.compile(r"^[a-z0-9]+(_[a-z0-9]+)*$")


@lru_cache
def _ga4_types() -> set[str]:
    groups = schema_loader.load("gtm_functions").get("type_groups", {})
    return set(groups.get("ga4_config", [])) | set(groups.get("ga4_event", []))


@lru_cache
def _ads_types() -> set[str]:
    groups = schema_loader.load("gtm_functions").get("type_groups", {})
    return set(groups.get("ads", []))


@lru_cache
def _recommended_events() -> set[str]:
    return set(schema_loader.load("ga4_events").get("recommended", []))


@lru_cache
def _ecommerce_funnel() -> list[str]:
    return list(schema_loader.load("ga4_events").get("ecommerce_funnel", []))


@lru_cache
def _pii_token() -> re.Pattern[str]:
    return re.compile(schema_loader.load("pii")["token_pattern"], re.IGNORECASE)


def _finding(checkpoint_id: str, status: Status, title: str, detail: str = "", **extra) -> Finding:
    cp = loader.get(checkpoint_id)
    if cp is None:  # registry drift — surface loudly rather than silently drop
        raise KeyError(f"unknown checkpoint id: {checkpoint_id}")
    extra.setdefault("remediation_hint", cp.how_to_check)  # caller may override
    return Finding(
        checkpoint_id=checkpoint_id,
        status=status,
        severity=cp.severity,
        category=cp.category,
        source=cp.source,
        title=title,
        detail=detail,
        **extra,
    )


def _container_has(containers: dict, types: set[str]) -> bool:
    for c in containers.values():
        for t in c.get("tags", []):
            if (t.get("type") or "") in types:
                return True
    return False


def check_gtm_installed(d: dict) -> Finding:
    ids = d.get("tag_ids", {}).get("gtm", [])
    if ids:
        return _finding("crawl.gtm_installed", Status.PASS, f"GTM installed: {', '.join(ids)}")
    return _finding(
        "crawl.gtm_installed",
        Status.FAIL,
        "No GTM container found",
        "No googletagmanager.com/gtm.js reference was found in the rendered page.",
        remediation_hint="Add the GTM snippet to the page <head>.",
    )


def check_gtm_in_head(d: dict) -> Finding:
    if not d.get("tag_ids", {}).get("gtm"):
        return _finding("crawl.gtm_in_head", Status.NA, "No GTM to place")
    if d.get("gtm_in_head"):
        return _finding("crawl.gtm_in_head", Status.PASS, "GTM loads from <head>")
    return _finding(
        "crawl.gtm_in_head",
        Status.WARN,
        "GTM snippet appears after <body>",
        "GTM should load in <head> for earliest execution.",
    )


def check_single_container(d: dict) -> Finding:
    ids = d.get("tag_ids", {}).get("gtm", [])
    if len(ids) <= 1:
        return _finding("crawl.single_container", Status.PASS, "Single GTM container")
    return _finding(
        "crawl.single_container",
        Status.FAIL,
        f"{len(ids)} GTM containers on one page",
        f"Containers: {', '.join(ids)}. Multiple containers cause conflicts and duplicate data.",
        affected_items=[{"container_id": i} for i in ids],
    )


def check_container_parsed(d: dict) -> Finding:
    containers = d.get("containers", {})
    if not containers:
        return _finding("crawl.container_parsed", Status.NA, "No GTM containers to parse")
    failed = [cid for cid, c in containers.items() if not c.get("parsed", True)]
    if failed:
        return _finding(
            "crawl.container_parsed",
            Status.WARN,
            f"{len(failed)} container(s) could not be parsed",
            f"Unparsed: {', '.join(failed)}. Tag-level checks may be incomplete.",
            affected_items=[{"container_id": cid} for cid in failed],
        )
    return _finding("crawl.container_parsed", Status.PASS, "All containers parsed successfully")


def check_no_legacy_ua(d: dict) -> Finding:
    ua_ids = d.get("tag_ids", {}).get("ua", [])
    if ua_ids:
        return _finding(
            "crawl.no_legacy_ua",
            Status.WARN,
            f"Legacy Universal Analytics still loading: {', '.join(ua_ids)}",
            "UA properties stopped processing data on Jul 1 2024. These tags add "
            "weight without collecting useful data.",
            affected_items=[{"ua_id": uid} for uid in ua_ids],
            remediation_hint="Remove the UA property from your tagging. Migrate to GA4.",
        )
    return _finding("crawl.no_legacy_ua", Status.PASS, "No legacy UA properties detected")


def check_no_duplicate_measurement_ids(d: dict) -> Finding:
    containers = d.get("containers", {})
    if len(containers) < 2:
        return _finding(
            "crawl.no_duplicate_measurement_ids",
            Status.NA,
            "Single container — no cross-container duplication possible",
        )
    id_to_containers: dict[str, list[str]] = {}
    for cid, c in containers.items():
        for mid in c.get("measurement_ids", []):
            id_to_containers.setdefault(mid, []).append(cid)
    duplicates = {mid: cids for mid, cids in id_to_containers.items() if len(cids) > 1}
    if duplicates:
        detail = "; ".join(f"{mid} in {', '.join(cids)}" for mid, cids in duplicates.items())
        return _finding(
            "crawl.no_duplicate_measurement_ids",
            Status.FAIL,
            "Same measurement ID configured in multiple containers",
            f"Duplicate IDs will cause double-counted hits. {detail}",
            affected_items=[
                {"measurement_id": mid, "containers": cids} for mid, cids in duplicates.items()
            ],
        )
    return _finding(
        "crawl.no_duplicate_measurement_ids",
        Status.PASS,
        "No duplicate measurement IDs across containers",
    )


def check_no_hardcoded_ga4_duplicate(d: dict) -> Finding:
    ga4 = d.get("tag_ids", {}).get("ga4", [])
    ga4_in_gtm = _container_has(d.get("containers", {}), _ga4_types())
    if ga4 and ga4_in_gtm:
        return _finding(
            "crawl.no_hardcoded_ga4_duplicate",
            Status.FAIL,
            "GA4 loaded via GTM AND hardcoded gtag",
            f"Hardcoded gtag {', '.join(ga4)} fires while GTM also configures GA4 — hits are double-counted.",
            affected_items=[{"hardcoded_id": g} for g in ga4],
            remediation_hint="Remove the hardcoded gtag.js; let GTM handle GA4.",
        )
    if ga4:
        return _finding(
            "crawl.no_hardcoded_ga4_duplicate",
            Status.PASS,
            "GA4 via hardcoded gtag only (no GTM duplication detected)",
        )
    return _finding("crawl.no_hardcoded_ga4_duplicate", Status.PASS, "No hardcoded GA4 duplication")


def check_no_hardcoded_ads_duplicate(d: dict) -> Finding:
    ads = d.get("tag_ids", {}).get("ads", [])
    ads_in_gtm = _container_has(d.get("containers", {}), _ads_types())
    if ads and ads_in_gtm:
        return _finding(
            "crawl.no_hardcoded_ads_duplicate",
            Status.FAIL,
            "Google Ads loaded via GTM AND hardcoded",
            f"Hardcoded {', '.join(ads)} fires while GTM also has Ads tags.",
            affected_items=[{"hardcoded_id": a} for a in ads],
            remediation_hint="Remove the hardcoded Ads snippet; let GTM handle conversions.",
        )
    return _finding("crawl.no_hardcoded_ads_duplicate", Status.PASS, "No hardcoded Ads duplication")


def check_datalayer_present(d: dict) -> Finding:
    dl = d.get("datalayer", {})
    if dl.get("init") or dl.get("push"):
        return _finding("crawl.datalayer_present", Status.PASS, "dataLayer present")
    return _finding(
        "crawl.datalayer_present",
        Status.WARN,
        "No dataLayer detected",
        "No dataLayer init or push found; custom event data may not reach GTM.",
    )


def check_datalayer_push_order(d: dict) -> Finding:
    if d.get("datalayer", {}).get("push_before_gtm"):
        return _finding(
            "crawl.datalayer_push_order",
            Status.FAIL,
            "dataLayer.push() before GTM loads",
            "Events pushed before the GTM snippet initialises are lost.",
        )
    return _finding("crawl.datalayer_push_order", Status.PASS, "No pushes precede GTM")


def check_consent_mode(d: dict) -> Finding:
    consent = d.get("consent", {})
    has_ads = bool(d.get("tag_ids", {}).get("ads")) or _container_has(
        d.get("containers", {}), _ads_types()
    )
    has_consent = consent.get("consent_mode") or consent.get("cmps")
    if not has_ads:
        return _finding("crawl.consent_mode_present", Status.NA, "No advertising tags detected")
    if has_consent:
        cmp = ", ".join(consent.get("cmps") or []) or "Consent Mode"
        return _finding(
            "crawl.consent_mode_present", Status.PASS, f"Consent management detected ({cmp})"
        )
    return _finding(
        "crawl.consent_mode_present",
        Status.FAIL,
        "Advertising tags but no consent management",
        "Ad tags are present but no CMP or Google Consent Mode was detected.",
    )


def check_consent_signals(d: dict) -> Finding:
    net = d.get("network", {})
    if not net.get("collect_hits"):
        return _finding("crawl.consent_signals_sent", Status.NA, "No GA collect beacons observed")
    if net.get("gcs_seen"):
        return _finding(
            "crawl.consent_signals_sent", Status.PASS, "Consent signals (gcs/gcd) sent with hits"
        )
    return _finding(
        "crawl.consent_signals_sent",
        Status.WARN,
        "GA hits without gcs/gcd consent params",
        "Collect beacons observed but no consent-state parameters were attached.",
    )


def check_noscript_fallback(d: dict) -> Finding:
    if not d.get("tag_ids", {}).get("gtm"):
        return _finding("crawl.noscript_fallback", Status.NA, "No GTM installed")
    if d.get("noscript", {}).get("present"):
        return _finding("crawl.noscript_fallback", Status.PASS, "GTM <noscript> fallback present")
    return _finding(
        "crawl.noscript_fallback",
        Status.WARN,
        "GTM <noscript> fallback missing",
        "JS-disabled visitors won't be tracked without the <noscript> iframe.",
    )


def check_cross_domain_linker(d: dict) -> Finding:
    # Public crawl can only confirm linker presence, not intent — informational.
    if d.get("cross_domain", {}).get("linker_seen"):
        return _finding(
            "crawl.cross_domain_linker", Status.PASS, "Linker (_gl) decoration observed"
        )
    return _finding(
        "crawl.cross_domain_linker",
        Status.NA,
        "No linker decoration observed",
        "No _gl parameter seen; only relevant if cross-domain tracking is intended.",
    )


def check_server_side_transport(d: dict) -> Finding:
    net = d.get("network", {})
    if net.get("server_side"):
        return _finding(
            "crawl.server_side_transport",
            Status.PASS,
            "Server-side / first-party transport detected",
            f"GA hits sent to: {', '.join(net.get('server_side_urls') or [])}",
        )
    return _finding("crawl.server_side_transport", Status.NA, "No server-side transport detected")


def check_third_party_sprawl(d: dict) -> Finding:
    domains = d.get("third_party_domains", [])
    if len(domains) > 15:
        return _finding(
            "crawl.third_party_script_sprawl",
            Status.WARN,
            f"{len(domains)} third-party script domains",
            "A large number of external scripts can slow load and leak data.",
            affected_items=[{"domain": x} for x in domains],
        )
    return _finding(
        "crawl.third_party_script_sprawl",
        Status.PASS,
        f"{len(domains)} third-party script domains",
    )


def check_event_inventory(d: dict) -> Finding:
    events = d.get("container_summary", {}).get("events", [])
    firing = d.get("network", {}).get("firing_events", [])
    if not events and not firing:
        return _finding("crawl.event_inventory", Status.NA, "No GA4 events found in container")
    return _finding(
        "crawl.event_inventory",
        Status.PASS,
        f"{len(events)} GA4 events configured, {len(firing)} firing on load",
        f"Configured: {', '.join(events[:20])}{'…' if len(events) > 20 else ''}",
        evidence={"configured": events, "firing_on_load": firing},
    )


def check_event_naming(d: dict) -> Finding:
    events = d.get("container_summary", {}).get("events", [])
    if not events:
        return _finding("crawl.event_naming_convention", Status.NA, "No events to check")
    non_snake = [e for e in events if not SNAKE_CASE.match(e)]
    # casing-collision: same name differing only by case
    lowered: dict[str, list[str]] = {}
    for e in events:
        lowered.setdefault(e.lower(), []).append(e)
    collisions = [v for v in lowered.values() if len(set(v)) > 1]
    if non_snake or collisions:
        detail = ""
        if non_snake:
            detail += f"Non snake_case: {', '.join(non_snake[:10])}. "
        if collisions:
            detail += f"Casing duplicates: {collisions}."
        return _finding(
            "crawl.event_naming_convention",
            Status.WARN,
            "Inconsistent event naming",
            detail,
            affected_items=[{"event": e} for e in non_snake[:20]],
        )
    return _finding(
        "crawl.event_naming_convention", Status.PASS, "Consistent snake_case event names"
    )


def check_recommended_events(d: dict) -> Finding:
    events = set(d.get("container_summary", {}).get("events", []))
    if not events:
        return _finding("crawl.recommended_event_names", Status.NA, "No events to check")
    used = sorted(events & _recommended_events())
    if used:
        return _finding(
            "crawl.recommended_event_names",
            Status.PASS,
            f"{len(used)} Google recommended events used",
            f"Recommended: {', '.join(used)}",
        )
    return _finding(
        "crawl.recommended_event_names",
        Status.WARN,
        "No Google recommended event names detected",
        "Using reserved names (purchase, login, sign_up, …) unlocks standard reports.",
    )


def check_ecommerce_funnel(d: dict) -> Finding:
    cs = d.get("container_summary", {})
    events = set(cs.get("events", []))
    has_ecom = cs.get("ecommerce") or bool(events & set(_ecommerce_funnel()))
    if not has_ecom:
        return _finding("crawl.ecommerce_funnel", Status.NA, "No ecommerce events detected")
    funnel = _ecommerce_funnel()
    missing = [e for e in funnel if e not in events]
    if missing:
        return _finding(
            "crawl.ecommerce_funnel",
            Status.WARN,
            "Incomplete ecommerce funnel",
            f"Present: {sorted(events & set(funnel))}. Missing: {missing}.",
        )
    return _finding("crawl.ecommerce_funnel", Status.PASS, "Core ecommerce funnel complete")


def check_pii_in_events(d: dict) -> Finding:
    events = d.get("container_summary", {}).get("events", [])
    flagged = [e for e in events if _pii_token().search(e) or "@" in e]
    if flagged:
        return _finding(
            "crawl.no_pii_in_events",
            Status.FAIL,
            "Possible PII in event names",
            f"Event names look like PII: {', '.join(flagged[:10])}",
            affected_items=[{"event": e} for e in flagged],
        )
    return _finding("crawl.no_pii_in_events", Status.PASS, "No PII-looking event names")


def check_pii_in_network(d: dict) -> Finding:
    hosts = d.get("network", {}).get("pii_hosts", [])
    if hosts:
        return _finding(
            "crawl.no_pii_in_network",
            Status.FAIL,
            "PII detected in outgoing requests",
            f"Emails / PII params sent to: {', '.join(hosts)}",
            affected_items=[{"host": h} for h in hosts],
        )
    return _finding(
        "crawl.no_pii_in_network", Status.PASS, "No PII observed in request query strings"
    )


def check_enhanced_conversions(d: dict) -> Finding:
    cs = d.get("container_summary", {})
    signals = [
        k
        for k, on in (
            ("enhanced conversions / EUID", cs.get("enhanced_conversions")),
            ("user properties", cs.get("user_properties")),
        )
        if on
    ]
    if signals:
        return _finding(
            "crawl.enhanced_conversions_review",
            Status.WARN,
            "User-data collection enabled — verify consent",
            f"Container enables: {', '.join(signals)}. Confirm consent + hashing.",
        )
    return _finding(
        "crawl.enhanced_conversions_review", Status.NA, "No enhanced user-data collection detected"
    )


def check_custom_html_tags(d: dict) -> Finding:
    n = d.get("container_summary", {}).get("custom_html_count", 0)
    if n > 0:
        return _finding(
            "crawl.custom_html_tags",
            Status.WARN,
            f"{n} custom HTML/JS tag(s) in container",
            "Custom HTML tags warrant a security / performance / PII review.",
        )
    return _finding("crawl.custom_html_tags", Status.PASS, "No custom HTML tags")


def check_vendor_inventory(d: dict) -> Finding:
    vendors = d.get("vendors", [])
    if not vendors:
        return _finding("crawl.vendor_inventory", Status.NA, "No vendors detected")
    names = ", ".join(v["name"] for v in vendors)
    return _finding(
        "crawl.vendor_inventory",
        Status.PASS,
        f"{len(vendors)} martech vendor(s) detected",
        names,
        evidence={"vendors": vendors},
    )


def check_third_party_cookies(d: dict) -> Finding:
    ck = d.get("cookies", {})
    total, third = ck.get("total", 0), ck.get("third_party", 0)
    if not total:
        return _finding("crawl.third_party_cookies", Status.NA, "No cookies observed")
    status = Status.WARN if third > 10 else Status.PASS
    return _finding(
        "crawl.third_party_cookies",
        status,
        f"{third} third-party / {total} total cookies",
    )


ALL_CHECKS = (
    check_gtm_installed,
    check_gtm_in_head,
    check_single_container,
    check_container_parsed,
    check_no_legacy_ua,
    check_no_duplicate_measurement_ids,
    check_no_hardcoded_ga4_duplicate,
    check_no_hardcoded_ads_duplicate,
    check_datalayer_present,
    check_datalayer_push_order,
    check_consent_mode,
    check_consent_signals,
    check_noscript_fallback,
    check_cross_domain_linker,
    check_server_side_transport,
    check_third_party_sprawl,
    check_event_inventory,
    check_event_naming,
    check_recommended_events,
    check_ecommerce_funnel,
    check_pii_in_events,
    check_pii_in_network,
    check_enhanced_conversions,
    check_custom_html_tags,
    check_vendor_inventory,
    check_third_party_cookies,
)


def run_crawl_checks(snapshot_data: dict) -> list[Finding]:
    """Run every crawl check against a crawl snapshot's `data`."""
    return [check(snapshot_data) for check in ALL_CHECKS]
