from core.collectors.gtm_container import parse_container

SAMPLE = """
var data = {
  "resource": {
    "version":"42",
    "macros":[{"function":"__e"}],
    "tags":[
      {"function":"__gaawc","vtp_measurementId":"G-ABC123"},
      {"function":"__gaawe","vtp_eventName":"purchase"},
      {"function":"__awct","vtp_conversionId":"AW-999"},
      {"function":"__cl"}
    ],
    "predicates":[],
    "rules":[]
  },
  "runtime":[[],[]]
};
"""


def test_parse_extracts_tags_and_types():
    c = parse_container(SAMPLE, "GTM-TEST")
    assert c["parsed"] is True
    assert c["id"] == "GTM-TEST"
    assert c["tag_count"] == 4
    types = {t["type"] for t in c["tags"]}
    assert "gaawc" in types  # GA4 config
    assert "gaawe" in types  # GA4 event
    assert "awct" in types  # Ads conversion


def test_parse_extracts_events_ids_and_summary():
    c = parse_container(SAMPLE, "GTM-TEST")
    assert c["events"] == ["purchase"]  # from vtp_eventName on the __gaawe tag
    assert "G-ABC123" in c["measurement_ids"]
    assert c["has_ga4"] is True
    assert c["has_ads"] is True
    assert c["event_tag_count"] == 1


def test_parse_failure_is_graceful():
    c = parse_container("not a container", "GTM-NOPE")
    assert c["parsed"] is False
    assert c["tags"] == []
    assert c["tag_count"] == 0
