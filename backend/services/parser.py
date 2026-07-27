"""Document parsing service."""

from __future__ import annotations

import os
import re
from typing import Any

from flask import Request


def normalize_text(text: str) -> str:
    """Collapse repeated whitespace and trim the input."""

    return re.sub(r"\s+", " ", text).strip()


def parse_submission_input(request: Request) -> dict[str, Any]:
    """Parse either plain text or an uploaded PDF from the request."""

    text = request.form.get("text", "").strip() if request.form else ""
    uploaded_file = request.files.get("file") if request.files else None

    if uploaded_file and uploaded_file.filename:
        filename = uploaded_file.filename
        _, extension = os.path.splitext(filename.lower())
        if extension != ".pdf":
            raise ValueError("Only PDF uploads are supported.")

        file_bytes = uploaded_file.read()
        if not file_bytes:
            raise ValueError("The uploaded PDF is empty.")

        return {
            "source_type": "pdf",
            "filename": filename,
            "text": normalize_text(text),
            "file_bytes": file_bytes,
            "mime_type": uploaded_file.mimetype or "application/pdf",
            "character_count": len(text),
            "word_count": len(text.split()),
        }

    if text:
        return {
            "source_type": "text",
            "filename": None,
            "text": normalize_text(text),
            "file_bytes": None,
            "mime_type": None,
            "character_count": len(text),
            "word_count": len(text.split()),
        }

    raise ValueError("Provide either text or a PDF file.")
