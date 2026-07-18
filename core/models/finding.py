from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from core.models.enums import Severity, Source, Status


class Finding(BaseModel):
    """The outcome of evaluating a checkpoint against a collected snapshot."""

    checkpoint_id: str
    status: Status
    severity: Severity
    category: str
    source: Source
    title: str
    detail: str = ""
    evidence: dict[str, Any] = Field(default_factory=dict)
    affected_items: list[dict[str, Any]] = Field(default_factory=list)
    remediation_hint: str = ""

    @property
    def is_problem(self) -> bool:
        return self.status in (Status.FAIL, Status.WARN)
