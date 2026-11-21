import os
from pathlib import Path
from secrets import token_hex


class Config:
    MAX_CONTENT_LENGTH = None
    JSON_SORT_KEYS = False
    SECRET_KEY = os.getenv("VERITONE_SECRET_KEY") or token_hex(32)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("VERITONE_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    DB_DIR = Path(os.getenv("VERITONE_DB_DIR", str(Path(__file__).resolve().parent.parent / "data")))
    DB_PATH = DB_DIR / "veritone.db"