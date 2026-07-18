from __future__ import annotations

from pydantic import BaseModel

from core.models.enums import Automation, Severity, Source


class Checkpoint(BaseModel):
    """A single auditable item, derived from the audit-entries registry."""

    id: str
    category: str  # Configuration | Integrations | Data Collection | Data Quality | ...
    tool: str  # GA4 | GTM | GTM SS | Google Ads | BigQuery | Reporting
    description: str
    how_to_check: str = ""
    source: Source = Source.API
    automation: Automation = Automation.AUTO
    collector: str | None = None  # which collector produces the snapshot this check reads
    api_ref: str = ""
    severity: Severity = Severity.MEDIUM

    model_config = {"use_enum_values": False}
