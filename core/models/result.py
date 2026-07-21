from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.finding import Finding
from core.models.snapshot import Snapshot


class ScorePenalty(BaseModel):
    """One penalty applied to the 100-point score."""

    checkpoint_id: str
    severity: str
    status: str  # fail or warn
    points: int  # how many points deducted


class Scores(BaseModel):
    overall: int  # 0-100
    grade: str  # A-E
    by_category: dict[str, int] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)  # status -> count
    penalties: list[ScorePenalty] = Field(default_factory=list)


class AuditResult(BaseModel):
    target: str
    edition: str = "oss"  # oss (crawl) | analyst (authenticated)
    snapshots: list[Snapshot] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    scores: Scores
    summary: str | None = None  # optional LLM narrative
    analysis_status: str | None = None  # ran | no_key | no_tracking | no_package | error
    analysis_detail: str | None = None  # failure reason when status == error
    documents: dict[str, str] = Field(default_factory=dict)  # doc-writer outputs, name -> markdown
    agent_traces: list[dict] = Field(default_factory=list)  # multi-agent graph step traces
