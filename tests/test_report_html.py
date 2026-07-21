from pathlib import Path

from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult, Scores
from core.models.snapshot import Snapshot
from report import render_html, render_report


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
            remediation_hint="Rename events to remove PII.",
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
        summary="## Executive summary\nSolid base, one PII risk.\n\n## Priorities\n- **Fix PII** in events.\n",
    )


def test_html_is_self_contained_and_complete():
    html = render_html(_result(), generated_at="2026-07-21 12:00")
    assert html.startswith("<!doctype html>")
    assert "Measurement Audit" in html and "Grade" not in html[:20]  # gauge shows grade
    assert ">B<" in html  # grade in gauge
    assert "Possible PII in event names" in html
    assert "email_complete" in html
    assert "Meta Pixel" in html
    assert "Executive summary" in html and "<strong>Fix PII</strong>" in html
    assert "<script" not in html  # no JS
    assert "@media print" in html  # print-friendly
    # self-contained: the only URLs present are the audited target, no CDNs/assets
    leftover = html.replace("https://example.com", "")
    assert "http://" not in leftover and "https://" not in leftover


def test_html_escapes_content():
    r = _result()
    r.target = "https://evil.com/<script>alert(1)</script>"
    html = render_html(r)
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_render_report_infers_format(tmp_path: Path):
    r = _result()
    assert render_report(r, tmp_path / "a.html").startswith("<!doctype html>")
    assert render_report(r, tmp_path / "a.md").startswith("# Measurement Audit")
    assert render_report(r, tmp_path / "a.markdown").startswith("# Measurement Audit")
