from __future__ import annotations

import re

from backend.services.profile_service import get_profile
from database.models import get_submission


def _parse_percentage(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", str(value))
    return float(match.group(1)) if match else None


def check_eligibility(submission_id: int, profile_id: str) -> dict:
    submission = get_submission(submission_id)
    if not submission:
        return {"eligible": False, "reasons": ["Submission not found"], "checked": False}

    profile = get_profile(profile_id)
    if not profile:
        return {"eligible": False, "reasons": ["Profile not found"], "checked": False}

    reasons = []
    eligible = True

    text = submission.get("text", "")

    batch_match = re.search(r"(?:batch|year)\s*[:=]?\s*(\d{4})", text, re.IGNORECASE)
    if batch_match:
        required_batch = batch_match.group(1)
        grad_year = str(profile.get("graduation_year", ""))
        if grad_year and required_batch not in grad_year:
            eligible = False
            reasons.append(f"Batch mismatch: requires {required_batch}, you are {grad_year}")

    branches_match = re.search(r"(?:branches?|departments?)\s*[:=]?\s*([^\n]+)", text, re.IGNORECASE)
    if branches_match:
        required_branches = [b.strip().upper() for b in branches_match.group(1).split(",")]
        user_branch = (profile.get("branch") or "").upper()
        if user_branch and required_branches and user_branch not in required_branches:
            eligible = False
            reasons.append(f"Branch mismatch: requires {', '.join(required_branches)}, you are {user_branch}")

    degree_match = re.search(r"(?:degree|qualification)\s*[:=]?\s*([^\n]+)", text, re.IGNORECASE)
    if degree_match:
        required_degree = degree_match.group(1).strip().upper()
        user_degree = (profile.get("degree") or "").upper()
        if user_degree and required_degree and required_degree not in user_degree:
            eligible = False
            reasons.append(f"Degree mismatch: requires {required_degree}, you have {user_degree}")

    pct_match = re.search(r"(?:percentage|cgpa|gpa)\s*[>=]+\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if pct_match:
        required_pct = float(pct_match.group(1))
        user_cgpa = profile.get("overall_cgpa")
        if user_cgpa is not None:
            user_pct = float(user_cgpa) if float(user_cgpa) <= 10 else float(user_cgpa)
            if user_pct < required_pct:
                eligible = False
                reasons.append(f"CGPA below minimum: {user_pct} < {required_pct}")

    backlog_match = re.search(r"(?:no\s+backlog|active\s+backlog|backlog\s*[=:]\s*(\d+))", text, re.IGNORECASE)
    if backlog_match:
        rule = backlog_match.group(0).lower()
        if "no backlog" in rule:
            active_backlogs = profile.get("active_backlogs", 0)
            if active_backlogs and int(active_backlogs) > 0:
                eligible = False
                reasons.append(f"Active backlogs: {active_backlogs}")

    return {
        "eligible": eligible,
        "reasons": reasons if reasons else ["All criteria met"],
        "checked": True,
    }
