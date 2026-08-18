from __future__ import annotations


def merge_operator(existing: dict | None, incoming: dict, first_party_path: str = "operator") -> dict:
    """Connector overwrites identity; first-party operator.* survives."""
    out = dict(incoming)
    if not existing:
        return out
    held = existing.get(first_party_path)
    if held is not None:
        out[first_party_path] = held
    return out


def merge_account_connectors(existing: dict, incoming: dict) -> dict:
    out = dict(existing)
    src = dict(out.get("sources") or {})
    src.update(incoming.get("sources") or {})
    out["sources"] = src
    return out
