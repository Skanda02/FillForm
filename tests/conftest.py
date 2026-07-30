from __future__ import annotations

import mongomock
import pytest


@pytest.fixture(autouse=True)
def _mock_mongodb(monkeypatch):
    client = mongomock.MongoClient()
    db = client["fillform_test"]

    import backend.mongo as db_mod

    monkeypatch.setattr(db_mod, "_client", client)
    monkeypatch.setattr(db_mod, "_db", db)

    yield db

    client.close()


@pytest.fixture()
def app():
    from backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    application.config["RATELIMIT_ENABLED"] = False
    application.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_profile_data():
    return {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "1234567890",
        "college": "ABC College",
        "usn": "1AB20CS001",
        "branch": "CSE",
        "degree": "B.E.",
        "graduation_year": 2026,
        "overall_cgpa": 8.5,
        "active_backlogs": 0,
        "skills": ["Python", "JavaScript"],
    }


@pytest.fixture()
def sample_submission_text():
    return (
        "Company: TechCorp\n"
        "Role: Software Engineer\n"
        "Branches: CSE, ISE\n"
        "Degree: B.E.\n"
        "Batch: 2024\n"
        "CGPA >= 7.5\n"
        "No backlog\n"
        "Deadline: 2026-08-15\n"
        "Apply at: https://example.com/apply"
    )
