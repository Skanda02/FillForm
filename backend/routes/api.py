"""API routes for FillForm."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Blueprint, jsonify, redirect, request, session

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR.parent))

from backend.services.groq_service import GroqExtractionError, analyze_with_groq
from backend.services.parser import parse_submission_input
from backend.services.analyzer import analyze_text
from backend.services.autofill import build_autofill_profile
from backend.services.reminders import build_reminder_plan
from backend.config import get_groq_api_key, get_groq_model
from database.models import save_submission
from backend.services.profile_service import (
    create_or_update_profile,
    get_profile,
    get_default_profile,
    delete_profile,
    list_profiles,
)
from backend.services.eligibility_service import check_eligibility
import secrets
from flask import redirect
from backend.services.calendar_service import get_auth_url, handle_callback, create_event, is_connected
from backend.services.auth_service import (
    get_login_url,
    handle_login_callback,
    get_current_user,
    create_profile_for_user,
    logout_user,
)


def _build_local_extracted(analysis: dict[str, object]) -> dict[str, object]:
    deadline_candidates = analysis.get("deadline_candidates", []) or []
    deadline = deadline_candidates[0] if deadline_candidates else None
    return {
        "company": None,
        "role": None,
        "deadline": deadline,
        "registration_status": "unknown",
        "registration_link": None,
        "ctc": None,
        "eligibility": {"batch": None, "branches": [], "degree": None},
        "criteria": {"percentage": None, "backlog_rule": None},
        "job_summary": {
            "overview": analysis.get("summary"),
            "highlights": analysis.get("keywords", []),
            "responsibilities": [],
            "requirements": [],
            "benefits": [],
        },
    }


api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health() -> tuple[object, int]:
    return jsonify({"status": "ok"}), 200


@api_bp.post("/api/analyze")
def api_analyze() -> tuple[object, int]:
    # lightweight request tracing to help diagnose 405/preflight issues
    print("[api_analyze] incoming from", request.remote_addr, "method", request.method)
    print("[api_analyze] Content-Type:", request.headers.get("Content-Type"))

    # Explicitly respond to CORS preflight if it arrives here
    if request.method == "OPTIONS":
        print("[api_analyze] preflight OPTIONS received")
        return jsonify({}), 200

    try:
        parsed = parse_submission_input(request)
        if get_groq_api_key():
            extracted = analyze_with_groq(parsed)
        else:
            analysis = analyze_text(parsed["text"])
            extracted = _build_local_extracted(analysis)
            save_submission(
                source_type=parsed["source_type"],
                filename=parsed["filename"],
                text=parsed["text"],
                summary=analysis.get("summary"),
                sentence_count=analysis.get("sentence_count"),
                keyword_count=analysis.get("keyword_count"),
                keywords=analysis.get("keywords"),
                deadline_candidates=analysis.get("deadline_candidates"),
                has_deadline_signal=analysis.get("has_deadline_signal", False),
                reminder_plan=build_reminder_plan(analysis.get("deadline_candidates", [])),
            )
        return jsonify({"extracted": extracted}), 200
    except GroqExtractionError as error:
        return jsonify({"error": str(error)}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@api_bp.get("/api/diag")
def api_diag() -> tuple[object, int]:
    """Lightweight diagnostic: report whether a Groq API key is loaded and which model is configured.

    This does NOT return the key value.
    """
    key_present = bool(get_groq_api_key())
    model = get_groq_model()
    return jsonify({"groq_key_present": key_present, "groq_model": model}), 200


@api_bp.get("/api/profiles")
def api_list_profiles() -> tuple[object, int]:
    return jsonify(list_profiles()), 200


@api_bp.get("/api/profiles/default")
def api_get_default_profile() -> tuple[object, int]:
    profile = get_default_profile()
    if not profile:
        return jsonify({"error": "No profile found"}), 404
    return jsonify(profile), 200


@api_bp.get("/api/profiles/<profile_id>")
def api_get_profile(profile_id: str) -> tuple[object, int]:
    profile = get_profile(profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile), 200


@api_bp.post("/api/profiles")
def api_create_profile() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    profile = create_or_update_profile(data)
    return jsonify(profile), 201


@api_bp.put("/api/profiles/<profile_id>")
def api_update_profile(profile_id: str) -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    profile = create_or_update_profile(data, profile_id)
    if not profile:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify(profile), 200


@api_bp.delete("/api/profiles/<profile_id>")
def api_delete_profile(profile_id: str) -> tuple[object, int]:
    deleted = delete_profile(profile_id)
    if not deleted:
        return jsonify({"error": "Profile not found"}), 404
    return jsonify({"success": True}), 200


@api_bp.post("/api/check-eligibility")
def api_check_eligibility() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    submission_id = data.get("submission_id")
    profile_id = data.get("profile_id")

    if not submission_id or not profile_id:
        return jsonify({"error": "submission_id and profile_id required"}), 400

    result = check_eligibility(int(submission_id), profile_id)
    return jsonify(result), 200


@api_bp.get("/api/calendar/auth")
def api_calendar_auth() -> tuple[object, int]:
    profile_id = request.args.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    state = secrets.token_urlsafe(32)
    auth_url = get_auth_url(state)
    return jsonify({"auth_url": auth_url}), 200


@api_bp.get("/api/calendar/callback")
def api_calendar_callback() -> tuple[object, int]:
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400
    handle_callback(code, state)
    return redirect("http://127.0.0.1:5000")


@api_bp.post("/api/calendar/create-event")
def api_calendar_create_event() -> tuple[object, int]:
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    profile_id = data.get("profile_id")
    event_data = data.get("event_data")

    if not profile_id or not event_data:
        return jsonify({"error": "profile_id and event_data required"}), 400

    result = create_event(profile_id, event_data)
    if not result:
        return jsonify({"error": "Calendar not connected"}), 400
    return jsonify(result), 201


@api_bp.get("/api/calendar/status")
def api_calendar_status() -> tuple[object, int]:
    profile_id = request.args.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    return jsonify({"connected": is_connected(profile_id)}), 200


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