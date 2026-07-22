"""Google OAuth login and session management for FillForm."""

from __future__ import annotations

from datetime import datetime, timezone

import requests as http_requests
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
    serialized = {**doc, "id": str(doc["_id"])}
    del serialized["_id"]
    return serialized


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


def get_user_id_from_session(session: dict) -> str | None:
    return session.get("user_id")


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
