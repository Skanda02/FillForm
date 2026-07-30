"""Flask application entry point for FillForm."""

from __future__ import annotations

from pathlib import Path

from flask import Flask
from flask_cors import CORS

from backend.config import get_cors_origins, get_debug_mode, get_secret_key
from backend.limiter import limiter
from backend.routes.api import api_bp
from database.models import initialize_database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="",
    )
    app.secret_key = get_secret_key()
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = not get_debug_mode()
    app.config["SESSION_COOKIE_HTTPONLY"] = True

    CORS(app, resources={r"/api/*": {"origins": get_cors_origins()}})
    limiter.init_app(app)
    app.register_blueprint(api_bp)
    initialize_database()

    @app.get("/")
    def home() -> object:
        return app.send_static_file("index.html")

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=get_debug_mode())
