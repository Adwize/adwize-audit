from pathlib import Path

from core.models.result import AuditResult
from report.html import render_html
from report.markdown import executive_summary, render_markdown

__all__ = ["executive_summary", "render_html", "render_markdown", "render_report", "write_report"]


def render_report(result: AuditResult, path: Path, generated_at: str = "") -> str:
    """Render to Markdown or HTML inferred from the file extension."""
    if path.suffix.lower() in (".html", ".htm"):
        return render_html(result, generated_at=generated_at)
    return render_markdown(result, generated_at=generated_at)


def write_report(result: AuditResult, path: Path, generated_at: str = "") -> Path:
    """Render (format inferred from extension) and write, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(result, path, generated_at=generated_at), encoding="utf-8")
    return path
