from __future__ import annotations

from datetime import datetime, timezone

from bson import ObjectId

from backend.database import get_collection


def _serialize(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc


def create_or_update_profile(data: dict, profile_id: str | None = None) -> dict:
    col = get_collection("profiles")
    now = datetime.now(timezone.utc).isoformat()
    data["updated_at"] = now

    if profile_id:
        col.update_one({"_id": ObjectId(profile_id)}, {"$set": data}, upsert=True)
        return get_profile(profile_id)

    data["created_at"] = now
    result = col.insert_one(data)
    return get_profile(str(result.inserted_id))


def get_profile(profile_id: str) -> dict | None:
    col = get_collection("profiles")
    doc = col.find_one({"_id": ObjectId(profile_id)})
    return _serialize(doc)


def get_default_profile() -> dict | None:
    col = get_collection("profiles")
    doc = col.find_one(sort=[("created_at", -1)])
    return _serialize(doc)


def delete_profile(profile_id: str) -> bool:
    col = get_collection("profiles")
    result = col.delete_one({"_id": ObjectId(profile_id)})
    return result.deleted_count > 0


def list_profiles() -> list[dict]:
    col = get_collection("profiles")
    return [_serialize(doc) for doc in col.find(sort=[("created_at", -1)])]
