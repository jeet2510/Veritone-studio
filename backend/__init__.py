from flask import Flask
from pathlib import Path

from .config import Config
from .database import init_db
from .routes import api_bp, page_bp


def create_app() -> Flask:
    base_dir = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        static_folder=str(base_dir / "frontend"),
        static_url_path="/static",
        template_folder=str(base_dir / "frontend"),
    )
    app.config.from_object(Config)

    init_db()

    app.register_blueprint(page_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app