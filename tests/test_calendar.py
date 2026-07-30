from __future__ import annotations

from bson import ObjectId

from backend.database import get_collection
from backend.services.calendar_service import is_connected


def test_is_connected_returns_false_when_no_tokens():
    result = is_connected(str(ObjectId()))
    assert result is False


def test_is_connected_returns_true_when_tokens_exist():
    oid = ObjectId()
    get_collection("calendar_tokens").insert_one({"profile_id": str(oid)})
    result = is_connected(str(oid))
    assert result is True
