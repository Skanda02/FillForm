"""Resume optimization service for FillForm."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

from backend.config import get_groq_api_key, get_groq_model
from database.models import list_resume_requests, save_resume_request

log = logging.getLogger(__name__)

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

RESUME_PROMPT = """
You are a professional resume optimization expert. Given a job description and the user's current resume, produce an optimized version.

Return ONLY valid JSON with these keys:
{
  "optimized_resume": string,
  "changes_summary": string
}

Rules:
- Tailor the resume to the job description
- Keep factual accuracy — do not invent experience
- Highlight relevant skills and achievements
- Keep same length or slightly shorter
- changes_summary should list 3-5 key changes made
""".strip()


def _call_groq(job_description: str, original_resume: str) -> dict[str, Any]:
    api_key = get_groq_api_key()
    if not api_key:
        return {"error": "Groq API key not configured"}

    user_content = f"Job Description:\n{job_description}\n\nCurrent Resume:\n{original_resume}"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": get_groq_model(),
        "messages": [
            {"role": "system", "content": RESUME_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    response = requests.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=90)
    if not response.ok:
        log.error("Groq resume request failed: %s %s", response.status_code, response.text)
        return {"error": f"Groq request failed: {response.status_code}"}

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        return {"error": "Groq returned no choices"}

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        return {"error": "Groq returned empty content"}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Groq returned invalid JSON"}


def optimize_resume(job_description: str, original_resume: str) -> dict[str, Any]:
    result = _call_groq(job_description, original_resume)
    if "error" in result:
        return result

    request_id = save_resume_request(
        job_description=job_description,
        original_resume=original_resume,
        optimized_resume=result.get("optimized_resume"),
        changes_summary=result.get("changes_summary"),
        completed=True,
    )

    return {
        "id": request_id,
        "optimized_resume": result.get("optimized_resume"),
        "changes_summary": result.get("changes_summary"),
    }


def get_resume_requests() -> list[dict[str, Any]]:
    return list_resume_requests()
