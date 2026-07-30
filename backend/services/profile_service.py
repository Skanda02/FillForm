from __future__ import annotations

import logging
from datetime import UTC, datetime

from bson import ObjectId
from bson.errors import InvalidId

from backend.database import get_collection

log = logging.getLogger(__name__)

ALLOWED_PROFILE_FIELDS = frozenset(
    {
        "name",
        "email",
        "phone",
        "degree",
        "branch",
        "batch",
        "percentage",
        "backlog_rule",
    }
)


def _serialize(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def _safe_object_id(id_str: str) -> ObjectId | None:
    try:
        return ObjectId(id_str)
    except InvalidId:
        return None


def create_or_update_profile(data: dict, profile_id: str | None = None) -> dict:
    col = get_collection("profiles")
    now = datetime.now(UTC).isoformat()
    safe_data = {k: v for k, v in data.items() if k in ALLOWED_PROFILE_FIELDS}
    safe_data["updated_at"] = now

    if profile_id:
        oid = _safe_object_id(profile_id)
        if not oid:
            raise ValueError(f"Invalid profile_id: {profile_id}")
        col.update_one({"_id": oid}, {"$set": safe_data}, upsert=True)
        return get_profile(profile_id)

    safe_data["created_at"] = now
    result = col.insert_one(safe_data)
    return get_profile(str(result.inserted_id))


def get_profile(profile_id: str) -> dict | None:
    oid = _safe_object_id(profile_id)
    if not oid:
        return None
    col = get_collection("profiles")
    doc = col.find_one({"_id": oid})
    return _serialize(doc)


def get_default_profile() -> dict | None:
    col = get_collection("profiles")
    doc = col.find_one(sort=[("created_at", -1)])
    return _serialize(doc)


def delete_profile(profile_id: str) -> bool:
    oid = _safe_object_id(profile_id)
    if not oid:
        return False
    col = get_collection("profiles")
    result = col.delete_one({"_id": oid})
    return result.deleted_count > 0


def list_profiles() -> list[dict]:
    col = get_collection("profiles")
    return [_serialize(doc) for doc in col.find(sort=[("created_at", -1)])]
