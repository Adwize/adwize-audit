"""Load audit *schemas* (knowledge that changes over time) from YAML instead of
hardcoding it in functions.

Resolution order for each schema, so a maintainer agent can keep them current
without code changes:
  1. `$ADWIZE_SCHEMA_DIR/<name>.yaml` — the latest schema an agent has written
     (the "memory" location; see the schema-maintainer agent, Phase 2).
  2. the committed `core/schemas/<name>.yaml` — the last known-good fallback.

Callers should read schemas through this loader, never inline the values.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PACKAGED_DIR = Path(__file__).resolve().parent
OVERRIDE_ENV = "ADWIZE_SCHEMA_DIR"


def _override_dir() -> Path | None:
    d = os.getenv(OVERRIDE_ENV)
    return Path(d) if d else None


def schema_path(name: str) -> Path:
    """Path the loader will actually read for `name` (override wins if present)."""
    override = _override_dir()
    if override and (override / f"{name}.yaml").exists():
        return override / f"{name}.yaml"
    return PACKAGED_DIR / f"{name}.yaml"


@lru_cache
def load(name: str) -> dict[str, Any]:
    with schema_path(name).open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def clear_cache() -> None:
    """For tests / after an agent rewrites a schema."""
    load.cache_clear()
