from __future__ import annotations

import os

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

_client: MongoClient | None = None
_db: Database | None = None


def get_db() -> Database:
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        kwargs: dict = {
            "connectTimeoutMS": 5000,
            "serverSelectionTimeoutMS": 5000,
            "socketTimeoutMS": 30000,
        }
        if uri.startswith("mongodb+srv://"):
            kwargs["tls"] = True
            kwargs["tlsAllowInvalidCertificates"] = False
        _client = MongoClient(uri, **kwargs)
        _db = _client["fillform"]
    return _db


def get_collection(name: str) -> Collection:
    return get_db()[name]
