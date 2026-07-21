"""Groq-powered extraction for FillForm."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

import requests

from backend.config import get_groq_api_key, get_groq_model


GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


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


class GroqExtractionError(RuntimeError):
	"""Raised when Groq cannot return usable structured data."""


def _parse_json_response(text: str) -> dict[str, Any]:
	try:
		return json.loads(text)
	except json.JSONDecodeError:
		match = re.search(r"\{.*\}", text, flags=re.DOTALL)
		if not match:
			raise GroqExtractionError("Groq did not return valid JSON.")
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


def _extract_text_from_pdf(file_bytes: bytes) -> str:
	try:
		from pypdf import PdfReader
		import io

		reader = PdfReader(io.BytesIO(file_bytes))
		pages = []
		for page in reader.pages:
			text = page.extract_text()
			if text:
				pages.append(text)
		return "\n\n".join(pages)
	except Exception:
		return "[PDF text extraction failed — include any pasted text instead]"


def _build_messages(parsed_input: dict[str, Any]) -> list[dict[str, str]]:
	text = parsed_input.get("text") or ""
	file_bytes = parsed_input.get("file_bytes")
	filename = parsed_input.get("filename")
	mime_type = parsed_input.get("mime_type") or "application/pdf"

	user_content = ""

	if file_bytes:
		if mime_type == "application/pdf":
			pdf_text = _extract_text_from_pdf(file_bytes)
			user_content = f"PDF content ({filename or 'uploaded file'}):\n{pdf_text}"
		else:
			user_content = f"File content ({filename or 'uploaded file'}) uploaded as {mime_type}."

		if text:
			user_content += f"\n\nExtra pasted text for the same posting:\n{text}"
	else:
		user_content = f"Job posting text:\n{text}"

	return [
		{"role": "system", "content": PROMPT},
		{"role": "user", "content": user_content},
	]


def _post_to_groq(parsed_input: dict[str, Any]) -> dict[str, Any]:
	api_key = get_groq_api_key()
	if not api_key:
		raise GroqExtractionError("Paste your Groq API key in backend/.env as GROQ_API_KEY=YOUR_KEY_HERE")

	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
	}

	payload = {
		"model": get_groq_model(),
		"messages": _build_messages(parsed_input),
		"temperature": 0.2,
		"response_format": {"type": "json_object"},
	}

	response = requests.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=90)
	if not response.ok:
		raise GroqExtractionError(f"Groq request failed with status {response.status_code}: {response.text}")

	body = response.json()
	choices = body.get("choices") or []
	if not choices:
		raise GroqExtractionError("Groq returned no choices.")

	message = choices[0].get("message") or {}
	content = message.get("content")
	if not content:
		raise GroqExtractionError("Groq response did not include content.")

	return _parse_json_response(content)


def analyze_with_groq(parsed_input: dict[str, Any]) -> dict[str, Any]:
	"""Send text or PDF bytes to Groq and normalize the structured output."""

	data = _post_to_groq(parsed_input)
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
