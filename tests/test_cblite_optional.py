from __future__ import annotations

from csm_dashboard.storage.errors import CouchbaseLiteNotAvailable
from csm_dashboard.storage.repo import open_store


def test_memory_store_open():
    store = open_store(memory=True)
    store.save("accounts", "acct:x", {"type": "account"})
    assert store.get("accounts", "acct:x")["type"] == "account"


def test_cblite_missing_is_typed():
    assert issubclass(CouchbaseLiteNotAvailable, Exception)
