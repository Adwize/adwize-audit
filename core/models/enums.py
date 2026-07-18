from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

    @property
    def weight(self) -> int:
        """Higher = more severe. Used for ordering and scoring."""
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[self.value]


class Status(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    NA = "na"  # not applicable / could not be checked


class Source(str, Enum):
    API = "api"  # authenticated Google API
    CRAWL = "crawl"  # public-source website crawl
    UI = "ui"  # UI-only, not machine-checkable — flag for the analyst


class Automation(str, Enum):
    AUTO = "auto"  # fully automated check
    SEMI = "semi"  # automated signal, needs analyst judgement
    MANUAL = "manual"  # analyst must verify by hand
