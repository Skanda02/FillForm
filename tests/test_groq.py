from __future__ import annotations

from unittest.mock import ANY, Mock, patch

from backend.services.groq_service import (
    GroqExtractionError,
    _normalize_deadline,
    _parse_json_response,
    analyze_with_groq,
)


class TestParseJsonResponse:
    def test_valid_json(self):
        assert _parse_json_response('{"company": "Test"}') == {"company": "Test"}

    def test_invalid_json_with_braces(self):
        result = _parse_json_response('Some text {"company": "Test"} more text')
        assert result == {"company": "Test"}

    def test_no_json_raises(self):
        try:
            _parse_json_response("No JSON here")
            assert False, "expected GroqExtractionError"
        except GroqExtractionError:
            pass


class TestNormalizeDeadline:
    def test_none_input(self):
        result, status = _normalize_deadline(None)
        assert result is None
        assert status == "unknown"

    def test_empty_input(self):
        result, status = _normalize_deadline("")
        assert result is None
        assert status == "unknown"

    def test_future_date_active(self):
        result, status = _normalize_deadline("2099-06-15")
        assert status == "active"
        assert "2099-06-15" in result

    def test_past_date_closed(self):
        result, status = _normalize_deadline("2020-01-01")
        assert status == "closed"
        assert "2020-01-01" in result

    def test_today_date(self):
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result, status = _normalize_deadline(today)
        assert status == "today"
        assert today in result

    def test_invalid_date_unknown(self):
        result, status = _normalize_deadline("not-a-date")
        assert status == "unknown"
        assert result == "not-a-date"


class TestAnalyzeWithGroq:
    def test_successful_response(self):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"company": "TestCorp", "role": "Engineer", "deadline": null}'}}]
        }

        with patch("backend.services.groq_service.requests.post", return_value=mock_response):
            with patch("backend.services.groq_service.get_groq_api_key", return_value="test-key"):
                result = analyze_with_groq({"text": "Test job posting"})

        assert result["company"] == "TestCorp"
        assert result["role"] == "Engineer"
        assert result["deadline"] is None
        assert result["registration_status"] == "unknown"
        assert "eligibility" in result
        assert "criteria" in result
        assert "job_summary" in result

    def test_missing_api_key(self):
        with patch("backend.services.groq_service.get_groq_api_key", return_value=None):
            try:
                analyze_with_groq({"text": "test"})
                assert False, "expected GroqExtractionError"
            except GroqExtractionError as e:
                assert "Groq API key" in str(e)

    def test_api_error_response(self):
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        with patch("backend.services.groq_service.requests.post", return_value=mock_response):
            with patch("backend.services.groq_service.get_groq_api_key", return_value="test-key"):
                try:
                    analyze_with_groq({"text": "test"})
                    assert False, "expected GroqExtractionError"
                except GroqExtractionError as e:
                    assert "429" in str(e)

    def test_no_choices(self):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"choices": []}

        with patch("backend.services.groq_service.requests.post", return_value=mock_response):
            with patch("backend.services.groq_service.get_groq_api_key", return_value="test-key"):
                try:
                    analyze_with_groq({"text": "test"})
                    assert False, "expected GroqExtractionError"
                except GroqExtractionError:
                    pass

    def test_empty_content(self):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"choices": [{"message": {"content": ""}}]}

        with patch("backend.services.groq_service.requests.post", return_value=mock_response):
            with patch("backend.services.groq_service.get_groq_api_key", return_value="test-key"):
                try:
                    analyze_with_groq({"text": "test"})
                    assert False, "expected GroqExtractionError"
                except GroqExtractionError:
                    pass

    def test_parses_deadline_and_status(self):
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"company": "X", "deadline": "2099-06-15"}'}}]
        }

        with patch("backend.services.groq_service.requests.post", return_value=mock_response):
            with patch("backend.services.groq_service.get_groq_api_key", return_value="test-key"):
                result = analyze_with_groq({"text": "test"})

        assert result["registration_status"] == "active"
