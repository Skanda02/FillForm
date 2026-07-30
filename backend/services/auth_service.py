"""Google OAuth login and session management for FillForm."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import requests as http_requests
from google_auth_oauthlib.flow import Flow

from backend.config import get_google_auth_redirect_uri
from backend.database import get_collection

log = logging.getLogger(__name__)

LOGIN_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

CLIENT_SECRETS_PATH = str(Path(__file__).resolve().parent.parent / "client_secret.json")


def get_login_url(state: str, redirect_uri: str | None = None) -> tuple[str, str]:
    uri = redirect_uri or get_google_auth_redirect_uri()
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_PATH,
        scopes=LOGIN_SCOPES,
        redirect_uri=uri,
        autogenerate_code_verifier=True,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url, flow.code_verifier


def handle_login_callback(code: str, code_verifier: str, redirect_uri: str | None = None) -> dict | None:
    uri = redirect_uri or get_google_auth_redirect_uri()
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_PATH,
        scopes=LOGIN_SCOPES,
        redirect_uri=uri,
        code_verifier=code_verifier,
    )
    try:
        flow.fetch_token(code=code)
    except Exception:
        log.exception("Login token exchange failed")
        return None
    credentials = flow.credentials

    resp = http_requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {credentials.token}"},
    )
    if resp.status_code != 200:
        log.error("Google userinfo request failed: status=%s body=%s", resp.status_code, resp.text[:200])
        return None
    google_user = resp.json()

    col = get_collection("users")
    now = datetime.now(UTC).isoformat()
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
    from bson.errors import InvalidId

    col = get_collection("users")
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    doc = col.find_one({"_id": oid})
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
    from bson.errors import InvalidId

    from backend.services.profile_service import create_or_update_profile

    profile = create_or_update_profile(profile_data)
    if not profile:
        return None

    col = get_collection("users")
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return None
    col.update_one(
        {"_id": oid},
        {"$set": {"profile_id": profile["id"], "updated_at": datetime.now(UTC).isoformat()}},
    )
    return profile


def logout_user(session: dict) -> None:
    session.clear()
