"""API routes for FillForm."""

from flask import Blueprint, jsonify, request

from services.gemini_service import GeminiExtractionError, analyze_with_gemini
from services.parser import parse_submission_input
from config import get_gemini_api_key, get_gemini_model


api_bp = Blueprint("api", __name__)


@api_bp.get("/health")
def health() -> tuple[object, int]:
    return jsonify({"status": "ok"}), 200


@api_bp.post("/api/analyze")
def api_analyze() -> tuple[object, int]:
    try:
        parsed = parse_submission_input(request)
        extracted = analyze_with_gemini(parsed)
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