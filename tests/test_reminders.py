from __future__ import annotations

from backend.services.reminders import build_reminder_plan


def test_no_deadline():
    result = build_reminder_plan([])
    assert result["has_deadline"] is False
    assert result["reminders"] == []


def test_single_deadline():
    result = build_reminder_plan(["2026-08-15"])
    assert result["has_deadline"] is True
    assert len(result["reminders"]) == 1
    assert "7 days before" in result["reminders"][0]["suggested_timing"]


def test_multiple_deadlines():
    result = build_reminder_plan(["2026-08-15", "2026-09-01"])
    assert result["has_deadline"] is True
    assert len(result["reminders"]) == 2
