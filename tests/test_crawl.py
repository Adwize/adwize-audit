from core.collectors.crawl import extract_signals

GOOD_HTML = """
<html><head>
<script>dataLayer = [];</script>
<script>(function(){/* gtm */})();//googletagmanager.com/gtm.js?id=GTM-GOOD1</script>
<script src="https://consent.cookiebot.com/uc.js"></script>
<script>gtag('consent','default',{});</script>
</head><body>
<noscript><iframe src="https://www.googletagmanager.com/ns.html?id=GTM-GOOD1"></iframe></noscript>
<script>dataLayer.push({event:'x'});</script>
</body></html>
"""

# GTM loader references the dataLayer via a variable (`w[l]=w[l]||[]`), so there
# is no literal `dataLayer = [` or `dataLayer.push(` for the regex to match.
GTM_ONLY_HTML = """
<html><head>
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':new Date().getTime()});})(window,document,'script','dataLayer','GTM-RUNTIME');</script>
<script src="https://www.googletagmanager.com/gtm.js?id=GTM-RUNTIME"></script>
</head><body></body></html>
"""

# hardcoded gtag G- in the page AND GTM container also configures GA4 → duplicate
DUP_HTML = """
<html><head>
<script src="https://www.googletagmanager.com/gtag/js?id=G-DUP999"></script>
<script>//googletagmanager.com/gtm.js?id=GTM-DUP1</script>
<script>//googletagmanager.com/gtm.js?id=GTM-DUP2</script>
</head><body></body></html>
"""


def _statuses(findings):
    return {f.checkpoint_id: f.status.value for f in findings}


def test_extract_signals_good_site():
    d = extract_signals(GOOD_HTML, request_urls=[], containers={})
    assert d["tag_ids"]["gtm"] == ["GTM-GOOD1"]
    assert d["gtm_in_head"] is True
    assert d["datalayer"]["init"] is True
    assert d["datalayer"]["push"] is True
    assert d["datalayer"]["push_before_gtm"] is False
    assert "Cookiebot" in d["consent"]["cmps"]
    assert d["consent"]["consent_mode"] is True
    assert d["noscript"]["present"] is True


def test_good_site_checks_pass():
    from core.checks.crawl_checks import run_crawl_checks

    d = extract_signals(GOOD_HTML, request_urls=[], containers={})
    st = _statuses(run_crawl_checks(d))
    assert st["crawl.gtm_installed"] == "pass"
    assert st["crawl.gtm_in_head"] == "pass"
    assert st["crawl.single_container"] == "pass"
    assert st["crawl.datalayer_push_order"] == "pass"


def test_duplicate_and_multi_container_detected():
    from core.checks.crawl_checks import run_crawl_checks

    containers = {
        "GTM-DUP1": {"parsed": True, "tags": [{"type": "gaawc"}]},
        "GTM-DUP2": {"parsed": True, "tags": []},
    }
    d = extract_signals(DUP_HTML, request_urls=[], containers=containers)
    st = _statuses(run_crawl_checks(d))
    assert st["crawl.no_hardcoded_ga4_duplicate"] == "fail"
    assert st["crawl.single_container"] == "fail"


def test_consent_signals_from_network():
    from core.checks.crawl_checks import run_crawl_checks

    urls = ["https://www.google-analytics.com/g/collect?tid=G-X&gcs=G111"]
    d = extract_signals(GOOD_HTML, request_urls=urls, containers={})
    st = _statuses(run_crawl_checks(d))
    assert d["network"]["gcs_seen"] is True
    assert st["crawl.consent_signals_sent"] == "pass"


def test_server_side_transport_detected():
    urls = ["https://sgtm.example.com/g/collect?tid=G-X"]
    d = extract_signals(GOOD_HTML, request_urls=urls, containers={})
    assert d["network"]["server_side"] is True


def test_datalayer_runtime_detection_passes():
    from core.checks.crawl_checks import run_crawl_checks

    # No literal init/push in the HTML, but the browser reports window.dataLayer
    # exists at runtime → dataLayer is present.
    d = extract_signals(
        GTM_ONLY_HTML,
        request_urls=[],
        containers={},
        datalayer_runtime={"exists": True, "length": 2},
    )
    assert d["datalayer"]["init"] is False
    assert d["datalayer"]["push"] is False
    assert d["datalayer"]["exists"] is True
    assert d["datalayer"]["length"] == 2
    st = _statuses(run_crawl_checks(d))
    assert st["crawl.datalayer_present"] == "pass"


def test_datalayer_absent_without_runtime_or_literal():
    from core.checks.crawl_checks import run_crawl_checks

    # No literal init/push and no runtime signal → warn.
    d = extract_signals(GTM_ONLY_HTML, request_urls=[], containers={})
    assert d["datalayer"]["exists"] is False
    st = _statuses(run_crawl_checks(d))
    assert st["crawl.datalayer_present"] == "warn"
