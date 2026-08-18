from csm_dashboard.storage.cbl_store import _unwrap_row
from csm_dashboard.storage.repo import ts_to_iso


def test_unwrap_collection_key():
    row = {"_id": "act:1", "activities": {"kind": "email_in", "title": "Hi"}}
    doc = _unwrap_row(row, "activities")
    assert doc["_id"] == "act:1"
    assert doc["kind"] == "email_in"


def test_unwrap_alias_a():
    row = {"_id": "act:2", "a": {"kind": "meeting", "title": "Scan"}}
    doc = _unwrap_row(row, "activities")
    assert doc["_id"] == "act:2"
    assert doc["kind"] == "meeting"
    assert doc["title"] == "Scan"


def test_ts_to_iso_unix():
    assert ts_to_iso("1723900000.000100").startswith("2024-08-17")
    assert ts_to_iso("2026-08-17T13:20:00Z") == "2026-08-17T13:20:00Z"
