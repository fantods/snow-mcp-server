import os
import re
from pathlib import Path

MAX_CONTENT_SIZE = 8192
DEFAULT_PAGE_SIZE = 50
ENTRY_TYPES = frozenset({"preference", "instruction", "snippet", "context"})
CONTEXT_KEY_PATTERN = re.compile(r"^(global|project:[a-zA-Z0-9_-]+)$")


def get_db_path() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        base = Path(xdg_data)
    else:
        base = Path.home() / ".local" / "share"
    db_dir = base / "snow"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "snow.db"
