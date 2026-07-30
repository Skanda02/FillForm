from __future__ import annotations

import io
from unittest.mock import Mock

from backend.services.parser import normalize_text, parse_submission_input


class TestNormalizeText:
    def test_collapses_whitespace(self):
        assert normalize_text("hello   world") == "hello world"

    def test_strips_whitespace(self):
        assert normalize_text("  hello world  ") == "hello world"

    def test_preserves_newlines_as_spaces(self):
        assert normalize_text("hello\nworld") == "hello world"

    def test_empty_string(self):
        assert normalize_text("") == ""


class TestParseSubmissionInput:
    def test_with_form_text(self):
        request = Mock()
        request.form = {"text": "hello world"}
        request.files = {}
        result = parse_submission_input(request)
        assert result["source_type"] == "text"
        assert result["text"] == "hello world"
        assert result["character_count"] == 11
        assert result["word_count"] == 2

    def test_with_pdf_file(self):
        request = Mock()
        request.form = {}
        file_mock = Mock()
        file_mock.filename = "test.pdf"
        file_mock.read.return_value = b"fake pdf content"
        request.files = {"file": file_mock}
        result = parse_submission_input(request)
        assert result["source_type"] == "pdf"
        assert result["filename"] == "test.pdf"
        assert result["file_bytes"] == b"fake pdf content"

    def test_raises_on_no_input(self):
        request = Mock()
        request.form = {}
        request.files = {}
        try:
            parse_submission_input(request)
            assert False, "expected ValueError"
        except ValueError:
            pass

    def test_raises_on_empty_text(self):
        request = Mock()
        request.form = {"text": ""}
        request.files = {}
        try:
            parse_submission_input(request)
            assert False, "expected ValueError"
        except ValueError:
            pass

    def test_raises_on_non_pdf(self):
        request = Mock()
        request.form = {}
        file_mock = Mock()
        file_mock.filename = "test.txt"
        request.files = {"file": file_mock}
        try:
            parse_submission_input(request)
            assert False, "expected ValueError"
        except ValueError:
            pass

    def test_with_text_and_pdf_text_takes_precedence(self):
        request = Mock()
        request.form = {"text": "pasted text"}
        file_mock = Mock()
        file_mock.filename = "test.pdf"
        file_mock.read.return_value = b"pdf content"
        request.files = {"file": file_mock}
        result = parse_submission_input(request)
        assert result["source_type"] == "pdf"
        assert result["text"] == "pasted text"
