"""Text analysis helpers for FillForm."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, time
import re


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


def build_structured_summary(text: str) -> dict[str, object]:
	lines = [line.strip() for line in text.splitlines() if line.strip()]
	first_sentences = split_sentences(text)[:2]
	overview = " ".join(first_sentences) if first_sentences else (lines[0] if lines else "")
	bullet_lines = [line.lstrip("-•* ").strip() for line in lines if line.lstrip().startswith(("-", "•", "*"))]
	section_map: dict[str, list[str]] = {
		"responsibilities": [],
		"requirements": [],
		"benefits": [],
	}
	active_section: str | None = None
	section_aliases = {
		"responsibility": "responsibilities",
		"responsibilities": "responsibilities",
		"role responsibilities": "responsibilities",
		"job responsibilities": "responsibilities",
		"requirement": "requirements",
		"requirements": "requirements",
		"eligibility": "requirements",
		"qualification": "requirements",
		"qualifications": "requirements",
		"benefit": "benefits",
		"benefits": "benefits",
		"perks": "benefits",
	}

	for line in lines:
		lowered = line.lower().rstrip(":")
		matched_section = next((section for alias, section in section_aliases.items() if lowered == alias), None)
		if matched_section:
			active_section = matched_section
			continue

		if active_section and (line.startswith(("-", "•", "*")) or len(line) < 140):
			section_map[active_section].append(line.lstrip("-•* ").strip())

	return {
		"overview": overview,
		"highlights": bullet_lines[:5],
		"responsibilities": section_map["responsibilities"][:5],
		"requirements": section_map["requirements"][:5],
		"benefits": section_map["benefits"][:5],
	}


def _first_non_empty(values: list[str | None]) -> str | None:
	for value in values:
		if value:
			return value
	return None


def _clean_field(value: str) -> str:
	return re.sub(r"\s+", " ", value).strip(" \t\n\r\f\v•·|-:")


def _split_header_chunks(text: str) -> list[str]:
	first_block = text.split("\n", 1)[0]
	chunks = re.split(r"\s*[•|·|-]\s*", first_block)
	return [_clean_field(chunk) for chunk in chunks if _clean_field(chunk)]


def _looks_like_company(value: str) -> bool:
	forbidden = {
		"eligibility",
		"location",
		"deadline",
		"apply",
		"application",
		"job",
		"role",
		"experience",
		"requirements",
	}
	lowered = value.lower()
	return 2 <= len(value.split()) <= 6 and not any(word in lowered for word in forbidden)


def _looks_like_role(value: str) -> bool:
	role_keywords = (
		"engineer",
		"developer",
		"analyst",
		"intern",
		"manager",
		"scientist",
		"specialist",
		"associate",
		"architect",
		"consultant",
		"designer",
		"lead",
	)
	lowered = value.lower()
	return 2 <= len(value.split()) <= 10 and any(keyword in lowered for keyword in role_keywords)


def _looks_like_job_title(value: str) -> bool:
	if len(value.split()) > 12:
		return False
	return bool(
		re.search(
			r"\b(engineer|developer|analyst|designer|manager|specialist|associate|scientist|architect|consultant|lead|intern|tester|full stack|frontend|backend|software|data)\b",
			value,
			flags=re.IGNORECASE,
		)
	)


def _clean_url(url: str) -> str:
	return url.rstrip(".,);]}")


def _extract_labeled_value(text: str, labels: tuple[str, ...]) -> str | None:
	for line in text.splitlines():
		clean_line = line.strip()
		for label in labels:
			match = re.search(rf"^{re.escape(label)}\s*[:\-]\s*(.+)$", clean_line, flags=re.IGNORECASE)
			if match:
				return _clean_field(match.group(1))
	return None


def extract_company(text: str) -> str | None:
	labeled = _extract_labeled_value(text, ("company", "organization", "employer"))
	if labeled:
		return labeled

	lines = [_clean_field(line) for line in text.splitlines() if _clean_field(line)]
	for line in lines[:5]:
		if _looks_like_company(line):
			return line
	return None


def extract_role(text: str) -> str | None:
	labeled = _extract_labeled_value(text, ("role", "job role", "designation", "title", "job title", "position"))
	if labeled:
		return labeled

	lines = [_clean_field(line) for line in text.splitlines() if _clean_field(line)]
	for line in lines[:8]:
		if _looks_like_role(line) or _looks_like_job_title(line):
			return line

	match = re.search(
		r"\b(?:for the position of|position of|role of|job title:|designation:)\s*([A-Za-z0-9&/().,\- ]{4,120})",
		text,
		flags=re.IGNORECASE,
	)
	if match:
		return _clean_field(match.group(1))

	return None


def extract_registration_link(text: str) -> str | None:
	url_pattern = r'https?://[^\s<>"]+'
	lines = text.splitlines()

	for line in lines:
		if re.search(r"\b(apply|register|registration|apply now|quick apply)\b", line, re.IGNORECASE):
			match = re.search(url_pattern, line)
			if match:
				return _clean_url(match.group(0))

	match = re.search(url_pattern, text)
	return _clean_url(match.group(0)) if match else None


def extract_deadline_label(text: str) -> str | None:
	match = re.search(
		r"\b(?:deadline|last date|apply by|registration closes|registration deadline|apply before)\s*[:\-]?\s*([^.\n]+)",
		text,
		flags=re.IGNORECASE,
	)
	if match:
		return _clean_field(match.group(1))
	return None


def extract_ctc(text: str) -> str | None:
	patterns = [
		r"\b(?:CTC|salary|package|compensation)\s*[:\-]?\s*([^\n.]+)",
		r"\b(?:CTC|salary|package|compensation)\b[^\n]*?([₹$]?\s*\d[\d,\.\s]*(?:LPA|lpa|lakhs?|lakhs per annum|per annum|PA|pa|K|k)?)",
	]
	for pattern in patterns:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if match:
			return _clean_field(match.group(1))
	return None


def extract_eligible_degree(text: str) -> str | None:
	return _first_non_empty([
		_extract_labeled_value(text, ("degree", "qualification", "qualifications", "eligible degree", "educational qualification")),
		_extract_labeled_value(text, ("preferred degree", "preferred qualification")),
	])


def extract_eligibility(text: str) -> dict[str, object]:
	batch_patterns = [
		r"\b(?:batch|for batch|eligible batch|graduating in|pass out(?: year)?)\s*[:\-]?\s*([^\n.]+)",
		r"\b(20\d{2}\s*(?:-|to|/|and|&)\s*20\d{2})\b",
	]
	branch_keywords = (
		"branch",
		"branches",
		"eligible branches",
		"stream",
		"streams",
	)
	known_branches = [
		"CSE",
		"C.S.E.",
		"Computer Science",
		"Information Technology",
		"IT",
		"ECE",
		"EEE",
		"Mechanical",
		"Civil",
		"AIML",
		"AI",
		"Data Science",
		"ME",
	]

	batch_match = _first_non_empty([
		_clean_field(match.group(1))
		if (match := re.search(pattern, text, flags=re.IGNORECASE))
		else None
		for pattern in batch_patterns
	])

	branch_match = None
	for line in text.splitlines():
		if any(keyword in line.lower() for keyword in branch_keywords):
			match = re.search(r"(?:branch(?:es)?|eligible branches|stream(?:s)?)\s*[:\-]?\s*([^\n.]+)", line, flags=re.IGNORECASE)
			if match:
				branch_match = _clean_field(match.group(1))
				break

	branches: list[str] = []
	if branch_match:
		branches = [part.strip(" .;,") for part in re.split(r"\s*(?:,|/|&|and|or)\s*", branch_match) if part.strip(" .;,")]
	else:
		for branch in known_branches:
			if re.search(rf"\b{re.escape(branch)}\b", text, flags=re.IGNORECASE):
				branches.append(branch)
		branches = list(dict.fromkeys(branches))

	return {
		"batch": batch_match,
		"branches": branches,
		"degree": extract_eligible_degree(text),
	}


def extract_criteria(text: str) -> dict[str, object]:
	percentage_patterns = [
		r"\b(?:percentage|marks|minimum marks|min percentage|cutoff)\s*[:\-]?\s*([^\n.]+)",
		r"\b(\d{2}(?:\.\d+)?)\s*%",
	]
	backlog_patterns = [
		r"\b(?:backlog|backlogs|arrears|arrear)\b[^\n.]*",
		r"\b(?:no backlog|without backlog|zero backlog|0 backlogs?|no active backlog)\b",
	]

	percentage = None
	for pattern in percentage_patterns:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if match:
			percentage = _clean_field(match.group(1) if match.lastindex else match.group(0))
			break

	backlog_rule = None
	for pattern in backlog_patterns:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if match:
			backlog_rule = _clean_field(match.group(0))
			break

	return {
		"percentage": percentage,
		"backlog_rule": backlog_rule,
	}


def extract_registration_status(deadline_iso: str | None) -> str:
	if not deadline_iso:
		return "unknown"
	try:
		deadline = datetime.fromisoformat(deadline_iso)
	except ValueError:
		return "unknown"
	return "closed" if deadline < datetime.now(deadline.tzinfo) else "active"


def parse_deadline_iso(text: str) -> str | None:
	"""Return a normalized ISO deadline string if a date can be found."""

	patterns = [
		(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b", "%Y-%m-%d"),
		(r"\b(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\b", "%m/%d/%Y"),
		(r"\b(?P<date>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:,\s*\d{4})?)\b", None),
	]

	for pattern, format_string in patterns:
		match = re.search(pattern, text, flags=re.IGNORECASE)
		if not match:
			continue

		candidate = match.group("date").replace(".", "")
		parsed_date = None

		if format_string:
			if format_string == "%m/%d/%Y" and len(candidate.split("/")[-1]) == 2:
				year = int(candidate.split("/")[-1])
				candidate = candidate.rsplit("/", 1)[0] + f"/20{year:02d}"
			parsed_date = datetime.strptime(candidate, format_string).date()
		else:
			for candidate_format in ("%b %d, %Y", "%b %d %Y", "%B %d, %Y", "%B %d %Y"):
				try:
					parsed_date = datetime.strptime(candidate, candidate_format).date()
					break
				except ValueError:
					continue

		if parsed_date:
			return datetime.combine(parsed_date, time(15, 0)).isoformat()

	return None


def extract_structured_details(text: str) -> dict[str, object]:
	"""Extract a simple company/role/deadline structure from a job posting text."""

	cleaned_text = text.strip()
	company = extract_company(cleaned_text)
	role = extract_role(cleaned_text)
	deadline = parse_deadline_iso(cleaned_text)
	deadline_label = extract_deadline_label(cleaned_text)
	registration_link = extract_registration_link(cleaned_text)
	ctc = extract_ctc(cleaned_text)
	eligibility = extract_eligibility(cleaned_text)
	criteria = extract_criteria(cleaned_text)
	job_summary = build_structured_summary(cleaned_text)
	registration_status = extract_registration_status(deadline)

	return {
		"company": company,
		"role": role,
		"deadline": deadline,
		"deadline_label": deadline_label,
		"ctc": ctc,
		"eligibility": eligibility,
		"criteria": criteria,
		"registration_link": registration_link,
		"registration_status": registration_status,
		"job_summary": job_summary,
	}


def analyze_text(text: str) -> dict[str, object]:
	normalized_text = text.strip()
	sentences = split_sentences(normalized_text)
	deadline_candidates = extract_deadline_candidates(normalized_text)
	structured_details = extract_structured_details(normalized_text)

	return {
		"summary": summarize_text(normalized_text),
		"sentence_count": len(sentences),
		"keyword_count": len(extract_keywords(normalized_text)),
		"keywords": extract_keywords(normalized_text),
		"deadline_candidates": deadline_candidates,
		"structured": structured_details,
		"has_deadline_signal": bool(
			deadline_candidates
			or re.search(r"\b(due|deadline|submit|application)\b", normalized_text, re.IGNORECASE)
		),
	}
