"""The analysis agent is key-gated: no OPENAI_API_KEY → it never runs (and never
makes a network call)."""

import pytest

from agents.analyst import agent
from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult, Scores
from core.models.snapshot import Snapshot


def _result(with_tracking=True):
    data = (
        {"tag_ids": {"gtm": ["GTM-X"], "ga4": [], "ads": [], "ua": []}}
        if with_tracking
        else {"tag_ids": {"gtm": [], "ga4": [], "ads": [], "ua": []}}
    )
    return AuditResult(
        target="https://example.com",
        snapshots=[Snapshot(collector="crawl", target="https://example.com", data=data)],
        findings=[
            Finding(
                checkpoint_id="crawl.gtm_installed",
                status=Status.PASS,
                severity=Severity.CRITICAL,
                category="Data Collection",
                source=Source.CRAWL,
                title="GTM installed",
            )
        ],
        scores=Scores(overall=90, grade="A"),
    )


@pytest.mark.asyncio
async def test_skips_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    outcome = await agent.run(_result())
    assert outcome.status == "no_key"
    assert outcome.summary is None


@pytest.mark.asyncio
async def test_skips_when_no_tracking(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # no tags detected → nothing to analyze, so no network call is attempted
    outcome = await agent.run(_result(with_tracking=False))
    assert outcome.status == "no_tracking"


@pytest.mark.asyncio
async def test_analyze_wrapper_returns_none_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert await agent.analyze(_result()) is None
