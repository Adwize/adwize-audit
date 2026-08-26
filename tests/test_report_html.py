from pathlib import Path

from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult, ScorePenalty, Scores
from core.models.snapshot import Snapshot
from report import render_html, render_report

_ALLOWED_URL_PREFIXES = (
    "https://getadwize.com",
    "https://app.getadwize.com",
    "https://calendly.com",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
)


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
        Finding(
            checkpoint_id="crawl.consent_mode_present",
            status=Status.PASS,
            severity=Severity.HIGH,
            category="Privacy",
            source=Source.CRAWL,
            title="Consent management detected (OneTrust)",
        ),
    ]
    data = {
        "tag_ids": {"gtm": ["GTM-X"], "ga4": [], "ads": [], "ua": []},
        "container_summary": {
            "events": ["email_complete", "purchase"],
            "measurement_ids": ["G-XYZ"],
            "custom_html_count": 2,
        },
        "vendors": [{"name": "Meta Pixel", "category": "advertising"}],
        "consent": {"cmps": ["OneTrust"], "accepted": True},
        "cookies": {"total": 3, "third_party": 0},
        "network": {"server_side": True, "firing_events": ["purchase"]},
    }
    return AuditResult(
        target="https://example.com",
        snapshots=[Snapshot(collector="crawl", target="https://example.com", data=data)],
        findings=findings,
        scores=Scores(
            overall=82,
            grade="B",
            by_category={"Privacy": 88},
            counts={"pass": 2, "fail": 1},
            penalties=[
                ScorePenalty(
                    checkpoint_id="crawl.no_pii_in_events",
                    severity="high",
                    status="fail",
                    points=12,
                )
            ],
        ),
        summary="## Executive summary\nSolid base, one PII risk.\n\n## Priorities\n- **Fix PII** in events.\n",
    )


def test_html_omits_letter_grade_from_copy():
    r = _result()
    r.scores.grade = "E"
    r.summary = (
        "## Executive summary\nThe Grade E setup has duplicate pixels.\n\n"
        "## Priorities\n- Fix duplicates.\n"
    )
    html = render_html(r)
    assert "Grade E" not in html
    assert ">E<" not in html
    assert "duplicate pixels" in html


def test_html_is_self_contained_and_complete():
    html = render_html(_result(), generated_at="2026-07-21 12:00")
    assert html.startswith("<!doctype html>")
    assert "Measurement Audit" in html
    assert "example.com" in html
    assert ">B<" not in html  # letter grades stay off the client HTML
    assert "https://calendly.com/qt-datastarter/discovery-meeting" in html
    assert "email_complete" in html
    assert "Meta Pixel" in html
    assert "Findings" in html
    assert "Already in place" in html
    assert "Request invite" in html
    assert "collection layer" in html
    assert "Estimated to fix with an agency" not in html
    assert "Stack" in html
    assert "Checkout funnel" in html
    assert "What to do" in html
    assert "Missing" in html
    assert 'class="tag rec"' not in html
    assert "Event inventory" not in html
    assert 'class="fold" open' in html
    assert html.count('class="fold"') >= 3
    assert "Executive summary" in html and "<strong>Fix PII</strong>" in html
    assert "<script" not in html  # no JS
    assert "@media print" in html
    leftover = html.replace("https://example.com", "")
    for url in _ALLOWED_URL_PREFIXES:
        leftover = leftover.replace(url, "")
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
