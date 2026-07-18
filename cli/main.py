import typer

# Load .env (if present) so OPENAI_API_KEY / ADWIZE_* are available to the CLI.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional; env vars still work without it
    pass

from cli.commands import audit, schema  # noqa: E402

app = typer.Typer(
    name="adwize-audit",
    help="Adwize Audit — open-source GA4/GTM measurement audits (no account access needed).",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

app.add_typer(audit.app, name="audit", help="Run and inspect measurement audits")
app.add_typer(schema.app, name="schema", help="Inspect/update audit knowledge schemas")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
