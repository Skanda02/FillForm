"""Reminder scheduling service."""

from __future__ import annotations


def build_reminder_plan(deadline_candidates: list[str]) -> dict[str, object]:
	"""Create a simple reminder plan from detected deadline strings."""

	if not deadline_candidates:
		return {
			"has_deadline": False,
			"message": "No explicit deadline detected.",
			"reminders": [],
		}

	reminders = []
	for deadline in deadline_candidates:
		reminders.append(
			{
				"deadline": deadline,
				"suggested_timing": ["7 days before", "1 day before", "same day"],
			}
		)

	return {
		"has_deadline": True,
		"message": "Potential deadline signals detected.",
		"reminders": reminders,
	}
