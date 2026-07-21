from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from core.models.checkpoint import Checkpoint

REGISTRY_DIR = Path(__file__).resolve().parent
# CSV-derived (authenticated) + hand-maintained crawl-native (public) checkpoints.
YAML_FILES = ("checkpoints.yaml", "crawl_checkpoints.yaml", "gtm_auth_checkpoints.yaml")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return raw.get("checkpoints", [])


@lru_cache
def load_checkpoints() -> tuple[Checkpoint, ...]:
    """Load the merged checkpoint registry (authenticated + crawl-native)."""
    seen: set[str] = set()
    out: list[Checkpoint] = []
    for name in YAML_FILES:
        for c in _read(REGISTRY_DIR / name):
            cp = Checkpoint(**c)
            if cp.id in seen:
                continue
            seen.add(cp.id)
            out.append(cp)
    return tuple(out)


def by_id() -> dict[str, Checkpoint]:
    return {c.id: c for c in load_checkpoints()}


def by_collector(collector: str) -> list[Checkpoint]:
    return [c for c in load_checkpoints() if c.collector == collector]


def get(checkpoint_id: str) -> Checkpoint | None:
    return by_id().get(checkpoint_id)
