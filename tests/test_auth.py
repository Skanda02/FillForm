from __future__ import annotations

from backend.services.auth_service import (
    create_profile_for_user,
    get_current_user,
    get_user_id_from_session,
    logout_user,
)


def test_get_user_id_from_session_returns_none_when_missing():
    assert get_user_id_from_session({}) is None


def test_get_user_id_from_session_returns_id():
    assert get_user_id_from_session({"user_id": "abc123"}) == "abc123"


def test_logout_user_clears_session():
    session = {"user_id": "abc", "other": "data"}
    logout_user(session)
    assert session == {}


class TestGetCurrentUser:
    def test_returns_none_for_invalid_id(self):
        assert get_current_user("invalid-id") is None

    def test_returns_user_when_found(self):
        from bson import ObjectId

        from backend.database import get_collection

        col = get_collection("users")
        oid = ObjectId()
        col.insert_one({"_id": oid, "email": "test@example.com"})

        result = get_current_user(str(oid))
        assert result is not None
        assert result["email"] == "test@example.com"
        assert result["id"] == str(oid)

    def test_includes_profile_when_linked(self):
        from bson import ObjectId

        from backend.database import get_collection

        users = get_collection("users")
        profiles = get_collection("profiles")

        oid = ObjectId()
        profile = profiles.insert_one({"name": "Test User"})
        users.insert_one({"_id": oid, "profile_id": profile.inserted_id})

        result = get_current_user(str(oid))
        assert result is not None
        assert result["profile"]["name"] == "Test User"


class TestCreateProfileForUser:
    def test_creates_and_links_profile(self):
        from bson import ObjectId

        from backend.database import get_collection

        users = get_collection("users")
        oid = ObjectId()
        users.insert_one({"_id": oid, "email": "test@example.com"})

        result = create_profile_for_user(str(oid), {"name": "New Profile"})
        assert result is not None

        user = users.find_one({"_id": oid})
        assert user.get("profile_id") is not None

    def test_returns_none_for_invalid_user(self):
        result = create_profile_for_user("invalid", {"name": "Test"})
        assert result is None
