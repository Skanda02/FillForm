"""Form autofill service."""

from __future__ import annotations

import re


def _match(pattern: str, text: str) -> str | None:
    result = re.search(pattern, text, flags=re.IGNORECASE)
    return result.group(1).strip() if result else None


def build_autofill_profile(text: str) -> dict[str, str | None]:
    """Extract a few common profile fields from the text."""

    return {
        "name": _match(r"\bname\s*[:\-]\s*([^\n,;]+)", text),
        "email": _match(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", text),
        "phone": _match(r"(\+?\d[\d\s().-]{7,}\d)", text),
        "organization": _match(r"\b(?:company|organization|institution|school)\s*[:\-]\s*([^\n,;]+)", text),
    }
