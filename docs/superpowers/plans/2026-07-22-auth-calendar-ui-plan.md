# FillForm Auth + Calendar + UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google OAuth login with persistent profiles, Google Calendar "Add to Calendar" button, and a cleaner UI — all in a single-page Flask-served HTML app.

**Architecture:** Backend adds `auth_service.py` for Google OAuth login/session management, new auth routes in `api.py`, and configures Flask sessions. Frontend (`index.html`) gets a login screen, profile form, reorganized result layout, calendar button, and nav bar. The existing `calendar_service.py` and `profile_service.py` are reused as-is.

**Tech Stack:** Flask, flask-cors, pymongo, google-auth-oauthlib, Google OAuth2, vanilla HTML/CSS/JS (single file)

## Global Constraints

- Python 3.11+, Flask 3.0+, pymongo 4.6+
- Google OAuth2 via `google-auth-oauthlib` (already in requirements.txt)
- MongoDB collections: `users` (new), `profiles` (existing), `calendar_tokens` (existing), `submissions` (existing)
- Frontend is a single `frontend/index.html` file — no build tools, no frameworks
- Session via `flask.session` (signed cookie, requires `SECRET_KEY`)
- All API routes prefixed with `/api/`
- CORS enabled for all `/api/*` routes

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/.env` | Modify | Add `SECRET_KEY`, `GOOGLE_LOGIN_CLIENT_ID`, `GOOGLE_LOGIN_CLIENT_SECRET` |
| `backend/config.py` | Modify | Add helper functions for new env vars |
| `backend/services/auth_service.py` | **Create** | Google OAuth login, user CRUD, session helpers |
| `backend/app.py` | Modify | Add `SECRET_KEY`, session config |
| `backend/routes/api.py` | Modify | Add auth routes (login, callback, me, logout) |
| `frontend/index.html` | Modify | Login screen, profile form, nav bar, calendar button, UI cleanup |

---

### Task 1: Environment & Config Setup

**Files:**
- Modify: `backend/.env`
- Modify: `backend/config.py`

**Interfaces:**
- Produces: `get_secret_key()`, `get_google_login_client_id()`, `get_google_login_client_secret()` in config.py

- [ ] **Step 1: Add new env vars to `backend/.env`**

Append to `backend/.env`:

```env
# Flask session signing key (generate a random string)
SECRET_KEY=fillform-dev-secret-change-in-production

# Google OAuth for login (create at https://console.cloud.google.com/apis/credentials)
GOOGLE_LOGIN_CLIENT_ID=
GOOGLE_LOGIN_CLIENT_SECRET=
```

- [ ] **Step 2: Add config helpers to `backend/config.py`**

Add these functions at the end of `backend/config.py`:

```python
def get_secret_key() -> str:
	return os.environ.get("SECRET_KEY", "fillform-dev-secret-change-in-production")


def get_google_login_client_id() -> str | None:
	return os.environ.get("GOOGLE_LOGIN_CLIENT_ID")


def get_google_login_client_secret() -> str | None:
	return os.environ.get("GOOGLE_LOGIN_CLIENT_SECRET")
```

- [ ] **Step 3: Verify config loads**

Run: ` python -c "from backend.config import get_secret_key, get_google_login_client_id; print('SECRET_KEY:', bool(get_secret_key())); print('LOGIN_CLIENT_ID:', get_google_login_client_id())"`

Expected: `SECRET_KEY: True` and `LOGIN_CLIENT_ID: None` (not set yet)

- [ ] **Step 4: Commit**

```bash
git add backend/.env backend/config.py
git commit -m "chore: add env vars and config helpers for auth"
```

---

### Task 2: Auth Service

**Files:**
- Create: `backend/services/auth_service.py`

**Interfaces:**
- Consumes: `get_google_login_client_id()`, `get_google_login_client_secret()` from `backend/config.py`
- Consumes: `get_collection()` from `backend.database`
- Produces: `get_login_url(state)`, `handle_login_callback(code)`, `get_current_user(user_id)`, `create_profile_for_user(user_id, profile_data)`, `get_user_id_from_session(session)`, `logout_user(session)`

- [ ] **Step 1: Create `backend/services/auth_service.py`**

```python
"""Google OAuth login and session management for FillForm."""

from __future__ import annotations

from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from backend.config import get_google_login_client_id, get_google_login_client_secret
from backend.database import get_collection

LOGIN_SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"]
LOGIN_REDIRECT_URI = "http://127.0.0.1:5000/api/auth/callback"


def _get_client_config() -> dict:
    return {
        "web": {
            "client_id": get_google_login_client_id() or "",
            "client_secret": get_google_login_client_secret() or "",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [LOGIN_REDIRECT_URI],
        }
    }


def get_login_url(state: str) -> str:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=LOGIN_SCOPES,
        redirect_uri=LOGIN_REDIRECT_URI,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url


def handle_login_callback(code: str) -> dict | None:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=LOGIN_SCOPES,
        redirect_uri=LOGIN_REDIRECT_URI,
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    import requests as http_requests
    resp = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
    )
    if resp.status_code != 200:
        return None
    google_user = resp.json()

    col = get_collection("users")
    now = datetime.now(timezone.utc).isoformat()
    existing = col.find_one({"google_id": google_user["id"]})

    if existing:
        col.update_one(
            {"google_id": google_user["id"]},
            {"$set": {"updated_at": now}},
        )
        return _serialize(existing)

    user_doc = {
        "google_id": google_user["id"],
        "email": google_user.get("email", ""),
        "name": google_user.get("name", ""),
        "picture": google_user.get("picture", ""),
        "profile_id": None,
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(user_doc)
    user_doc["id"] = str(result.inserted_id)
    del user_doc["_id"]
    return user_doc


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


def get_current_user(user_id: str) -> dict | None:
    from bson import ObjectId
    col = get_collection("users")
    doc = col.find_one({"_id": ObjectId(user_id)})
    if not doc:
        return None
    user = _serialize(doc)

    if user.get("profile_id"):
        from backend.services.profile_service import get_profile
        user["profile"] = get_profile(user["profile_id"])
    else:
        user["profile"] = None

    return user


def create_profile_for_user(user_id: str, profile_data: dict) -> dict | None:
    from bson import ObjectId
    from backend.services.profile_service import create_or_update_profile

    profile = create_or_update_profile(profile_data)
    if not profile:
        return None

    col = get_collection("users")
    col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"profile_id": profile["id"], "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return profile


def logout_user(session: dict) -> None:
    session.clear()
```

- [ ] **Step 2: Verify import works**

Run: `cd /Users/skandaprasadk/Documents/projects/FillForm && python -c "from backend.services.auth_service import get_login_url, handle_login_callback, get_current_user; print('auth_service OK')"`

Expected: `auth_service OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/auth_service.py
git commit -m "feat: add auth_service with Google OAuth login and user management"
```

---

### Task 3: Auth Routes & Flask Session Config

**Files:**
- Modify: `backend/app.py`
- Modify: `backend/routes/api.py`

**Interfaces:**
- Consumes: `get_login_url()`, `handle_login_callback()`, `get_current_user()`, `logout_user()` from `backend.services.auth_service`
- Consumes: `get_secret_key()` from `backend.config`
- Produces: `GET /api/auth/login`, `GET /api/auth/callback`, `GET /api/auth/me`, `POST /api/auth/logout`

- [ ] **Step 1: Configure Flask session in `backend/app.py`**

Replace the contents of `backend/app.py`:

```python
"""Flask application entry point for FillForm."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask
from flask_cors import CORS

from backend.config import get_secret_key
from backend.routes.api import api_bp
from database.models import initialize_database

FRONTEND_DIR = PROJECT_ROOT / "frontend"


def create_app() -> Flask:
    app = Flask(
        __name__,
        static_folder=str(FRONTEND_DIR),
        static_url_path="",
    )
    app.secret_key = get_secret_key()
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_HTTPONLY"] = True

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
```

- [ ] **Step 2: Add auth routes to `backend/routes/api.py`**

Add these imports at the top of `backend/routes/api.py` (after the existing calendar import on line 30):

```python
import secrets
from flask import session
from backend.services.auth_service import (
    get_login_url,
    handle_login_callback,
    get_current_user,
    create_profile_for_user,
    logout_user,
)
```

Then add these routes at the end of `backend/routes/api.py`:

```python
@api_bp.get("/api/auth/login")
def api_auth_login() -> tuple[object, int]:
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    auth_url = get_login_url(state)
    return jsonify({"auth_url": auth_url}), 200


@api_bp.get("/api/auth/callback")
def api_auth_callback() -> tuple[object, int]:
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400

    user = handle_login_callback(code)
    if not user:
        return jsonify({"error": "Failed to authenticate with Google"}), 401

    session["user_id"] = user["id"]
    return redirect("http://127.0.0.1:5000")


@api_bp.get("/api/auth/me")
def api_auth_me() -> tuple[object, int]:
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    user = get_current_user(user_id)
    if not user:
        session.clear()
        return jsonify({"error": "User not found"}), 401

    return jsonify(user), 200


@api_bp.post("/api/auth/logout")
def api_auth_logout() -> tuple[object, int]:
    logout_user(session)
    return jsonify({"success": True}), 200


@api_bp.post("/api/auth/profile")
def api_auth_create_profile() -> tuple[object, int]:
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    profile = create_profile_for_user(user_id, data)
    if not profile:
        return jsonify({"error": "Failed to create profile"}), 500

    return jsonify(profile), 201
```

- [ ] **Step 3: Remove duplicate `import secrets` and `from flask import redirect`**

Check that the top of `api.py` doesn't have duplicate imports. The existing file already imports `secrets` (line 28) and `redirect` (line 29). Remove the new duplicates from Step 2 and keep only the originals. The final import block should have:

```python
import secrets
from flask import Blueprint, jsonify, redirect, request, session
```

And the single auth import block:

```python
from backend.services.auth_service import (
    get_login_url,
    handle_login_callback,
    get_current_user,
    create_profile_for_user,
    logout_user,
)
```

- [ ] **Step 4: Verify server starts**

Run: `cd /Users/skandaprasadk/Documents/projects/FillForm && python -c "from backend.app import create_app; app = create_app(); print('App created OK')"`

Expected: `App created OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app.py backend/routes/api.py
git commit -m "feat: add auth routes and Flask session config"
```

---

### Task 4: Frontend — Login Screen & Profile Form

**Files:**
- Modify: `frontend/index.html`

**Interfaces:**
- Consumes: `GET /api/auth/login`, `GET /api/auth/me`, `POST /api/auth/profile`, `POST /api/auth/logout`
- Produces: Login UI, profile creation form, session-aware app loading

- [ ] **Step 1: Replace the entire `frontend/index.html`**

Replace the full contents of `frontend/index.html` with the following. This includes the login screen, profile form, nav bar, reorganized layout, and all CSS/JS:

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>FillForm</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f0f2f5; color: #1a1a2e; min-height: 100vh; }

    /* Nav */
    .nav { display: flex; align-items: center; justify-content: space-between; padding: 16px 32px; background: #fff; border-bottom: 1px solid #e5e7eb; position: sticky; top: 0; z-index: 100; }
    .nav-brand { font-size: 20px; font-weight: 800; color: #1a1a2e; letter-spacing: -0.5px; }
    .nav-user { display: flex; align-items: center; gap: 12px; }
    .nav-user img { width: 32px; height: 32px; border-radius: 50%; }
    .nav-user span { font-size: 14px; font-weight: 600; }
    .nav-logout { padding: 6px 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; font-size: 13px; font-weight: 600; cursor: pointer; color: #6b7280; }
    .nav-logout:hover { background: #f9fafb; border-color: #d1d5db; }

    /* Container */
    .container { max-width: 900px; margin: 0 auto; padding: 32px 20px 64px; }

    /* Auth screens */
    .auth-screen { display: flex; align-items: center; justify-content: center; min-height: calc(100vh - 65px); }
    .auth-card { background: #fff; border-radius: 16px; padding: 48px 40px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); text-align: center; max-width: 420px; width: 100%; }
    .auth-card h1 { font-size: 28px; font-weight: 800; margin-bottom: 8px; }
    .auth-card p { color: #6b7280; font-size: 14px; margin-bottom: 32px; line-height: 1.5; }
    .google-btn { display: inline-flex; align-items: center; gap: 12px; padding: 12px 28px; border: 1px solid #d1d5db; border-radius: 10px; background: #fff; font-size: 15px; font-weight: 600; cursor: pointer; color: #374151; transition: box-shadow 0.15s; }
    .google-btn:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .google-btn svg { width: 20px; height: 20px; }

    /* Profile form */
    .profile-card { background: #fff; border-radius: 16px; padding: 40px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); max-width: 520px; width: 100%; }
    .profile-card h2 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
    .profile-card .subtitle { color: #6b7280; font-size: 14px; margin-bottom: 28px; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .form-group { display: flex; flex-direction: column; gap: 6px; }
    .form-group.full { grid-column: 1 / -1; }
    .form-group label { font-size: 13px; font-weight: 600; color: #374151; }
    .form-group input { padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 14px; outline: none; transition: border-color 0.15s; }
    .form-group input:focus { border-color: #6366f1; }
    .form-submit { margin-top: 24px; width: 100%; padding: 12px; border: none; border-radius: 10px; background: #6366f1; color: #fff; font-size: 15px; font-weight: 700; cursor: pointer; }
    .form-submit:hover { background: #4f46e5; }

    /* Hero */
    .hero { margin-bottom: 28px; }
    .hero h1 { font-size: 26px; font-weight: 800; margin-bottom: 6px; }
    .hero p { color: #6b7280; font-size: 14px; }

    /* Input section */
    .input-section { background: #fff; border-radius: 16px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 24px; }
    .input-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .input-grid label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }
    .input-grid textarea { width: 100%; min-height: 180px; padding: 14px; border: 1px solid #d1d5db; border-radius: 10px; font: inherit; font-size: 14px; resize: vertical; outline: none; }
    .input-grid textarea:focus { border-color: #6366f1; }
    .input-grid input[type="file"] { font-size: 14px; }
    .analyze-btn { margin-top: 16px; padding: 12px 24px; border: none; border-radius: 10px; background: #1a1a2e; color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; width: 100%; }
    .analyze-btn:hover { background: #16213e; }
    .analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .loading-overlay { display: none; position: relative; }
    .loading-overlay.active { display: block; }
    .spinner { width: 20px; height: 20px; border: 3px solid #e5e7eb; border-top-color: #6366f1; border-radius: 50%; animation: spin 0.6s linear infinite; display: inline-block; vertical-align: middle; margin-right: 8px; }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Result cards */
    .results { display: none; }
    .results.visible { display: block; }
    .section-title { font-size: 16px; font-weight: 700; margin-bottom: 14px; color: #1a1a2e; }
    .card { background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); margin-bottom: 20px; transition: box-shadow 0.15s; }
    .card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    .card-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
    .card-field-label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: #9ca3af; font-weight: 600; margin-bottom: 6px; }
    .card-field-value { font-size: 15px; font-weight: 600; color: #1a1a2e; word-break: break-word; }

    /* Deadline card */
    .deadline-card { border-left: 4px solid #d1d5db; }
    .deadline-card.active { border-left-color: #22c55e; }
    .deadline-card.today { border-left-color: #f59e0b; }
    .deadline-card.expired { border-left-color: #ef4444; }
    .status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .status-pill.active { background: #dcfce7; color: #166534; }
    .status-pill.today { background: #fef3c7; color: #92400e; }
    .status-pill.expired { background: #fee2e2; color: #991b1b; }
    .timer-bar { width: 100%; height: 8px; border-radius: 999px; background: #e5e7eb; overflow: hidden; margin-top: 12px; }
    .timer-fill { height: 100%; width: 0%; background: linear-gradient(90deg, #f59e0b, #ef4444); transition: width 0.4s ease; }
    .timer-text { margin-top: 6px; font-size: 13px; font-weight: 600; color: #6b7280; }
    .deadline-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; align-items: center; }

    /* Buttons */
    .btn-calendar { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 10px; background: #fff; border: 1px solid #d1d5db; font-size: 13px; font-weight: 700; cursor: pointer; color: #374151; transition: all 0.15s; }
    .btn-calendar:hover { background: #f9fafb; border-color: #a5b4fc; color: #4f46e5; }
    .btn-calendar.connected { border-color: #818cf8; color: #4f46e5; }
    .btn-calendar.added { background: #dcfce7; border-color: #86efac; color: #166534; cursor: default; }
    .btn-connect-cal { display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 10px; background: #f0f0ff; border: 1px solid #c7d2fe; font-size: 13px; font-weight: 700; cursor: pointer; color: #4338ca; }
    .btn-connect-cal:hover { background: #e0e7ff; }
    .btn-apply { display: inline-flex; align-items: center; justify-content: center; padding: 10px 18px; border-radius: 10px; background: #1a1a2e; color: #fff; text-decoration: none; font-size: 13px; font-weight: 700; transition: background 0.15s; }
    .btn-apply:hover { background: #16213e; }

    /* Summary */
    .summary-section { padding: 14px; border-radius: 10px; background: #f9fafb; border: 1px solid #e5e7eb; margin-bottom: 12px; }
    .summary-section h4 { font-size: 13px; font-weight: 700; color: #374151; margin-bottom: 8px; }
    .summary-section p, .summary-section li { font-size: 14px; color: #4b5563; line-height: 1.6; }
    .summary-list { padding-left: 18px; }

    /* Toast */
    .toast-container { position: fixed; bottom: 24px; right: 24px; z-index: 1000; display: flex; flex-direction: column; gap: 8px; }
    .toast { padding: 14px 20px; border-radius: 10px; font-size: 14px; font-weight: 600; color: #fff; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideIn 0.3s ease, fadeOut 0.3s ease 2.7s forwards; }
    .toast.success { background: #16a34a; }
    .toast.error { background: #dc2626; }
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes fadeOut { to { opacity: 0; transform: translateY(10px); } }

    /* Error */
    .error-box { display: none; padding: 12px 16px; border-radius: 10px; background: #fef2f2; color: #991b1b; font-size: 14px; margin-top: 16px; }

    /* Mobile */
    @media (max-width: 640px) {
      .nav { padding: 12px 16px; }
      .container { padding: 20px 16px 48px; }
      .input-grid { grid-template-columns: 1fr; }
      .card-grid { grid-template-columns: 1fr; }
      .form-grid { grid-template-columns: 1fr; }
      .auth-card { padding: 32px 24px; }
      .profile-card { padding: 28px 20px; }
    }
  </style>
</head>
<body>

  <!-- Toast container -->
  <div class="toast-container" id="toast-container"></div>

  <!-- Loading state (before auth check) -->
  <div id="app-loading" class="auth-screen">
    <div class="spinner" style="width:32px;height:32px;border-width:4px;"></div>
  </div>

  <!-- Login screen -->
  <div id="login-screen" class="auth-screen" style="display:none;">
    <div class="auth-card">
      <h1>FillForm</h1>
      <p>AI-powered form automation. Sign in to save your profile and track deadlines.</p>
      <button class="google-btn" id="google-login-btn">
        <svg viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
        Sign in with Google
      </button>
    </div>
  </div>

  <!-- Profile creation screen -->
  <div id="profile-screen" class="auth-screen" style="display:none;">
    <div class="profile-card">
      <h2>Create your profile</h2>
      <p class="subtitle">We'll use this to check eligibility and autofill forms for you.</p>
      <div class="form-grid">
        <div class="form-group full">
          <label for="pf-name">Full Name</label>
          <input id="pf-name" type="text" placeholder="John Doe" />
        </div>
        <div class="form-group full">
          <label for="pf-email">Email</label>
          <input id="pf-email" type="email" placeholder="john@example.com" />
        </div>
        <div class="form-group">
          <label for="pf-phone">Phone</label>
          <input id="pf-phone" type="tel" placeholder="+91 98765 43210" />
        </div>
        <div class="form-group">
          <label for="pf-degree">Degree</label>
          <input id="pf-degree" type="text" placeholder="B.Tech" />
        </div>
        <div class="form-group">
          <label for="pf-branch">Branch</label>
          <input id="pf-branch" type="text" placeholder="Computer Science" />
        </div>
        <div class="form-group">
          <label for="pf-batch">Batch</label>
          <input id="pf-batch" type="text" placeholder="2022-2026" />
        </div>
        <div class="form-group">
          <label for="pf-percentage">Percentage / CGPA</label>
          <input id="pf-percentage" type="text" placeholder="8.5 CGPA" />
        </div>
        <div class="form-group">
          <label for="pf-backlogs">Backlogs</label>
          <input id="pf-backlogs" type="text" placeholder="None" />
        </div>
      </div>
      <button class="form-submit" id="profile-submit">Save Profile</button>
    </div>
  </div>

  <!-- Main app -->
  <div id="main-app" style="display:none;">
    <nav class="nav">
      <div class="nav-brand">FillForm</div>
      <div class="nav-user">
        <img id="nav-avatar" src="" alt="" />
        <span id="nav-name"></span>
        <button class="nav-logout" id="nav-logout">Logout</button>
      </div>
    </nav>

    <main class="container">
      <section class="hero">
        <h1>Analyze a form or job posting</h1>
        <p>Paste text or upload a PDF to extract deadlines, eligibility, and get autofill hints.</p>
      </section>

      <section class="input-section">
        <div class="input-grid">
          <div>
            <label for="text">Text input</label>
            <textarea id="text" placeholder="Paste a job description, application form, or notes here..."></textarea>
          </div>
          <div>
            <label for="file">PDF input</label>
            <input id="file" type="file" accept="application/pdf" />
            <button class="analyze-btn" id="submit">
              <span id="btn-label">Analyze</span>
            </button>
          </div>
        </div>
      </section>

      <div class="error-box" id="error-box"></div>

      <div class="results" id="results">
        <!-- Job Overview -->
        <h3 class="section-title">Job Overview</h3>
        <div class="card">
          <div class="card-grid">
            <div>
              <div class="card-field-label">Company</div>
              <div class="card-field-value" id="r-company">—</div>
            </div>
            <div>
              <div class="card-field-label">Role</div>
              <div class="card-field-value" id="r-role">—</div>
            </div>
            <div>
              <div class="card-field-label">CTC</div>
              <div class="card-field-value" id="r-ctc">—</div>
            </div>
            <div>
              <div class="card-field-label">Eligibility</div>
              <div class="card-field-value" id="r-eligibility">—</div>
            </div>
            <div>
              <div class="card-field-label">Criteria</div>
              <div class="card-field-value" id="r-criteria">—</div>
            </div>
            <div>
              <div class="card-field-label">Registration</div>
              <div class="card-field-value" id="r-registration">—</div>
              <div style="margin-top:8px;">
                <a class="btn-apply" id="r-apply" href="#" target="_blank" rel="noreferrer" style="display:none;">Quick Apply →</a>
              </div>
            </div>
          </div>
        </div>

        <!-- Deadline & Actions -->
        <h3 class="section-title">Deadline & Actions</h3>
        <div class="card deadline-card" id="deadline-card">
          <div class="card-field-label">Deadline</div>
          <div class="card-field-value" id="r-deadline">—</div>
          <div style="margin-top:8px;">
            <span class="status-pill" id="r-deadline-status">Not checked</span>
          </div>
          <div id="timer-section" style="display:none; margin-top:12px;">
            <div class="timer-bar"><div class="timer-fill" id="timer-fill"></div></div>
            <div class="timer-text" id="timer-text"></div>
          </div>
          <div class="deadline-actions" id="deadline-actions"></div>
        </div>

        <!-- Job Summary -->
        <h3 class="section-title">Job Summary</h3>
        <div class="card" id="summary-card">
          <div id="r-summary"></div>
        </div>
      </div>
    </main>
  </div>

  <script>
    const API = window.FILLFORM_API_BASE_URL || (function() {
      try {
        if (window.location.protocol.startsWith('http') && (window.location.port === '5000' || window.location.host.includes(':5000'))) {
          return window.location.origin;
        }
      } catch (e) {}
      return 'http://127.0.0.1:5000';
    })();

    let currentUser = null;
    let deadlineTimerId = null;

    // ── Toast ──
    function showToast(message, type = 'success') {
      const container = document.getElementById('toast-container');
      const toast = document.createElement('div');
      toast.className = `toast ${type}`;
      toast.textContent = message;
      container.appendChild(toast);
      setTimeout(() => toast.remove(), 3000);
    }

    // ── Auth ──
    async function checkAuth() {
      try {
        const res = await fetch(`${API}/api/auth/me`);
        if (res.ok) {
          currentUser = await res.json();
          if (currentUser.profile) {
            showMainApp();
          } else {
            showProfileForm();
          }
        } else {
          showLogin();
        }
      } catch (e) {
        showLogin();
      }
    }

    function showLogin() {
      document.getElementById('app-loading').style.display = 'none';
      document.getElementById('login-screen').style.display = 'flex';
      document.getElementById('profile-screen').style.display = 'none';
      document.getElementById('main-app').style.display = 'none';
    }

    function showProfileForm() {
      document.getElementById('app-loading').style.display = 'none';
      document.getElementById('login-screen').style.display = 'none';
      document.getElementById('profile-screen').style.display = 'flex';
      document.getElementById('main-app').style.display = 'none';
      if (currentUser) {
        document.getElementById('pf-name').value = currentUser.name || '';
        document.getElementById('pf-email').value = currentUser.email || '';
      }
    }

    function showMainApp() {
      document.getElementById('app-loading').style.display = 'none';
      document.getElementById('login-screen').style.display = 'none';
      document.getElementById('profile-screen').style.display = 'none';
      document.getElementById('main-app').style.display = 'block';
      if (currentUser) {
        document.getElementById('nav-name').textContent = currentUser.name || currentUser.email;
        const avatar = document.getElementById('nav-avatar');
        if (currentUser.picture) {
          avatar.src = currentUser.picture;
          avatar.style.display = 'inline';
        } else {
          avatar.style.display = 'none';
        }
      }
    }

    document.getElementById('google-login-btn').addEventListener('click', async () => {
      const res = await fetch(`${API}/api/auth/login`);
      const data = await res.json();
      if (data.auth_url) window.location.href = data.auth_url;
    });

    document.getElementById('profile-submit').addEventListener('click', async () => {
      const profileData = {
        name: document.getElementById('pf-name').value,
        email: document.getElementById('pf-email').value,
        phone: document.getElementById('pf-phone').value,
        degree: document.getElementById('pf-degree').value,
        branch: document.getElementById('pf-branch').value,
        batch: document.getElementById('pf-batch').value,
        percentage: document.getElementById('pf-percentage').value,
        backlog_rule: document.getElementById('pf-backlogs').value,
      };
      const res = await fetch(`${API}/api/auth/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profileData),
      });
      if (res.ok) {
        const profile = await res.json();
        currentUser.profile = profile;
        showMainApp();
      } else {
        showToast('Failed to save profile', 'error');
      }
    });

    document.getElementById('nav-logout').addEventListener('click', async () => {
      await fetch(`${API}/api/auth/logout`, { method: 'POST' });
      currentUser = null;
      showLogin();
    });

    // ── Helpers ──
    function format12Hour(date) {
      const pad = (v) => String(v).padStart(2, '0');
      const h24 = date.getHours();
      const h12 = h24 % 12 || 12;
      const mer = h24 >= 12 ? 'p.m.' : 'a.m.';
      return `${date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}, ${h12}:${pad(date.getMinutes())} ${mer}`;
    }

    function formatCompactDuration(ms) {
      if (ms <= 0) return 'Deadline passed';
      const totalMin = Math.floor(ms / 60000);
      const days = Math.floor(totalMin / 1440);
      const hours = Math.floor((totalMin % 1440) / 60);
      const minutes = totalMin % 60;
      const parts = [];
      if (days) parts.push(`${days}d`);
      if (hours) parts.push(`${hours}h`);
      parts.push(`${minutes}m`);
      return parts.join(' ');
    }

    function getDeadlineStatus(date) {
      const now = new Date();
      const startOfToday = new Date(now); startOfToday.setHours(0, 0, 0, 0);
      const startOfDeadline = new Date(date); startOfDeadline.setHours(0, 0, 0, 0);
      if (date < now) return 'expired';
      if (startOfToday.getTime() === startOfDeadline.getTime()) return 'today';
      return 'active';
    }

    function clearDeadlineTimer() {
      if (deadlineTimerId) { clearInterval(deadlineTimerId); deadlineTimerId = null; }
    }

    // ── Analysis ──
    document.getElementById('submit').addEventListener('click', async () => {
      const formData = new FormData();
      const text = document.getElementById('text').value;
      const file = document.getElementById('file').files[0];
      if (text) formData.append('text', text);
      if (file) formData.append('file', file);

      const btn = document.getElementById('submit');
      const btnLabel = document.getElementById('btn-label');
      btn.disabled = true;
      btnLabel.innerHTML = '<span class="spinner"></span> Analyzing...';
      document.getElementById('results').classList.remove('visible');
      document.getElementById('error-box').style.display = 'none';

      try {
        const response = await fetch(`${API}/api/analyze`, { method: 'POST', body: formData });
        if (!response.ok) {
          const body = await response.text();
          throw new Error(body || `Request failed with status ${response.status}`);
        }
        const data = await response.json();
        renderResults(data.extracted);
      } catch (error) {
        const msg = error instanceof Error ? error.message : 'Failed to fetch data.';
        document.getElementById('error-box').textContent = msg;
        document.getElementById('error-box').style.display = 'block';
      } finally {
        btn.disabled = false;
        btnLabel.textContent = 'Analyze';
      }
    });

    // ── Render ──
    function renderResults(ex) {
      document.getElementById('results').classList.add('visible');
      document.getElementById('r-company').textContent = ex?.company || '—';
      document.getElementById('r-role').textContent = ex?.role || '—';
      document.getElementById('r-ctc').textContent = ex?.ctc || '—';

      const elig = [];
      if (ex?.eligibility?.batch) elig.push(`Batch: ${ex.eligibility.batch}`);
      if (ex?.eligibility?.branches?.length) elig.push(`Branches: ${ex.eligibility.branches.join(', ')}`);
      if (ex?.eligibility?.degree) elig.push(`Degree: ${ex.eligibility.degree}`);
      document.getElementById('r-eligibility').textContent = elig.length ? elig.join(' | ') : '—';

      const crit = [];
      if (ex?.criteria?.percentage) crit.push(`Percentage: ${ex.criteria.percentage}`);
      if (ex?.criteria?.backlog_rule) crit.push(`Backlog: ${ex.criteria.backlog_rule}`);
      document.getElementById('r-criteria').textContent = crit.length ? crit.join(' | ') : '—';

      // Registration
      const regLink = ex?.registration_link;
      const regEl = document.getElementById('r-registration');
      const applyBtn = document.getElementById('r-apply');
      regEl.textContent = regLink || '—';
      if (regLink) {
        applyBtn.style.display = 'inline-flex';
        applyBtn.href = regLink;
      } else {
        applyBtn.style.display = 'none';
      }

      // Summary
      renderSummary(ex?.job_summary);

      // Deadline
      renderDeadline(ex);
    }

    function renderDeadline(ex) {
      clearDeadlineTimer();
      const card = document.getElementById('deadline-card');
      const statusEl = document.getElementById('r-deadline-status');
      const timerSection = document.getElementById('timer-section');
      const timerFill = document.getElementById('timer-fill');
      const timerText = document.getElementById('timer-text');
      const actionsEl = document.getElementById('deadline-actions');

      card.className = 'card deadline-card';
      statusEl.className = 'status-pill';
      timerSection.style.display = 'none';
      timerFill.style.width = '0%';
      timerText.textContent = '';
      actionsEl.innerHTML = '';

      const deadlineEl = document.getElementById('r-deadline');

      if (!ex?.deadline) {
        deadlineEl.textContent = '—';
        statusEl.textContent = 'Not checked';
        return;
      }

      const deadlineDate = new Date(ex.deadline);
      if (Number.isNaN(deadlineDate.getTime())) {
        deadlineEl.textContent = ex.deadline;
        return;
      }

      deadlineEl.textContent = format12Hour(deadlineDate);
      const status = getDeadlineStatus(deadlineDate);

      if (status === 'expired') {
        statusEl.textContent = 'Closed';
        statusEl.classList.add('expired');
        card.classList.add('expired');
      } else if (status === 'today') {
        statusEl.textContent = 'Deadline today';
        statusEl.classList.add('today');
        card.classList.add('today');
        timerSection.style.display = 'block';
        const deadlineTime = deadlineDate.getTime();
        const startOfDay = new Date(deadlineDate); startOfDay.setHours(0, 0, 0, 0);
        const totalWindow = Math.max(deadlineTime - startOfDay.getTime(), 1);
        const updateTimer = () => {
          const now = new Date();
          const remaining = deadlineTime - now.getTime();
          const elapsed = now.getTime() - startOfDay.getTime();
          timerFill.style.width = `${Math.min(Math.max((elapsed / totalWindow) * 100, 0), 100)}%`;
          timerText.textContent = remaining > 0 ? `${formatCompactDuration(remaining)} left` : 'Deadline passed';
          if (remaining <= 0) {
            statusEl.textContent = 'Closed';
            statusEl.className = 'status-pill expired';
            card.className = 'card deadline-card expired';
            clearDeadlineTimer();
          }
        };
        updateTimer();
        deadlineTimerId = setInterval(updateTimer, 1000);
      } else {
        statusEl.textContent = 'Active';
        statusEl.classList.add('active');
        card.classList.add('active');
      }

      // Calendar buttons
      if (status === 'active' || status === 'today') {
        renderCalendarActions(actionsEl, ex, status);
      }
    }

    async function renderCalendarActions(container, ex, deadlineStatus) {
      if (!currentUser?.profile?.id) return;

      const profileId = currentUser.profile.id;
      try {
        const res = await fetch(`${API}/api/calendar/status?profile_id=${profileId}`);
        const data = await res.json();

        if (data.connected) {
          const btn = document.createElement('button');
          btn.className = 'btn-calendar connected';
          btn.innerHTML = '📅 Add to Google Calendar';
          btn.addEventListener('click', async () => {
            btn.disabled = true;
            btn.innerHTML = '⏳ Creating...';
            const startDate = new Date(ex.deadline);
            const endDate = new Date(startDate.getTime() + 60 * 60 * 1000);
            const eventData = {
              summary: `${ex.company || 'FillForm'} — ${ex.role || 'Reminder'}`,
              description: `CTC: ${ex.ctc || 'N/A'}\nEligibility: ${ex.eligibility?.branches?.join(', ') || 'N/A'}\nLink: ${ex.registration_link || 'N/A'}`,
              start_datetime: startDate.toISOString(),
              end_datetime: endDate.toISOString(),
            };
            try {
              const createRes = await fetch(`${API}/api/calendar/create-event`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ profile_id: profileId, event_data: eventData }),
              });
              if (createRes.ok) {
                btn.className = 'btn-calendar added';
                btn.innerHTML = '✓ Added to Calendar';
                showToast('Event created in Google Calendar');
              } else {
                throw new Error('Failed');
              }
            } catch (e) {
              btn.innerHTML = '📅 Add to Google Calendar';
              btn.disabled = false;
              showToast('Failed to create event', 'error');
            }
          });
          container.appendChild(btn);
        } else {
          const connectBtn = document.createElement('button');
          connectBtn.className = 'btn-connect-cal';
          connectBtn.innerHTML = '🔗 Connect Google Calendar';
          connectBtn.addEventListener('click', async () => {
            const authRes = await fetch(`${API}/api/calendar/auth?profile_id=${profileId}`);
            const authData = await authRes.json();
            if (authData.auth_url) window.open(authData.auth_url, '_blank');
          });
          container.appendChild(connectBtn);
        }
      } catch (e) {
        // Calendar status check failed silently
      }
    }

    function renderSummary(details) {
      const el = document.getElementById('r-summary');
      el.innerHTML = '';
      if (!details) { el.textContent = '—'; return; }

      const wrapper = document.createElement('div');
      const addSection = (title, content) => {
        if (!content || (Array.isArray(content) && content.length === 0)) return;
        const section = document.createElement('div');
        section.className = 'summary-section';
        const h = document.createElement('h4');
        h.textContent = title;
        section.appendChild(h);
        if (Array.isArray(content)) {
          const list = document.createElement('ul');
          list.className = 'summary-list';
          content.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            list.appendChild(li);
          });
          section.appendChild(list);
        } else {
          const p = document.createElement('p');
          p.textContent = content;
          section.appendChild(p);
        }
        wrapper.appendChild(section);
      };
      addSection('Overview', details.overview);
      addSection('Highlights', details.highlights);
      addSection('Responsibilities', details.responsibilities);
      addSection('Requirements', details.requirements);
      addSection('Benefits', details.benefits);
      el.appendChild(wrapper);
    }

    // ── Init ──
    checkAuth();
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify the page loads**

Run: ` python -c "from backend.app import create_app; app = create_app(); print('Routes:'); [print(f'  {rule}') for rule in app.url_map.iter_rules() if 'auth' in str(rule)]"`

Expected: Shows `/api/auth/login`, `/api/auth/callback`, `/api/auth/me`, `/api/auth/logout`, `/api/auth/profile` routes.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat: add login screen, profile form, calendar button, and UI overhaul"
```

---

### Task 5: End-to-End Verification

**Files:** None (verification only)

- [ ] **Step 1: Start the server**

Run: `python -m backend.app`

Expected: Server starts on `http://127.0.0.1:5000` without errors.

- [ ] **Step 2: Verify login screen renders**

Open `http://127.0.0.1:5000` in a browser. Expected: "Sign in with Google" button visible, no errors in console.

- [ ] **Step 3: Verify auth flow (requires Google OAuth credentials)**

1. Set `GOOGLE_LOGIN_CLIENT_ID` and `GOOGLE_LOGIN_CLIENT_SECRET` in `backend/.env`
2. Click "Sign in with Google"
3. Complete Google consent
4. Expected: Redirected back, profile form shown (first time) or main app shown (returning user)

- [ ] **Step 4: Verify analysis still works**

Paste sample job text into the textarea, click "Analyze". Expected: Results appear in the new card layout. Deadline card shows status pill and, if active, "Add to Google Calendar" or "Connect Google Calendar" button.

- [ ] **Step 5: Verify calendar flow (requires calendar OAuth)**

1. Click "Connect Google Calendar" → complete OAuth
2. Return to app, click "Add to Google Calendar"
3. Expected: Button changes to "✓ Added to Calendar", toast appears

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "feat: complete auth + calendar + UI overhaul"
```
