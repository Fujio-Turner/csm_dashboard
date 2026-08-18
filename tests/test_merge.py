from __future__ import annotations

from csm_dashboard.ingest.merge import merge_operator


def test_operator_survives():
    existing = {"summary": "old", "operator": {"triage": "hot", "ignore": False}}
    incoming = {"summary": "new", "operator": {"triage": "", "ignore": True}}
    out = merge_operator(existing, incoming)
    assert out["summary"] == "new"
    assert out["operator"]["triage"] == "hot"
