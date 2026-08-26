"""The audit knowledge (GTM functions, vendors, CMPs, GA4 events, PII) lives in
YAML schemas, resolved as: agent-written override dir → committed fallback."""

from core.schemas import loader


def test_committed_schemas_load():
    assert loader.load("gtm_functions")["functions"]["__gaawe"]["type"] == "gaawe"
    assert any(v["name"] == "Meta Pixel" for v in loader.load("vendors")["vendors"])
    assert any(c["name"] == "Didomi" for c in loader.load("cmp")["cmps"])
    assert "purchase" in loader.load("ga4_events")["recommended"]
    pii = loader.load("pii")
    assert "analytics_host_pattern" in pii
    assert "crm_host_pattern" in pii


def test_override_dir_wins(tmp_path, monkeypatch):
    # an agent writes a newer schema to the override dir → loader must prefer it
    (tmp_path / "vendors.yaml").write_text(
        "vendors:\n  - {name: FutureVendor, category: analytics, pattern: 'futurevendor'}\n"
    )
    monkeypatch.setenv(loader.OVERRIDE_ENV, str(tmp_path))
    loader.clear_cache()
    try:
        names = {v["name"] for v in loader.load("vendors")["vendors"]}
        assert names == {"FutureVendor"}
    finally:
        monkeypatch.delenv(loader.OVERRIDE_ENV, raising=False)
        loader.clear_cache()


def test_fallback_to_committed_when_override_missing(tmp_path, monkeypatch):
    # override dir set but no cmp.yaml there → falls back to committed schema
    monkeypatch.setenv(loader.OVERRIDE_ENV, str(tmp_path))
    loader.clear_cache()
    try:
        assert any(c["name"] == "OneTrust" for c in loader.load("cmp")["cmps"])
    finally:
        monkeypatch.delenv(loader.OVERRIDE_ENV, raising=False)
        loader.clear_cache()
