from core.models.enums import Severity, Source, Status
from core.models.finding import Finding
from core.scoring import score


def _f(status, severity):
    return Finding(
        checkpoint_id="x.y",
        status=status,
        severity=severity,
        category="Data Quality",
        source=Source.CRAWL,
        title="t",
    )


def test_all_pass_is_100_grade_a():
    s = score([_f(Status.PASS, Severity.CRITICAL), _f(Status.PASS, Severity.HIGH)])
    assert s.overall == 100
    assert s.grade == "A"


def test_critical_fail_penalizes():
    s = score([_f(Status.FAIL, Severity.CRITICAL)])
    assert s.overall == 75  # 100 - 25
    assert s.grade == "B"


def test_warn_is_half_penalty():
    s = score([_f(Status.WARN, Severity.HIGH)])  # high fail = 12, warn = 6
    assert s.overall == 94


def test_na_does_not_penalize():
    s = score([_f(Status.NA, Severity.CRITICAL)])
    assert s.overall == 100
