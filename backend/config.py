"""Local configuration helpers for FillForm."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: Path | None = None) -> None:
	"""Load KEY=VALUE pairs from a local .env file if present."""

	project_root = Path(__file__).resolve().parents[1]
	resolved_path = env_path or project_root / ".env"
	if not resolved_path.exists():
		return

	for line in resolved_path.read_text(encoding="utf-8").splitlines():
		candidate = line.strip()
		if not candidate or candidate.startswith("#") or "=" not in candidate:
			continue

		key, value = candidate.split("=", 1)
		os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file()
load_env_file(Path(__file__).with_name(".env"))


def get_gemini_api_key() -> str | None:
	return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def get_gemini_model() -> str:
	return os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
