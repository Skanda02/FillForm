"""API routes for FillForm."""

from __future__ import annotations

import hmac
import logging
import secrets

from flask import Blueprint, jsonify, redirect, request, session

log = logging.getLogger(__name__)

from backend.config import get_groq_api_key, get_groq_model
from backend.limiter import limiter
from backend.services.analyzer import analyze_text
from backend.services.auth_service import (
    create_profile_for_user,
    get_current_user,
    get_login_url,
    handle_login_callback,
    logout_user,
)
from backend.services.calendar_service import create_event, get_auth_url, handle_callback, is_connected
from backend.services.eligibility_service import check_eligibility
from backend.services.groq_service import GroqExtractionError, analyze_with_groq
from backend.services.parser import parse_submission_input
from backend.services.profile_service import (
    create_or_update_profile,
    delete_profile,
    get_default_profile,
    get_profile,
    list_profiles,
)
from backend.services.reminders import build_reminder_plan
from database.models import save_submission


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
@limiter.limit("10 per minute")
def api_analyze() -> tuple[object, int]:
    if request.method == "OPTIONS":
        return jsonify({}), 200

    try:
        parsed = parse_submission_input(request)
        if get_groq_api_key():
            extracted = analyze_with_groq(parsed)
            deadline = extracted.get("deadline")
            submission_id = save_submission(
                source_type=parsed["source_type"],
                filename=parsed["filename"],
                text=parsed["text"],
                summary=extracted.get("job_summary", {}).get("overview"),
                deadline_candidates=[deadline] if deadline else [],
                has_deadline_signal=bool(deadline),
                reminder_plan=build_reminder_plan([deadline] if deadline else []),
            )
        else:
            analysis = analyze_text(parsed["text"])
            extracted = _build_local_extracted(analysis)
            submission_id = save_submission(
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
        return jsonify({"extracted": extracted, "submission_id": submission_id}), 200
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
    limit = request.args.get("limit", 20, type=int)
    offset = request.args.get("offset", 0, type=int)
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return jsonify(list_profiles(limit=limit, offset=offset)), 200


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

    try:
        sub_id = int(submission_id)
    except (TypeError, ValueError):
        return jsonify({"error": "submission_id must be a valid integer"}), 400

    result = check_eligibility(sub_id, profile_id)
    return jsonify(result), 200


@api_bp.get("/api/calendar/auth")
def api_calendar_auth() -> tuple[object, int]:
    profile_id = request.args.get("profile_id")
    if not profile_id:
        return jsonify({"error": "profile_id required"}), 400
    state = secrets.token_urlsafe(32)
    session["calendar_oauth_state"] = state
    session["calendar_profile_id"] = profile_id
    auth_url = get_auth_url(state)
    return jsonify({"auth_url": auth_url}), 200


@api_bp.get("/api/calendar/callback")
def api_calendar_callback() -> tuple[object, int]:
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400
    expected_state = session.pop("calendar_oauth_state", None)
    profile_id = session.pop("calendar_profile_id", None)
    if not state or not hmac.compare_digest(state, expected_state or ""):
        log.warning("Calendar OAuth state mismatch: expected=%s got=%s", expected_state, state)
        return jsonify({"error": "Invalid OAuth state"}), 401
    if not profile_id:
        return jsonify({"error": "profile_id not found in session"}), 400
    handle_callback(code, profile_id)
    return redirect(request.host_url)


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
    redirect_uri = f"{request.host_url.rstrip('/')}/api/auth/callback"
    session["login_redirect_uri"] = redirect_uri
    auth_url, code_verifier = get_login_url(state, redirect_uri=redirect_uri)
    session["code_verifier"] = code_verifier
    return jsonify({"auth_url": auth_url}), 200


@api_bp.get("/api/auth/callback")
def api_auth_callback() -> tuple[object, int]:
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Authorization code not provided"}), 400

    code_verifier = session.get("code_verifier")
    redirect_uri = session.get("login_redirect_uri")

    if not code_verifier:
        return jsonify({"error": "Session expired or code_verifier missing. Please try logging in again."}), 400

    user = handle_login_callback(code, code_verifier, redirect_uri=redirect_uri)
    if not user:
        return jsonify({"error": "Failed to authenticate with Google"}), 401

    session["user_id"] = user["id"]
    return redirect(f"{request.host_url.rstrip('/')}")


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
