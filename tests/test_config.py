from __future__ import annotations

import os
from unittest.mock import patch

from backend.config import (
    load_env_file,
    get_groq_api_key,
    get_groq_model,
    get_cors_origins,
    get_debug_mode,
    get_secret_key,
    get_google_calendar_redirect_uri,
    get_google_auth_redirect_uri,
)


def test_get_groq_api_key_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_groq_api_key() is None


def test_get_groq_api_key_set():
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
        assert get_groq_api_key() == "test-key"


def test_get_groq_model_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_groq_model() == "llama-3.3-70b-versatile"


def test_get_groq_model_set():
    with patch.dict(os.environ, {"GROQ_MODEL": "mixtral-8x7b-32768"}, clear=True):
        assert get_groq_model() == "mixtral-8x7b-32768"


def test_get_cors_origins_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_cors_origins() == ["*"]


def test_get_cors_origins_set():
    with patch.dict(os.environ, {"CORS_ORIGINS": "http://localhost:3000,https://example.com"}, clear=True):
        assert get_cors_origins() == ["http://localhost:3000", "https://example.com"]


def test_get_debug_mode_false():
    with patch.dict(os.environ, {}, clear=True):
        assert get_debug_mode() is False


def test_get_debug_mode_true():
    with patch.dict(os.environ, {"FLASK_DEBUG": "1"}, clear=True):
        assert get_debug_mode() is True


def test_get_secret_key_debug_generates():
    with patch.dict(os.environ, {"FLASK_DEBUG": "1"}, clear=True):
        key = get_secret_key()
        assert len(key) == 64
        assert isinstance(key, str)


def test_get_secret_key_production_raises():
    with patch.dict(os.environ, {}, clear=True):
        try:
            get_secret_key()
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass


def test_get_secret_key_from_env():
    with patch.dict(os.environ, {"SECRET_KEY": "my-secret"}, clear=True):
        assert get_secret_key() == "my-secret"


def test_get_google_calendar_redirect_uri_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_calendar_redirect_uri() == "http://localhost:5000/api/calendar/callback"


def test_get_google_calendar_redirect_uri_set():
    with patch.dict(os.environ, {"GOOGLE_CALENDAR_REDIRECT_URI": "https://example.com/callback"}, clear=True):
        assert get_google_calendar_redirect_uri() == "https://example.com/callback"


def test_get_google_auth_redirect_uri_default():
    with patch.dict(os.environ, {}, clear=True):
        assert get_google_auth_redirect_uri() is None


def test_get_google_auth_redirect_uri_set():
    with patch.dict(os.environ, {"GOOGLE_AUTH_REDIRECT_URI": "https://example.com/auth"}, clear=True):
        assert get_google_auth_redirect_uri() == "https://example.com/auth"


def test_load_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_VAR=hello\n# comment\n\nOTHER_VAR=world\n")
    load_env_file(env_file)
    assert os.environ.get("TEST_VAR") == "hello"
    assert os.environ.get("OTHER_VAR") == "world"


def test_load_env_file_strips_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('QUOTED_VAR="value with spaces"\n')
    load_env_file(env_file)
    assert os.environ.get("QUOTED_VAR") == "value with spaces"
