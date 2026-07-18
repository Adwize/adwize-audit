"""Deterministic health scoring from findings. Mirrors the adwize-main pattern
(scored report) but computed purely from statuses + severities."""

from __future__ import annotations

from collections import Counter, defaultdict

from core.models.enums import Severity, Status
from core.models.finding import Finding
from core.models.result import ScorePenalty, Scores

# penalty applied to the 100-point score when a checkpoint FAILs, by severity.
FAIL_PENALTY = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 12,
    Severity.MEDIUM: 5,
    Severity.LOW: 2,
    Severity.INFO: 0,
}


def _penalty(f: Finding) -> int:
    base = FAIL_PENALTY[f.severity]
    if f.status == Status.FAIL:
        return base
    if f.status == Status.WARN:
        return base // 2
    return 0  # PASS / NA


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def score(findings: list[Finding]) -> Scores:
    penalties: list[ScorePenalty] = []
    for f in findings:
        p = _penalty(f)
        if p > 0:
            penalties.append(
                ScorePenalty(
                    checkpoint_id=f.checkpoint_id,
                    severity=f.severity.value,
                    status=f.status.value,
                    points=p,
                )
            )

    overall = max(0, 100 - sum(p.points for p in penalties))

    cat_penalty: dict[str, int] = defaultdict(int)
    for f in findings:
        cat_penalty[f.category] += _penalty(f)
    by_category = {c: max(0, 100 - p) for c, p in cat_penalty.items()}

    counts = Counter(f.status.value for f in findings)
    return Scores(
        overall=overall,
        grade=_grade(overall),
        by_category=by_category,
        counts=dict(counts),
        penalties=penalties,
    )
