from __future__ import annotations

import os
from unittest.mock import patch

from backend.mongo import get_collection, get_db


def test_get_db_returns_singleton():
    db1 = get_db()
    db2 = get_db()
    assert db1 is db2


def test_get_collection_returns_collection():
    col = get_collection("test")
    assert col.name == "test"


def test_get_db_uses_env_uri():
    with patch.dict(os.environ, {"MONGO_URI": "mongodb://localhost:27017"}, clear=True):
        db = get_db()
        assert db is not None
