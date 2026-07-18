from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from core.models.enums import Status
from core.models.result import AuditResult

console = Console()

_STATUS_STYLE = {"pass": "green", "fail": "red", "warn": "yellow", "na": "dim"}
_STATUS_MARK = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "na": " NA "}
_GRADE_STYLE = {"A": "bold green", "B": "green", "C": "yellow", "D": "red", "E": "bold red"}


def render_result(result: AuditResult) -> None:
    g = result.scores.grade
    header = f"[{_GRADE_STYLE.get(g, 'bold')}]Grade {g}[/]  ·  {result.scores.overall}/100  ·  {result.target}"
    console.print(Panel(header, title="Measurement Audit", expand=False))

    order = {Status.FAIL: 0, Status.WARN: 1, Status.PASS: 2, Status.NA: 3}
    findings = sorted(
        result.findings, key=lambda f: (order[f.status], -f.severity.weight, f.checkpoint_id)
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("", width=4)
    table.add_column("Checkpoint")
    table.add_column("Severity")
    table.add_column("Title")
    for f in findings:
        style = _STATUS_STYLE[f.status.value]
        table.add_row(
            f"[{style}]{_STATUS_MARK[f.status.value]}[/]",
            f.checkpoint_id,
            f.severity.value,
            f.title,
        )
    console.print(table)

    counts = result.scores.counts
    status_order = ["fail", "warn", "pass", "na"]
    summary = "  ".join(
        f"[{_STATUS_STYLE.get(k, 'white')}]{k}={counts[k]}[/]" for k in status_order if k in counts
    )
    console.print(summary)

    if result.scores.penalties:
        penalties = sorted(result.scores.penalties, key=lambda p: -p.points)
        penalty_lines = ", ".join(
            f"{p.checkpoint_id.removeprefix('crawl.')} (-{p.points})" for p in penalties[:5]
        )
        total = sum(p.points for p in result.scores.penalties)
        console.print(f"[dim]Score: 100 − {total} = {result.scores.overall}  [{penalty_lines}][/]")
