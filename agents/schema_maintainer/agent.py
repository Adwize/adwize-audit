"""Schema-maintainer agent: keeps the audit knowledge schemas current.

Skill split:
  - `discover_unknowns(snapshots)` — DETERMINISTIC. Finds GTM tag `function`
    codes seen in scans that the `gtm_functions` schema doesn't map yet.
  - `classify(unknowns)` — KEY-GATED LLM. Proposes {type, vendor, purpose} for
    unknown functions. Skipped (returns {}) without OPENAI_API_KEY.
  - `write_override(name, data)` — merges proposals into `$ADWIZE_SCHEMA_DIR/
    <name>.yaml` (the "memory" the loader prefers over the committed fallback).

So without any agent run, the committed schema is used; when the agent runs, its
learnings land in the override dir and take effect on the next scan.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from agents._base import with_memory
from agents.models import model_for
from agents.schema_maintainer.prompt import SYSTEM
from core.models.snapshot import Snapshot
from core.schemas import loader


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def discover_unknowns(snapshots: list[Snapshot]) -> dict[str, int]:
    """GTM tag functions present in scans but absent from the schema."""
    gf = loader.load("gtm_functions")
    known = set(gf.get("functions", {}))
    prefix = gf.get("custom_template_prefix", "__cvt_")
    counts: Counter[str] = Counter()
    for sn in snapshots:
        for cont in (sn.data or {}).get("containers", {}).values():
            for tag in cont.get("tags", []):
                fn = tag.get("function") or ""
                if fn and fn not in known and not fn.startswith(prefix):
                    counts[fn] += 1
    return dict(counts)


async def classify(unknown_functions: dict[str, int], model: str | None = None) -> dict[str, Any]:
    """LLM-classify unknown function codes → {functions: {code: {...}}}. Needs a key."""
    import importlib.util

    if not unknown_functions or not has_key() or importlib.util.find_spec("openai") is None:
        return {}

    from agents import llm

    try:
        text = await llm.complete(
            model or model_for("schema_maintainer"),
            [
                {"role": "system", "content": with_memory(SYSTEM, __file__)},
                {
                    "role": "user",
                    "content": "Unknown functions: " + ", ".join(sorted(unknown_functions)),
                },
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(text or "{}")
    except Exception:  # noqa: BLE001
        return {}


def override_dir() -> Path:
    d = os.getenv(loader.OVERRIDE_ENV) or (Path.home() / ".adwize" / "schemas")
    return Path(d)


def write_override(name: str, additions: dict[str, Any]) -> Path:
    """Merge `additions` into $ADWIZE_SCHEMA_DIR/<name>.yaml, seeding from the
    current (committed or override) schema so nothing is lost."""
    out_dir = override_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = dict(loader.load(name))
    base_functions = dict(base.get("functions", {}))
    base_functions.update(additions.get("functions", {}))
    base["functions"] = base_functions
    path = out_dir / f"{name}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(base, f, sort_keys=False, allow_unicode=True)
    loader.clear_cache()
    return path


async def learn(snapshots: list[Snapshot], model: str | None = None) -> dict[str, Any]:
    """Full pass: discover → classify → write. Returns a summary of what changed."""
    unknowns = discover_unknowns(snapshots)
    proposals = await classify(unknowns, model=model)
    written = None
    if proposals.get("functions"):
        written = str(write_override("gtm_functions", proposals))
    return {"unknown_functions": unknowns, "proposed": proposals, "written": written}
