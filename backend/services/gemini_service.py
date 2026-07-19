"""Gemini-powered extraction for FillForm."""

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from typing import Any

import requests

from config import get_gemini_api_key, get_gemini_model


GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"


PROMPT = """
You are extracting job-posting details from text or a PDF.
Return ONLY valid JSON with exactly these keys:
{
  "company": string | null,
  "role": string | null,
  "deadline": string | null,
  "registration_status": "active" | "closed" | "today" | "unknown",
  "registration_link": string | null,
  "ctc": string | null,
  "eligibility": {
    "batch": string | null,
    "branches": string[],
    "degree": string | null
  },
  "criteria": {
    "percentage": string | null,
    "backlog_rule": string | null
  },
  "job_summary": {
    "overview": string | null,
    "highlights": string[],
    "responsibilities": string[],
    "requirements": string[],
    "benefits": string[]
  }
}

Rules:
- Do not guess. Use null for missing text fields and [] for missing lists.
- Deadline must be ISO 8601 like 2026-08-20T15:00:00 when present.
- Keep eligibility and summary structured, concise, and readable.
- Exclude every field not listed above.
""".strip()


class GeminiExtractionError(RuntimeError):
	"""Raised when Gemini cannot return usable structured data."""


def _parse_json_response(text: str) -> dict[str, Any]:
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		match = re.search(r"\{.*\}", text, flags=re.DOTALL)
		if not match:
			raise GeminiExtractionError("Gemini did not return valid JSON.")
		return json.loads(match.group(0))


def _normalize_deadline(value: str | None) -> tuple[str | None, str]:
	if not value:
		return None, "unknown"

	candidate = value.strip().replace("Z", "+00:00")
	if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
		candidate = f"{candidate}T15:00:00"

	try:
		deadline = datetime.fromisoformat(candidate)
	except ValueError:
		return value, "unknown"

	now = datetime.now(deadline.tzinfo)
	if deadline.date() < now.date():
		return deadline.isoformat(), "closed"
	if deadline.date() == now.date():
		return deadline.isoformat(), "today"
	return deadline.isoformat(), "active"


def _build_contents(parsed_input: dict[str, Any]) -> list[dict[str, Any]]:
	parts: list[dict[str, Any]] = [{"text": PROMPT}]
	text = parsed_input.get("text") or ""
	filename = parsed_input.get("filename")
	file_bytes = parsed_input.get("file_bytes")
	mime_type = parsed_input.get("mime_type") or "application/pdf"

	if file_bytes:
		parts.append(
			{
				"inline_data": {
					"mime_type": mime_type,
					"data": base64.b64encode(file_bytes).decode("utf-8"),
				},
			}
		)
		if text:
			parts.append({"text": f"Extra pasted text for the same posting ({filename or 'uploaded file'}):\n{text}"})
	else:
		parts.append({"text": f"Job posting text:\n{text}"})

	return [{"role": "user", "parts": parts}]


def _post_to_gemini(parsed_input: dict[str, Any]) -> dict[str, Any]:
	api_key = get_gemini_api_key()
	if not api_key:
		raise GeminiExtractionError("Paste your Gemini API key in backend/.env as GOOGLE_API_KEY=YOUR_KEY_HERE")

	url = GEMINI_ENDPOINT.format(model=get_gemini_model(), api_key=api_key)
	payload = {
		"contents": _build_contents(parsed_input),
		"generationConfig": {
			"temperature": 0.2,
			"responseMimeType": "application/json",
		},
	}

	response = requests.post(url, json=payload, timeout=90)
	if not response.ok:
		raise GeminiExtractionError(f"Gemini request failed with status {response.status_code}: {response.text}")

	body = response.json()
	candidates = body.get("candidates") or []
	if not candidates:
		raise GeminiExtractionError("Gemini returned no candidates.")

	content = candidates[0].get("content") or {}
	parts = content.get("parts") or []
	if not parts or "text" not in parts[0]:
		raise GeminiExtractionError("Gemini response did not include structured text.")

	return _parse_json_response(parts[0]["text"])


def analyze_with_gemini(parsed_input: dict[str, Any]) -> dict[str, Any]:
	"""Send text or PDF bytes to Gemini and normalize the structured output."""

	data = _post_to_gemini(parsed_input)
	deadline, registration_status = _normalize_deadline(data.get("deadline"))

	eligibility = data.get("eligibility") or {}
	criteria = data.get("criteria") or {}
	job_summary = data.get("job_summary") or {}

	return {
		"company": data.get("company"),
		"role": data.get("role"),
		"deadline": deadline,
		"registration_status": data.get("registration_status") or registration_status,
		"registration_link": data.get("registration_link"),
		"ctc": data.get("ctc"),
		"eligibility": {
			"batch": eligibility.get("batch"),
			"branches": eligibility.get("branches") or [],
			"degree": eligibility.get("degree"),
		},
		"criteria": {
			"percentage": criteria.get("percentage"),
			"backlog_rule": criteria.get("backlog_rule"),
		},
		"job_summary": {
			"overview": job_summary.get("overview"),
			"highlights": job_summary.get("highlights") or [],
			"responsibilities": job_summary.get("responsibilities") or [],
			"requirements": job_summary.get("requirements") or [],
			"benefits": job_summary.get("benefits") or [],
		},
	}
