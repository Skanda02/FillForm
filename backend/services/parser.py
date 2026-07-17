"""Document parsing service."""

from __future__ import annotations

import os
import re
from typing import Any

from flask import Request

try:
	from pypdf import PdfReader
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing.
	PdfReader = None


def normalize_text(text: str) -> str:
	"""Collapse repeated whitespace and trim the input."""

	return re.sub(r"\s+", " ", text).strip()


def extract_text_from_pdf(file_storage: Any) -> str:
	"""Extract text from an uploaded PDF file object."""

	if PdfReader is None:
		raise RuntimeError("PDF support is unavailable. Install pypdf to enable uploads.")

	file_storage.stream.seek(0)
	reader = PdfReader(file_storage.stream)
	pages: list[str] = []
	for page in reader.pages:
		extracted = page.extract_text() or ""
		if extracted:
			pages.append(extracted)
	return "\n".join(pages).strip()


def parse_submission_input(request: Request) -> dict[str, Any]:
	"""Parse either plain text or an uploaded PDF from the request."""

	text = request.form.get("text", "").strip() if request.form else ""
	uploaded_file = request.files.get("file") if request.files else None

	if uploaded_file and uploaded_file.filename:
		filename = uploaded_file.filename
		_, extension = os.path.splitext(filename.lower())
		if extension != ".pdf":
			raise ValueError("Only PDF uploads are supported.")

		extracted_text = extract_text_from_pdf(uploaded_file)
		combined_text = "\n".join(part for part in [text, extracted_text] if part).strip()
		final_text = combined_text or extracted_text

		if not final_text:
			raise ValueError("The PDF did not contain readable text.")

		return {
			"source_type": "pdf",
			"filename": filename,
			"text": normalize_text(final_text),
			"character_count": len(final_text),
			"word_count": len(final_text.split()),
		}

	if text:
		return {
			"source_type": "text",
			"filename": None,
			"text": normalize_text(text),
			"character_count": len(text),
			"word_count": len(text.split()),
		}

	raise ValueError("Provide either text or a PDF file.")
