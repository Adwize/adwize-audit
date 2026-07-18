"""Analyst agent (OSS edition): turns deterministic findings into an analyst
brief + prioritized recommendations using an LLM.

Key-gated by design, but never *silently* skipped — `run()` returns an
`AnalysisOutcome` whose `status` says exactly what happened (ran / no key / no
tracking / package missing / errored), so the CLI can always tell the user
whether the analyst ran and why. Provider is OpenAI; the model is configurable
(ADWIZE_OPENAI_MODEL). The system prompt is `prompt.SYSTEM` + this agent's
committed MEMORY.md heuristics.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from agents._base import with_memory
from agents.analyst.prompt import SYSTEM
from agents.models import model_for
from core.models.enums import Status
from core.models.result import AuditResult
from core.registry import loader as registry


@dataclass
class AnalysisOutcome:
    status: str  # ran | no_key | no_tracking | no_package | error
    summary: str | None = None
    detail: str = ""


def has_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def _has_tracking(result: AuditResult) -> bool:
    for sn in result.snapshots:
        ids = sn.data.get("tag_ids", {}) if sn.data else {}
        if any(ids.get(k) for k in ("ga4", "ads", "ua", "gtm")):
            return True
    return False


def _uncovered_checks(result: AuditResult) -> list:
    """Registry checkpoints this scan did NOT evaluate — the candidate pool for
    the 'what to check next' section (they need account access or manual review)."""
    done = {f.checkpoint_id for f in result.findings}
    return [c for c in registry.load_checkpoints() if c.id not in done]


def _prompt(result: AuditResult) -> str:
    lines = [
        f"Target: {result.target}",
        f"Grade: {result.scores.grade} ({result.scores.overall}/100)",
        "",
        "== Findings ==",
    ]
    for f in result.findings:
        if f.status not in (Status.FAIL, Status.WARN):
            continue
        lines.append(f"- [{f.status.value}/{f.severity.value}] {f.title}: {f.detail}")
        if f.affected_items:
            lines.append(f"    affected: {json.dumps(f.affected_items)[:600]}")
        if f.evidence:
            lines.append(f"    evidence: {json.dumps(f.evidence)[:600]}")
    lines.append(
        "Passing: " + ", ".join(f.checkpoint_id for f in result.findings if f.status == Status.PASS)
    )

    sig = result.snapshots[0].data if result.snapshots else {}
    cs = sig.get("container_summary", {})
    events = cs.get("events", [])
    vendors = ", ".join(f"{v['name']} ({v['category']})" for v in sig.get("vendors", []))
    consent = sig.get("consent", {})
    lines += [
        "",
        "== Signals observed ==",
        f"GA4 events configured ({len(events)}): {', '.join(events[:40])}"
        + ("…" if len(events) > 40 else ""),
        f"measurement_ids: {cs.get('measurement_ids')}",
        f"vendors: {vendors}",
        f"ecommerce={cs.get('ecommerce')}, enhanced_conversions={cs.get('enhanced_conversions')}, "
        f"user_properties={cs.get('user_properties')}, custom_html_tags={cs.get('custom_html_count')}",
        f"consent: accepted={consent.get('accepted')} cmps={consent.get('cmps')}",
        f"cookies: {sig.get('cookies')}",
    ]

    lines += ["", "== Checks NOT covered by this public scan (candidate next steps) =="]
    by_tool: dict[str, list[str]] = {}
    for c in _uncovered_checks(result):
        by_tool.setdefault(c.tool, []).append(
            f"  - {c.id} [{c.source.value}]: {c.how_to_check[:110]}"
        )
    for tool, items in sorted(by_tool.items()):
        lines.append(f"[{tool}]")
        lines.extend(items)
    return "\n".join(lines)


async def run(result: AuditResult, model: str | None = None) -> AnalysisOutcome:
    """Run the analyst, returning an outcome that always explains what happened."""
    if not has_key():
        return AnalysisOutcome("no_key")
    if not _has_tracking(result):
        return AnalysisOutcome("no_tracking")
    import importlib.util

    if importlib.util.find_spec("openai") is None:
        return AnalysisOutcome("no_package", detail="openai package not installed")

    from agents import llm

    try:
        text = await llm.complete(
            model or model_for("analyst"),
            [
                {"role": "system", "content": with_memory(SYSTEM, __file__)},
                {"role": "user", "content": _prompt(result)},
            ],
            temperature=0.2,
        )
        return AnalysisOutcome("ran", summary=text.strip() or None)
    except Exception as exc:  # noqa: BLE001 — must never break the scan, but surface why
        return AnalysisOutcome("error", detail=f"{type(exc).__name__}: {exc}")


async def analyze(result: AuditResult, model: str | None = None) -> str | None:
    """Convenience wrapper: the brief text, or None if it didn't run."""
    return (await run(result, model=model)).summary
