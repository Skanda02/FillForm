from __future__ import annotations

from bson import ObjectId

from backend.services.profile_service import create_or_update_profile


def _make_submission(text: str) -> int:
    from database.models import save_submission

    submission_id = save_submission(
        source_type="text",
        filename=None,
        text=text,
        summary=None,
        sentence_count=0,
        keyword_count=0,
        keywords=[],
        deadline_candidates=[],
        has_deadline_signal=False,
        reminder_plan={},
    )
    return submission_id


def _make_profile(data: dict) -> str:
    profile = create_or_update_profile(data)
    return profile["id"]


def test_eligible_all_criteria_met():
    from backend.services.eligibility_service import check_eligibility

    text = "Branches: CSE\nDegree: B.E.\nCGPA >= 7.0\nNo backlog"
    submission_id = _make_submission(text)
    profile_id = _make_profile({
        "branch": "CSE",
        "degree": "B.E.",
        "graduation_year": 2024,
        "overall_cgpa": 8.5,
        "active_backlogs": 0,
    })

    result = check_eligibility(submission_id, profile_id)
    assert result["eligible"] is True
    assert result["checked"] is True


def test_branch_mismatch():
    from backend.services.eligibility_service import check_eligibility

    text = "Branches: ECE, ISE"
    submission_id = _make_submission(text)
    profile_id = _make_profile({"branch": "CSE"})

    result = check_eligibility(submission_id, profile_id)
    assert result["eligible"] is False
    assert any("Branch mismatch" in r for r in result["reasons"])


def test_degree_mismatch():
    from backend.services.eligibility_service import check_eligibility

    text = "Degree: B.Tech"
    submission_id = _make_submission(text)
    profile_id = _make_profile({"degree": "B.E."})

    result = check_eligibility(submission_id, profile_id)
    assert result["eligible"] is False
    assert any("Degree mismatch" in r for r in result["reasons"])


def test_cgpa_below_minimum():
    from backend.services.eligibility_service import check_eligibility

    text = "CGPA >= 9.0"
    submission_id = _make_submission(text)
    profile_id = _make_profile({"overall_cgpa": 7.5})

    result = check_eligibility(submission_id, profile_id)
    assert result["eligible"] is False
    assert any("CGPA below" in r for r in result["reasons"])


def test_active_backlogs():
    from backend.services.eligibility_service import check_eligibility

    text = "No backlog"
    submission_id = _make_submission(text)
    profile_id = _make_profile({"active_backlogs": 2})

    result = check_eligibility(submission_id, profile_id)
    assert result["eligible"] is False
    assert any("Active backlogs" in r for r in result["reasons"])


def test_submission_not_found():
    from backend.services.eligibility_service import check_eligibility

    result = check_eligibility(99999, str(ObjectId()))
    assert result["eligible"] is False
    assert result["checked"] is False
    assert "Submission not found" in result["reasons"]


def test_profile_not_found():
    from backend.services.eligibility_service import check_eligibility

    text = "Branches: CSE"
    submission_id = _make_submission(text)
    result = check_eligibility(submission_id, str(ObjectId()))
    assert result["eligible"] is False
    assert result["checked"] is False
    assert "Profile not found" in result["reasons"]
