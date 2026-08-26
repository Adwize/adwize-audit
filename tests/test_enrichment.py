"""Tests for the enriched crawl signals (container summary, vendors, network
beacons, PII) and the checks that consume them."""

from core.checks.crawl_checks import run_crawl_checks
from core.collectors import vendors
from core.collectors.crawl import extract_signals


def _statuses(findings):
    return {f.checkpoint_id: f.status.value for f in findings}


def _findings_by_id(findings):
    return {f.checkpoint_id: f for f in findings}


HTML = "<html><head>//googletagmanager.com/gtm.js?id=GTM-X</head><body></body></html>"


def test_vendor_detection():
    html = '<script src="https://connect.facebook.net/en_US/fbevents.js"></script>'
    urls = ["https://bat.bing.com/bat.js", "https://t.contentsquare.net/uxa.js"]
    found = {v["name"] for v in vendors.detect(html, urls)}
    assert "Meta Pixel" in found
    assert "Microsoft/Bing UET" in found
    assert "Contentsquare" in found


def test_event_inventory_and_naming_and_ecommerce():
    containers = {
        "GTM-X": {
            "events": ["add_to_cart", "begin_checkout", "view_item", "purchase", "BadName"],
            "measurement_ids": ["G-ABC123"],
            "ecommerce": True,
            "custom_html_count": 2,
            "enhanced_conversions": True,
            "user_properties": True,
            "has_ga4": True,
        }
    }
    d = extract_signals(HTML, request_urls=[], containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))

    assert fb["crawl.event_inventory"].status.value == "pass"
    assert "5 GA4 events" in fb["crawl.event_inventory"].title
    # BadName is not snake_case → warn
    assert fb["crawl.event_naming_convention"].status.value == "warn"
    # full funnel present → pass
    assert fb["crawl.ecommerce_funnel"].status.value == "pass"
    # recommended names used
    assert fb["crawl.recommended_event_names"].status.value == "pass"
    # custom html present → warn
    assert fb["crawl.custom_html_tags"].status.value == "warn"
    # enhanced conversions → warn (verify consent)
    assert fb["crawl.enhanced_conversions_review"].status.value == "warn"


def test_pii_detection_in_events_and_network():
    # A PII-token event name corroborated by email in an unknown-host URL →
    # event names warn. The network hit is a review warning, not a critical leak.
    containers = {"GTM-X": {"events": ["purchase", "user_email_submit"], "has_ga4": True}}
    urls = ["https://collector.example.com/track?email=jane@doe.com"]
    d = extract_signals(HTML, request_urls=urls, containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))
    assert fb["crawl.no_pii_in_events"].status.value == "warn"
    net = fb["crawl.no_pii_in_network"]
    assert net.status.value == "warn"
    assert net.severity.value == "medium"
    assert "leak" not in net.title.lower()
    assert d["network"]["pii_hits"][0]["bucket"] == "other"


def test_pii_in_analytics_url_is_a_fail():
    urls = ["https://www.google-analytics.com/g/collect?en=page_view&email=jane@doe.com"]
    d = extract_signals(HTML, request_urls=urls, containers={})
    fb = _findings_by_id(run_crawl_checks(d))
    f = fb["crawl.no_pii_in_network"]
    assert f.status.value == "fail"
    assert f.severity.value == "critical"
    assert "Google Analytics" in f.title
    assert "jane@" not in f.title
    assert d["network"]["pii_hits"][0]["bucket"] == "analytics"


def test_pii_in_hubspot_url_is_a_crm_warn_not_a_leak():
    urls = ["https://api.hubspot.com/analytics/v2/events?email=jane@doe.com"]
    d = extract_signals(HTML, request_urls=urls, containers={})
    fb = _findings_by_id(run_crawl_checks(d))
    f = fb["crawl.no_pii_in_network"]
    assert f.status.value == "warn"
    assert f.severity.value == "medium"
    assert "HubSpot" in f.title
    assert "leak" not in f.title.lower()
    assert "leak" not in f.detail.lower()
    assert "jane@" not in f.title and "jane@" not in f.detail
    assert d["network"]["pii_hits"][0]["bucket"] == "crm"


def test_pii_event_name_without_evidence_passes():
    # Step-label event names that merely contain the word "email"/"phone" but with
    # no actual PII value, no user-data flags, and no PII leaving the site must NOT
    # be flagged (this was the bookretreats.com false positive).
    containers = {
        "GTM-X": {
            "events": ["contacthost_step4_email", "email_complete", "purchase"],
            "has_ga4": True,
        }
    }
    d = extract_signals(HTML, request_urls=[], containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))
    assert fb["crawl.no_pii_in_events"].status.value == "pass"


def test_pii_event_name_with_user_data_warns():
    # PII-token event name + the container collects user data → warn.
    containers = {
        "GTM-X": {"events": ["purchase", "phone_verify"], "user_properties": True, "has_ga4": True}
    }
    d = extract_signals(HTML, request_urls=[], containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))
    assert fb["crawl.no_pii_in_events"].status.value == "warn"


def test_actual_email_in_event_name_warns():
    # An event name embedding a real email address is a strong signal → warn.
    containers = {"GTM-X": {"events": ["signup_jane@doe.com"], "has_ga4": True}}
    d = extract_signals(HTML, request_urls=[], containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))
    assert fb["crawl.no_pii_in_events"].status.value == "warn"


def test_incomplete_ecommerce_funnel_warns():
    containers = {
        "GTM-X": {"events": ["add_to_cart", "view_item"], "ecommerce": True, "has_ga4": True}
    }
    d = extract_signals(HTML, request_urls=[], containers=containers)
    fb = _findings_by_id(run_crawl_checks(d))
    f = fb["crawl.ecommerce_funnel"]
    assert f.status.value == "warn"
    assert "begin_checkout" in f.detail and "purchase" in f.detail


def test_network_firing_events_extracted():
    urls = [
        "https://www.google-analytics.com/g/collect?en=page_view&tid=G-X",
        "https://www.google-analytics.com/g/collect?en=add_to_cart&tid=G-X&gcs=G111",
    ]
    d = extract_signals(HTML, request_urls=urls, containers={})
    assert set(d["network"]["firing_events"]) == {"page_view", "add_to_cart"}
    assert d["network"]["gcs_seen"] is True
