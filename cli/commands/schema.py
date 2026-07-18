from __future__ import annotations

import asyncio

import typer

from agents.schema_maintainer import agent as maintainer
from cli.render import console
from storage import repository

app = typer.Typer(help="Inspect and update the audit knowledge schemas (schema-maintainer agent).")


async def _snapshots(limit: int):
    runs = await repository.list_runs(limit=limit)
    out = []
    for r in runs:
        full = await repository.get_run(r.id)
        if full:
            out.extend(full.snapshots)
    # SnapshotRow → lightweight object with .data
    from core.models.snapshot import Snapshot

    return [Snapshot(collector=s.collector, target=s.target, ok=s.ok, data=s.data) for s in out]


@app.command()
def discover(limit: int = typer.Option(50, help="How many recent runs to scan.")) -> None:
    """Find GTM tag functions in past scans that the schema doesn't map yet."""
    snaps = asyncio.run(_snapshots(limit))
    unknowns = maintainer.discover_unknowns(snaps)
    if not unknowns:
        console.print("[green]No unknown GTM tag functions — schema is current.[/]")
        return
    from rich.table import Table

    t = Table(show_header=True, header_style="bold")
    t.add_column("Unknown function")
    t.add_column("Seen")
    for fn, n in sorted(unknowns.items(), key=lambda x: -x[1]):
        t.add_row(fn, str(n))
    console.print(t)
    console.print(
        "[dim]Run `adwize-audit schema learn` (needs OPENAI_API_KEY) to classify + persist.[/]"
    )


@app.command()
def learn(limit: int = typer.Option(50, help="How many recent runs to scan.")) -> None:
    """Discover → classify (LLM) → write updated schema to the override dir."""
    if not maintainer.has_key():
        console.print(
            "[yellow]Set OPENAI_API_KEY to let the schema-maintainer classify unknowns.[/]"
        )
        raise typer.Exit(code=1)
    snaps = asyncio.run(_snapshots(limit))
    result = asyncio.run(maintainer.learn(snaps))
    console.print(result.get("proposed") or "[dim]Nothing to classify.[/]")
    if result.get("written"):
        console.print(f"[green]Updated schema written to {result['written']}[/]")
