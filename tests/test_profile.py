from __future__ import annotations

from backend.services.profile_service import (
    create_or_update_profile,
    delete_profile,
    get_default_profile,
    get_profile,
    list_profiles,
)


def test_create_profile():
    profile = create_or_update_profile({"name": "Alice", "email": "alice@test.com"})
    assert "id" in profile
    assert profile["name"] == "Alice"
    assert "created_at" in profile
    assert "updated_at" in profile


def test_get_profile():
    created = create_or_update_profile({"name": "Bob"})
    fetched = get_profile(created["id"])
    assert fetched is not None
    assert fetched["name"] == "Bob"


def test_get_profile_not_found():
    from bson import ObjectId

    assert get_profile(str(ObjectId())) is None


def test_update_profile():
    created = create_or_update_profile({"name": "Charlie"})
    updated = create_or_update_profile({"name": "Charlie Updated"}, profile_id=created["id"])
    assert updated["name"] == "Charlie Updated"


def test_delete_profile():
    created = create_or_update_profile({"name": "Dave"})
    assert delete_profile(created["id"]) is True
    assert get_profile(created["id"]) is None


def test_delete_profile_not_found():
    from bson import ObjectId

    assert delete_profile(str(ObjectId())) is False


def test_list_profiles():
    create_or_update_profile({"name": "Eve"})
    create_or_update_profile({"name": "Frank"})
    result = list_profiles()
    assert result["total"] == 2
    assert len(result["profiles"]) == 2


def test_get_default_profile():
    create_or_update_profile({"name": "First"})
    create_or_update_profile({"name": "Second"})
    default = get_default_profile()
    assert default is not None
    assert default["name"] == "Second"


def test_get_default_profile_empty():
    assert get_default_profile() is None
