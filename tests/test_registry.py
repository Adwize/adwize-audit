from core.models.enums import Source
from core.registry import loader


def test_registry_loads_and_merges():
    cps = loader.load_checkpoints()
    assert len(cps) > 60  # CSV-derived + crawl-native
    ids = {c.id for c in cps}
    # crawl-native present
    assert "crawl.gtm_installed" in ids
    assert "crawl.no_hardcoded_ga4_duplicate" in ids
    # CSV-derived present
    assert any(c.id.startswith("ga4.") for c in cps)


def test_ids_unique():
    cps = loader.load_checkpoints()
    ids = [c.id for c in cps]
    assert len(ids) == len(set(ids))


def test_crawl_checkpoints_are_crawl_source():
    for c in loader.by_collector("crawl"):
        assert c.source == Source.CRAWL


def test_get_returns_checkpoint():
    cp = loader.get("crawl.gtm_installed")
    assert cp is not None
    assert cp.severity.value == "critical"
