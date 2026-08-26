"""Multi-page crawl: link discovery + per-page signal aggregation (both pure)."""

from core.collectors.crawl import discover_links, merge_signals

HTML = """
<html><body>
<a href="/products/yoga-retreat">Product</a>
<a href="/cart">Cart</a>
<a href="/checkout">Checkout</a>
<a href="/contact-us">Contact</a>
<a href="/about">About</a>
<a href="https://external.example.org/x">External</a>
<a href="mailto:hi@example.com">Mail</a>
<a href="/products/yoga-retreat">Dup product</a>
</body></html>
"""


def test_discover_links_prioritizes_key_pages_and_stays_internal():
    links = discover_links("https://shop.example.com/", HTML, limit=4)
    assert len(links) == 4
    joined = " ".join(links)
    # key page types selected first
    assert any("/checkout" in x for x in links)
    assert any("/cart" in x for x in links)
    assert any("/products/" in x for x in links)
    # never leaves the site, never mailto, no dup paths
    assert "external.example.org" not in joined
    assert "mailto:" not in joined
    assert len(links) == len(set(links))


def test_merge_signals_unions_and_ors():
    home = {
        "tag_ids": {"ga4": [], "ads": [], "ua": [], "gtm": ["GTM-A"]},
        "gtm_in_head": True,
        "datalayer": {"init": True, "push": False, "push_before_gtm": False},
        "consent": {
            "consent_mode": True,
            "cmps": ["OneTrust"],
            "signals_seen": False,
            "accepted": True,
            "accepted_cmp": "OneTrust",
        },
        "noscript": {"present": True, "ids": ["GTM-A"]},
        "cross_domain": {"linker_seen": False},
        "third_party_domains": ["a.com"],
        "network": {
            "collect_hits": 1,
            "gcs_seen": False,
            "server_side": False,
            "server_side_urls": [],
            "firing_events": ["page_view"],
            "pii_hosts": [],
            "pii_hits": [],
        },
        "cookies": {"total": 3, "third_party": 0},
        "vendors": [{"name": "OneTrust", "category": "consent"}],
    }
    checkout = {
        "tag_ids": {"ga4": [], "ads": [], "ua": [], "gtm": ["GTM-A"]},
        "gtm_in_head": False,  # worse on this page
        "datalayer": {"init": True, "push": True, "push_before_gtm": True},  # problem here
        "consent": {
            "consent_mode": True,
            "cmps": ["OneTrust"],
            "signals_seen": True,
            "accepted": True,
            "accepted_cmp": "OneTrust",
        },
        "noscript": {"present": False, "ids": []},
        "cross_domain": {"linker_seen": True},
        "third_party_domains": ["b.com"],
        "network": {
            "collect_hits": 4,
            "gcs_seen": True,
            "server_side": True,
            "server_side_urls": ["https://sgtm.x/g/collect"],
            "firing_events": ["purchase"],
            "pii_hosts": ["leaky.example.com"],
            "pii_hits": [
                {"host": "leaky.example.com", "kinds": ["email"], "bucket": "other"}
            ],
        },
        "cookies": {"total": 9, "third_party": 5},
        "vendors": [{"name": "Meta Pixel", "category": "advertising"}],
    }
    pages = [
        {"url": "https://x/", "http_status": 200},
        {"url": "https://x/checkout", "http_status": 200},
    ]
    m = merge_signals([home, checkout], containers={}, pages=pages)

    assert m["pages_scanned"] == 2
    assert m["gtm_in_head"] is False  # not in head on every page → flagged
    assert m["datalayer"]["push_before_gtm"] is True  # problem OR'd in
    assert set(m["network"]["firing_events"]) == {"page_view", "purchase"}  # union across pages
    assert m["network"]["collect_hits"] == 5  # summed
    assert m["network"]["server_side"] is True
    assert m["network"]["pii_hosts"] == ["leaky.example.com"]
    assert m["network"]["pii_hits"] == [
        {"host": "leaky.example.com", "kinds": ["email"], "bucket": "other"}
    ]
    assert m["cookies"]["third_party"] == 5  # max
    assert {v["name"] for v in m["vendors"]} == {"OneTrust", "Meta Pixel"}
    assert m["consent"]["signals_seen"] is True
