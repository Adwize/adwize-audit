"""Public (OSS) audit engine: crawl a URL, run deterministic checks, score, and
optionally run the (key-gated) analysis agent.

No account access. The authenticated analyst edition wraps this with API
collectors + the multi-agent graph in the private repo.
"""

from __future__ import annotations

from agents.analyst import agent
from core.checks.crawl_checks import run_crawl_checks
from core.collectors import crawl
from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult, Scores
from core.scoring import score


async def run_scan(
    url: str,
    timeout: float = 20.0,
    containers: list[str] | None = None,
    accept_consent: bool = True,
    analyze: bool = True,
    model: str | None = None,
    max_pages: int = 5,
    extra_pages: list[str] | None = None,
) -> AuditResult:
    """Crawl `url` (homepage + key internal pages), evaluate the crawl
    checkpoints, score, and (if a key is configured) attach an LLM analyst brief.

    `max_pages` bounds how many pages are crawled/aggregated; `extra_pages` adds
    explicit URLs; `containers` force-fetches known GTM container IDs;
    `accept_consent` simulates clicking a CMP's "accept all".
    """
    snapshot = await crawl.collect(
        url,
        timeout=timeout,
        extra_containers=containers,
        accept_consent=accept_consent,
        max_pages=max_pages,
        extra_pages=extra_pages,
    )

    if snapshot.ok:
        findings: list[Finding] = run_crawl_checks(snapshot.data)
        scores: Scores = score(findings)
    else:
        findings = [
            Finding(
                checkpoint_id="crawl.scan_failed",
                status=Status.FAIL,
                severity=Severity.CRITICAL,
                category="Data Collection",
                source=Source.CRAWL,
                title="Crawl failed — site could not be scanned",
                detail=f"Error: {snapshot.error or 'unknown'}. "
                "The page may be unreachable, blocking bots, or timing out.",
                remediation_hint="Verify the URL is accessible and try increasing --timeout.",
            )
        ]
        scores = Scores(overall=0, grade="E", counts={"fail": 1})
    result = AuditResult(
        target=snapshot.target,
        edition="oss",
        snapshots=[snapshot],
        findings=findings,
        scores=scores,
    )

    if analyze and snapshot.ok:
        outcome = await agent.run(result, model=model)
        result.summary = outcome.summary
        result.analysis_status = outcome.status
        result.analysis_detail = outcome.detail or None

    return result
