"""API routes for FillForm."""

from __future__ import annotations

import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR.parent))

from backend.services.gemini_service import GeminiExtractionError, analyze_with_gemini
from backend.services.parser import parse_submission_input
from backend.services.analyzer import analyze_text
from backend.services.autofill import build_autofill_profile
from backend.services.reminders import build_reminder_plan
from backend.config import get_gemini_api_key, get_gemini_model
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
        if get_gemini_api_key():
            extracted = analyze_with_gemini(parsed)
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
    except GeminiExtractionError as error:
        return jsonify({"error": str(error)}), 502
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@api_bp.get("/api/diag")
def api_diag() -> tuple[object, int]:
    """Lightweight diagnostic: report whether a Gemini API key is loaded and which model is configured.

    This does NOT return the key value.
    """
    key_present = bool(get_gemini_api_key())
    model = get_gemini_model()
    return jsonify({"gemini_key_present": key_present, "gemini_model": model}), 200