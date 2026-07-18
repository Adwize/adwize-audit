import os
import tempfile
from pathlib import Path

# Point the local store at a throwaway dir BEFORE storage is imported/engine built.
_TMP = Path(tempfile.mkdtemp(prefix="adwize-audit-test-"))
os.environ["ADWIZE_DATA_DIR"] = str(_TMP)
os.environ["ADWIZE_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
