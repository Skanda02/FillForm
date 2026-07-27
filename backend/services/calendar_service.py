from __future__ import annotations

import os
from datetime import UTC, datetime

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from backend.config import get_google_calendar_redirect_uri
from backend.database import get_collection

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _get_redirect_uri() -> str:
    return get_google_calendar_redirect_uri()


def _get_client_config() -> dict:
    return {
        "web": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [_get_redirect_uri()],
        }
    }


def get_auth_url(state: str) -> str:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        state=state,
    )
    return auth_url


def handle_callback(code: str, profile_id: str) -> bool:
    flow = Flow.from_client_config(
        _get_client_config(),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )
    flow.fetch_token(code=code)
    credentials = flow.credentials

    col = get_collection("calendar_tokens")
    col.update_one(
        {"profile_id": profile_id},
        {
            "$set": {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_expiry": credentials.expiry.isoformat() if credentials.expiry else None,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            "$setOnInsert": {
                "profile_id": profile_id,
                "created_at": datetime.now(UTC).isoformat(),
            },
        },
        upsert=True,
    )
    return True


def _get_credentials(profile_id: str) -> Credentials | None:
    col = get_collection("calendar_tokens")
    doc = col.find_one({"profile_id": profile_id})
    if not doc:
        return None
    return Credentials(
        token=doc.get("access_token"),
        refresh_token=doc.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        scopes=SCOPES,
    )


def is_connected(profile_id: str) -> bool:
    return _get_credentials(profile_id) is not None


def create_event(profile_id: str, event_data: dict) -> dict | None:
    creds = _get_credentials(profile_id)
    if not creds:
        return None

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": event_data.get("summary", "FillForm Reminder"),
        "description": event_data.get("description", ""),
        "start": {
            "dateTime": event_data["start_datetime"],
            "timeZone": "Asia/Kolkata",
        },
        "end": {
            "dateTime": event_data["end_datetime"],
            "timeZone": "Asia/Kolkata",
        },
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "email", "minutes": 7 * 24 * 60},
                {"method": "popup", "minutes": 24 * 60},
                {"method": "popup", "minutes": 60},
            ],
        },
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return {"event_id": created.get("id"), "html_link": created.get("htmlLink")}
