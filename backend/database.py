from __future__ import annotations

import os
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        _client = MongoClient(uri)
        _db = _client["fillform"]
    return _db


def get_collection(name: str) -> Collection:
    return get_db()[name]
