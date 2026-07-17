"""Text analysis helpers for FillForm."""

from __future__ import annotations

import re
from collections import Counter


STOP_WORDS = {
	"a",
	"an",
	"and",
	"are",
	"as",
	"at",
	"be",
	"by",
	"for",
	"from",
	"has",
	"have",
	"in",
	"is",
	"it",
	"of",
	"on",
	"or",
	"that",
	"the",
	"this",
	"to",
	"was",
	"were",
	"with",
}


def split_sentences(text: str) -> list[str]:
	sentences = re.split(r"(?<=[.!?])\s+", text.strip())
	return [sentence.strip() for sentence in sentences if sentence.strip()]


def extract_deadline_candidates(text: str) -> list[str]:
	patterns = [
		r"\b\d{4}-\d{2}-\d{2}\b",
		r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
		r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?\b",
	]

	matches: list[str] = []
	for pattern in patterns:
		matches.extend(re.findall(pattern, text, flags=re.IGNORECASE))
	return list(dict.fromkeys(matches))


def extract_keywords(text: str, limit: int = 8) -> list[str]:
	words = re.findall(r"[A-Za-z][A-Za-z'-]+", text.lower())
	filtered = [word for word in words if word not in STOP_WORDS and len(word) > 2]
	return [word for word, _ in Counter(filtered).most_common(limit)]


def summarize_text(text: str) -> str:
	sentences = split_sentences(text)
	if not sentences:
		return ""
	return " ".join(sentences[:2])


def analyze_text(text: str) -> dict[str, object]:
	normalized_text = text.strip()
	sentences = split_sentences(normalized_text)
	deadline_candidates = extract_deadline_candidates(normalized_text)

	return {
		"summary": summarize_text(normalized_text),
		"sentence_count": len(sentences),
		"keyword_count": len(extract_keywords(normalized_text)),
		"keywords": extract_keywords(normalized_text),
		"deadline_candidates": deadline_candidates,
		"has_deadline_signal": bool(
			deadline_candidates
			or re.search(r"\b(due|deadline|submit|application)\b", normalized_text, re.IGNORECASE)
		),
	}
