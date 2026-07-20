"""Flask application entry point for FillForm."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask
from flask_cors import CORS

from backend.routes.api import api_bp
from database.models import initialize_database

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_app() -> Flask:
	app = Flask(
		__name__,
		static_folder=str(FRONTEND_DIR),
		static_url_path="",
	)
	CORS(app, resources={r"/api/*": {"origins": "*"}})
	app.register_blueprint(api_bp)
	initialize_database()

	@app.get("/")
	def home() -> object:
		return app.send_static_file("index.html")

	return app

app = create_app()


if __name__ == "__main__":
		app.run(debug=True)
