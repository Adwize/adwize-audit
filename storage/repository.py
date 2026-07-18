from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.models.result import AuditResult
from storage.database import init_db, session
from storage.models import AuditRun, FindingRow, SnapshotRow


async def save_result(result: AuditResult) -> int:
    """Persist an audit result; returns the new run id."""
    await init_db()
    async with session() as s:
        run = AuditRun(
            target=result.target,
            edition=result.edition,
            overall_score=result.scores.overall,
            grade=result.scores.grade,
            scores=result.scores.model_dump(),
            summary=result.summary,
            analysis_status=result.analysis_status,
            analysis_detail=result.analysis_detail,
        )
        run.snapshots = [
            SnapshotRow(
                collector=sn.collector,
                target=sn.target,
                ok=sn.ok,
                error=sn.error,
                data=sn.data,
            )
            for sn in result.snapshots
        ]
        run.findings = [
            FindingRow(
                checkpoint_id=f.checkpoint_id,
                status=f.status.value,
                severity=f.severity.value,
                category=f.category,
                source=f.source.value,
                title=f.title,
                detail=f.detail,
                evidence=f.evidence,
                affected_items=f.affected_items,
                remediation_hint=f.remediation_hint,
            )
            for f in result.findings
        ]
        s.add(run)
        await s.commit()
        return run.id


async def list_runs(target: str | None = None, limit: int = 20) -> list[AuditRun]:
    await init_db()
    async with session() as s:
        stmt = select(AuditRun).order_by(AuditRun.created_at.desc()).limit(limit)
        if target:
            stmt = stmt.where(AuditRun.target == target)
        return list((await s.execute(stmt)).scalars().all())


async def get_run(run_id: int) -> AuditRun | None:
    await init_db()
    async with session() as s:
        stmt = (
            select(AuditRun)
            .where(AuditRun.id == run_id)
            .options(selectinload(AuditRun.findings), selectinload(AuditRun.snapshots))
        )
        return (await s.execute(stmt)).scalars().first()
