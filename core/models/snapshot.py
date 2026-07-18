from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Snapshot(BaseModel):
    """Raw, normalized output of one collector for one target.

    Stored verbatim so runs are reproducible, diffable, and re-analyzable offline.
    """

    collector: str  # e.g. "crawl", "ga4_admin", "gtm"
    target: str  # url or resource id the snapshot describes
    ok: bool = True  # did collection succeed
    error: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
