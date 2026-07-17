"""API routes for FillForm."""

from flask import Blueprint, jsonify, request

from services.analyzer import analyze_text
from services.autofill import build_autofill_profile
from services.parser import parse_submission_input
from services.reminders import build_reminder_plan


api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health() -> tuple[object, int]:
    return jsonify({"status": "ok"}), 200


@api_bp.post("/api/analyze")
def api_analyze() -> tuple[object, int]:
    parsed = parse_submission_input(request)
    analysis = analyze_text(parsed["text"])
    autofill_profile = build_autofill_profile(parsed["text"])
    reminder_plan = build_reminder_plan(analysis.get("deadline_candidates", []))
    return jsonify(
        {
            "input": parsed,
            "analysis": analysis,
            "autofill": autofill_profile,
            "reminders": reminder_plan,
        }
    ), 200