from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult, Scores
from core.models.snapshot import Snapshot
from report import executive_summary, render_markdown


def _result():
    findings = [
        Finding(
            checkpoint_id="crawl.no_pii_in_events",
            status=Status.FAIL,
            severity=Severity.HIGH,
            category="Privacy",
            source=Source.CRAWL,
            title="Possible PII in event names",
            detail="Event names look like PII.",
            affected_items=[{"event": "email_complete"}],
        ),
        Finding(
            checkpoint_id="crawl.gtm_installed",
            status=Status.PASS,
            severity=Severity.CRITICAL,
            category="Data Collection",
            source=Source.CRAWL,
            title="GTM installed",
        ),
    ]
    data = {
        "tag_ids": {"gtm": ["GTM-X"], "ga4": [], "ads": [], "ua": []},
        "container_summary": {
            "events": ["email_complete", "purchase"],
            "measurement_ids": ["G-XYZ"],
        },
        "vendors": [{"name": "Meta Pixel", "category": "advertising"}],
        "consent": {"cmps": ["OneTrust"], "accepted": True},
        "cookies": {"total": 3, "third_party": 0},
    }
    return AuditResult(
        target="https://example.com",
        snapshots=[Snapshot(collector="crawl", target="https://example.com", data=data)],
        findings=findings,
        scores=Scores(
            overall=82, grade="B", by_category={"Privacy": 88}, counts={"pass": 1, "fail": 1}
        ),
        summary="## Executive summary\nSolid base, one PII risk.\n\n## Findings deep-dive\n- detail\n",
    )


def test_markdown_contains_sections_and_evidence():
    md = render_markdown(_result(), generated_at="2026-07-17 12:00")
    assert "# Measurement Audit — https://example.com" in md
    assert "Grade B — 82/100" in md
    assert "## Analysis" in md and "Executive summary" in md
    assert "Possible PII in event names" in md
    assert "email_complete" in md  # affected item / event inventory
    assert "## Measurement inventory" in md
    assert "Meta Pixel" in md
    assert "GTM-X" in md


def test_executive_summary_extracts_first_section():
    brief = "## Executive summary\nThe key point.\n\n## Findings deep-dive\nlots of detail"
    assert executive_summary(brief) == "The key point."


def test_executive_summary_falls_back_to_whole_text():
    assert executive_summary("no headings here") == "no headings here"
