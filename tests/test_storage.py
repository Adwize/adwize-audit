import pytest

from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.models.result import AuditResult
from core.models.snapshot import Snapshot
from core.scoring import score
from storage import repository


def _result():
    findings = [
        Finding(
            checkpoint_id="crawl.gtm_installed",
            status=Status.PASS,
            severity=Severity.CRITICAL,
            category="Data Collection",
            source=Source.CRAWL,
            title="GTM installed",
        ),
        Finding(
            checkpoint_id="crawl.single_container",
            status=Status.FAIL,
            severity=Severity.HIGH,
            category="Data Collection",
            source=Source.CRAWL,
            title="2 containers",
        ),
    ]
    return AuditResult(
        target="https://example.com",
        snapshots=[Snapshot(collector="crawl", target="https://example.com", data={"x": 1})],
        findings=findings,
        scores=score(findings),
    )


@pytest.mark.asyncio
async def test_save_and_load_roundtrip():
    run_id = await repository.save_result(_result())
    assert run_id > 0

    run = await repository.get_run(run_id)
    assert run is not None
    assert run.target == "https://example.com"
    assert run.grade == "B"  # one high fail = -12
    assert len(run.findings) == 2
    assert len(run.snapshots) == 1

    runs = await repository.list_runs(target="https://example.com")
    assert any(r.id == run_id for r in runs)
