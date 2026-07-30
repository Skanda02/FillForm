from __future__ import annotations

from backend.services.analyzer import (
    analyze_text,
    build_structured_summary,
    extract_company,
    extract_criteria,
    extract_ctc,
    extract_deadline_candidates,
    extract_deadline_label,
    extract_eligibility,
    extract_eligible_degree,
    extract_keywords,
    extract_registration_link,
    extract_registration_status,
    extract_role,
    parse_deadline_iso,
    split_sentences,
    summarize_text,
)


class TestSplitSentences:
    def test_basic_split(self):
        result = split_sentences("Hello world. How are you? Fine.")
        assert result == ["Hello world.", "How are you?", "Fine."]

    def test_single_sentence(self):
        result = split_sentences("Hello world.")
        assert result == ["Hello world."]

    def test_empty(self):
        assert split_sentences("") == []


class TestExtractDeadlineCandidates:
    def test_iso_date(self):
        assert extract_deadline_candidates("Deadline: 2026-08-15") == ["2026-08-15"]

    def test_us_date(self):
        result = extract_deadline_candidates("Due by 08/15/2026")
        assert result == ["08/15/2026"]

    def test_text_date(self):
        result = extract_deadline_candidates("Due Aug 15, 2026")
        assert "Aug 15, 2026" in result

    def test_no_date(self):
        assert extract_deadline_candidates("No deadline here") == []

    def test_deduplicates(self):
        result = extract_deadline_candidates("2026-08-15 and again 2026-08-15")
        assert result == ["2026-08-15"]


class TestExtractKeywords:
    def test_basic_keywords(self):
        text = "Python developer with JavaScript experience"
        result = extract_keywords(text, limit=3)
        assert len(result) <= 3

    def test_filters_stop_words(self):
        text = "the and of is for in to"
        assert extract_keywords(text) == []

    def test_short_words_filtered(self):
        text = "a b cd ef gh ij kl mn"
        assert extract_keywords(text) == []

    def test_limited_results(self):
        text = "one two three four five six seven eight nine ten"
        assert len(extract_keywords(text, limit=3)) <= 3


class TestSummarizeText:
    def test_returns_first_two_sentences(self):
        text = "First sentence. Second sentence. Third sentence."
        assert summarize_text(text) == "First sentence. Second sentence."

    def test_single_sentence(self):
        assert summarize_text("Only one.") == "Only one."

    def test_empty(self):
        assert summarize_text("") == ""


class TestBuildStructuredSummary:
    def test_returns_expected_keys(self):
        text = "Company Overview: A tech company.\nResponsibilities: Code\nRequirements: Python"
        result = build_structured_summary(text)
        assert "overview" in result
        assert "highlights" in result
        assert isinstance(result.get("responsibilities"), list)
        assert isinstance(result.get("requirements"), list)
        assert isinstance(result.get("benefits"), list)


class TestExtractCompany:
    def test_from_label(self):
        text = "Company: TechCorp\nSome other text"
        assert extract_company(text) == "TechCorp"


class TestExtractRole:
    def test_from_label(self):
        text = "Role: Software Engineer\nSome text"
        assert extract_role(text) == "Software Engineer"


class TestExtractRegistrationLink:
    def test_with_apply_label(self):
        text = "Apply at: https://example.com/apply"
        result = extract_registration_link(text)
        assert result == "https://example.com/apply"

    def test_no_link(self):
        assert extract_registration_link("No link here") is None


class TestExtractDeadlineLabel:
    def test_from_label(self):
        text = "Deadline: 2026-08-15"
        assert extract_deadline_label(text) == "2026-08-15"

    def test_no_deadline(self):
        assert extract_deadline_label("No deadline") is None


class TestExtractCtc:
    def test_from_label(self):
        text = "CTC: 12 LPA\nMore text"
        assert extract_ctc(text) == "12 LPA"


class TestExtractEligibleDegree:
    def test_from_label(self):
        text = "Degree: B.E.\nMore"
        assert extract_eligible_degree(text) == "B.E."

    def test_no_degree(self):
        assert extract_eligible_degree("Text") is None


class TestExtractEligibility:
    def test_returns_dict_with_keys(self):
        text = "Batch: 2024\nBranches: CSE, ECE\nDegree: B.E."
        result = extract_eligibility(text)
        assert "batch" in result
        assert "branches" in result
        assert isinstance(result["branches"], list)
        assert "degree" in result


class TestExtractCriteria:
    def test_returns_dict_with_keys(self):
        text = "CGPA >= 7.5\nNo backlog"
        result = extract_criteria(text)
        assert "percentage" in result
        assert "backlog_rule" in result


class TestExtractRegistrationStatus:
    def test_active_when_future(self):
        assert extract_registration_status("2099-01-01T15:00:00") == "active"

    def test_closed_when_past(self):
        assert extract_registration_status("2020-01-01T15:00:00") == "closed"

    def test_unknown_when_none(self):
        assert extract_registration_status(None) == "unknown"


class TestParseDeadlineIso:
    def test_parses_iso_date(self):
        result = parse_deadline_iso("2026-08-15")
        assert result is not None
        assert "2026-08-15" in result

    def test_returns_none_for_invalid(self):
        assert parse_deadline_iso("not a date") is None


class TestAnalyzeText:
    def test_returns_all_keys(self):
        text = "Company: TestCorp\nRole: Engineer\nDeadline: 2026-08-15"
        result = analyze_text(text)
        assert "summary" in result
        assert "sentence_count" in result
        assert "keyword_count" in result
        assert "keywords" in result
        assert "deadline_candidates" in result
        assert "structured" in result
        assert "has_deadline_signal" in result
