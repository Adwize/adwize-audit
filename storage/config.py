from __future__ import annotations

import os
from pathlib import Path

DATA_DIR = Path(os.getenv("ADWIZE_DATA_DIR", Path.home() / ".adwize"))


def database_url() -> str:
    """SQLite in ~/.adwize by default; override with ADWIZE_DATABASE_URL
    (e.g. a postgresql+asyncpg:// URL for the shared analyst store)."""
    url = os.getenv("ADWIZE_DATABASE_URL")
    if url:
        return url
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{DATA_DIR / 'audit.db'}"
