import os
from pathlib import Path


class Config:
    # Unlimited upload size; large streams are written to temporary files on disk
    MAX_CONTENT_LENGTH = None
    JSON_SORT_KEYS = False

    _default_db_dir = Path("/app/data") if Path("/app").exists() else Path("data")
    DB_DIR = Path(os.getenv("VERITONE_DB_DIR", str(_default_db_dir)))
    DB_PATH = DB_DIR / "veritone.db"