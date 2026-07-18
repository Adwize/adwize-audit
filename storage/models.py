from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(2048), index=True)
    edition: Mapped[str] = mapped_column(String(32), default="oss")
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(2), default="E")
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    snapshots: Mapped[list["SnapshotRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )
    findings: Mapped[list["FindingRow"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class SnapshotRow(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), index=True)
    collector: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(2048))
    ok: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[AuditRun] = relationship(back_populates="snapshots")


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), index=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(8))
    severity: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(512))
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    affected_items: Mapped[list] = mapped_column(JSON, default=list)
    remediation_hint: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[AuditRun] = relationship(back_populates="findings")
