from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from cli.render import console, render_result
from report import executive_summary, write_report
from storage import repository

app = typer.Typer(help="Run and inspect measurement audits.")

_ANALYSIS_SKIP_MSG = {
    "no_key": "Analysis agent skipped — set OPENAI_API_KEY to enable it.",
    "no_tracking": "Analysis agent skipped — no Google tags detected to analyze.",
    "no_package": "Analysis agent skipped — install the LLM extra: uv sync --extra llm",
}


def _report_analysis(result) -> None:
    """Terminal view: the executive summary only (full brief goes to the .md
    report), plus a clear status when the analyst didn't run."""
    from rich.panel import Panel

    if result.summary:
        console.print(
            Panel(
                executive_summary(result.summary), title="Analysis — summary", border_style="cyan"
            )
        )
        return
    status = result.analysis_status
    if status == "error":
        console.print(f"[yellow]Analysis agent failed:[/] {result.analysis_detail}")
    elif status in _ANALYSIS_SKIP_MSG:
        console.print(f"[dim]{_ANALYSIS_SKIP_MSG[status]}[/]")
    elif status == "ran":  # ran but produced no text
        console.print("[dim]Analysis agent returned no content.[/]")


@app.command()
def scan(
    url: str = typer.Argument(..., help="Website URL to audit (no account access needed)."),
    timeout: float = typer.Option(20.0, help="Page render timeout (seconds)."),
    pages: int = typer.Option(5, "--pages", help="Max pages to crawl (homepage + discovered)."),
    page: list[str] = typer.Option(
        None, "--page", help="Explicit extra page URL to include (repeatable)."
    ),
    container: list[str] = typer.Option(
        None, "--container", help="Force-fetch a known GTM container id (repeatable)."
    ),
    consent: bool = typer.Option(
        True, help="Simulate accepting a consent banner (reveals gated tags)."
    ),
    analyze: bool = typer.Option(True, help="Run the LLM analysis agent (needs OPENAI_API_KEY)."),
    model: Optional[str] = typer.Option(
        None, help="OpenAI model for analysis (overrides default)."
    ),
    save: bool = typer.Option(True, help="Store the run locally (view later with `audit show`)."),
    report: Optional[Path] = typer.Option(
        None,
        "--report",
        help="Also write a full report here (off by default; .html or .md by extension).",
    ),
) -> None:
    """Public-source scan of a website's Google tag setup.

    Shows a concise result in the terminal. Pass --report <path> to also write a
    full report — format inferred from the extension (`.html`/`.htm` → static
    HTML, otherwise Markdown).
    """
    from agents.analyst import agent
    from core.checks.crawl_checks import run_crawl_checks
    from core.collectors import crawl
    from core.models.finding import Finding
    from core.models.result import AuditResult, Scores
    from core.scoring import score

    with console.status(f"[bold]Crawling {url}[/] (up to {pages} pages)...") as status:
        snapshot = asyncio.run(
            crawl.collect(
                url,
                timeout=timeout,
                extra_containers=container,
                accept_consent=consent,
                max_pages=pages,
                extra_pages=page,
            )
        )

        if not snapshot.ok:
            console.print(f"[red]Could not scan {url}:[/] {snapshot.error}")
            raise typer.Exit(code=1)

        status.update("[bold]Running checks...")
        findings: list[Finding] = run_crawl_checks(snapshot.data)
        scores: Scores = score(findings)

        result = AuditResult(
            target=snapshot.target,
            edition="oss",
            snapshots=[snapshot],
            findings=findings,
            scores=scores,
        )

        if analyze:
            status.update("[bold]Analyzing with LLM...")
            outcome = asyncio.run(agent.run(result, model=model))
            result.summary = outcome.summary
            result.analysis_status = outcome.status
            result.analysis_detail = outcome.detail or None

    # 1) concise terminal view
    render_result(result)
    n_pages = result.snapshots[0].data.get("pages_scanned", 1) if result.snapshots else 1
    if n_pages > 1:
        console.print(f"[dim]Crawled {n_pages} pages[/]")
    if analyze:
        _report_analysis(result)

    # 2) persist + full Markdown report
    run_id = asyncio.run(repository.save_result(result)) if save else None
    if save:
        console.print(f"[dim]Saved as run #{run_id}[/]")

    if report is not None:
        write_report(result, report, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
        console.print(f"[dim]Full report: {report}[/]")


@app.command("list")
def list_runs(
    target: Optional[str] = typer.Option(None, help="Filter by target URL."),
    limit: int = typer.Option(20, help="Max rows."),
) -> None:
    """List recent audit runs."""
    from rich.table import Table

    runs = asyncio.run(repository.list_runs(target=target, limit=limit))
    if not runs:
        console.print("[dim]No runs yet.[/]")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("#")
    table.add_column("Target")
    table.add_column("Grade")
    table.add_column("Score")
    table.add_column("When")
    for r in runs:
        table.add_row(
            str(r.id),
            r.target,
            r.grade,
            str(r.overall_score),
            r.created_at.strftime("%Y-%m-%d %H:%M"),
        )
    console.print(table)


@app.command()
def show(run_id: int = typer.Argument(..., help="Run id from `audit list`.")) -> None:
    """Show a stored run's findings."""
    run = asyncio.run(repository.get_run(run_id))
    if run is None:
        console.print(f"[red]No run #{run_id}[/]")
        raise typer.Exit(code=1)

    from core.models.enums import Severity, Source, Status
    from core.models.finding import Finding
    from core.models.result import AuditResult, Scores

    findings = [
        Finding(
            checkpoint_id=f.checkpoint_id,
            status=Status(f.status),
            severity=Severity(f.severity),
            category=f.category,
            source=Source(f.source),
            title=f.title,
            detail=f.detail,
            evidence=f.evidence or {},
            affected_items=f.affected_items or [],
            remediation_hint=f.remediation_hint or "",
        )
        for f in run.findings
    ]
    result = AuditResult(
        target=run.target,
        edition=run.edition,
        findings=findings,
        scores=Scores(**(run.scores or {"overall": run.overall_score, "grade": run.grade})),
        summary=run.summary,
        analysis_status=run.analysis_status,
        analysis_detail=run.analysis_detail,
    )
    render_result(result)
    if result.summary or result.analysis_status:
        _report_analysis(result)
