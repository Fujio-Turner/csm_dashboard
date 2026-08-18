from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _domain(addr: str) -> str:
    if "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[-1].lower().strip()


def route_event(accounts: list[dict], event: dict, *, operator_domains: set[str] | None = None) -> str:
    """Return account_id or empty string if none / ambiguous."""
    hint = event.get("account_hint") or {}
    payload = event.get("payload") or {}
    explicit = str(payload.get("account_id") or event.get("account_id") or "").strip()
    if explicit:
        return explicit

    kind = str(event.get("kind") or "")
    candidates: list[str] = []
    ours = {d.lower().lstrip("@") for d in (operator_domains or set()) if d}

    if kind == "ticket":
        key = str(payload.get("project_key") or hint.get("project_keys", [None])[0] or "")
        keys = set(hint.get("project_keys") or [])
        if key:
            keys.add(key)
        for acct in accounts:
            configured = set((acct.get("connectors") or {}).get("jira", {}).get("project_keys") or [])
            if keys & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    if kind == "email":
        addrs = [payload.get("from_addr") or ""]
        addrs.extend(payload.get("to_addrs") or [])
        addrs.extend(payload.get("cc_addrs") or [])
        addrs.extend(hint.get("domains") or [])
        domains = {_domain(a) if "@" in str(a) else str(a).lower().lstrip("@") for a in addrs if a}
        domains -= ours
        domains.discard("")
        for acct in accounts:
            if acct.get("removed"):
                continue
            configured = {str(d).lower().lstrip("@") for d in (acct.get("domains") or [])}
            if domains & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    if kind in {"slack_message", "slack_channel"}:
        chans = set(hint.get("channel_ids") or [])
        if payload.get("channel_id"):
            chans.add(payload["channel_id"])
        for acct in accounts:
            configured = set((acct.get("connectors") or {}).get("slack", {}).get("channel_ids") or [])
            if chans & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    if kind in {"teams_message", "teams_channel"}:
        chans = set(hint.get("channel_ids") or [])
        if payload.get("channel_id"):
            chans.add(payload["channel_id"])
        for acct in accounts:
            configured = set((acct.get("connectors") or {}).get("teams", {}).get("channel_ids") or [])
            if chans & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    if kind in {"salesforce_opportunity", "salesforce_case"}:
        ids = set(hint.get("sf_account_ids") or [])
        if payload.get("sf_account_id"):
            ids.add(payload["sf_account_id"])
        if payload.get("account_id"):
            ids.add(payload["account_id"])
        for acct in accounts:
            configured = set((acct.get("connectors") or {}).get("salesforce", {}).get("account_ids") or [])
            configured.add(acct.get("account_id") or acct.get("_id") or "")
            if ids & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    if kind == "calendar_event":
        attendee_domains = set()
        for row in payload.get("attendees") or []:
            attendee_domains.add(_domain(str((row or {}).get("email") or "")))
        attendee_domains.update(d.lower() for d in (hint.get("domains") or []) if d)
        attendee_domains.discard("")
        for acct in accounts:
            cal = (acct.get("connectors") or {}).get("calendar") or {}
            configured = {d.lower() for d in (cal.get("attendee_domains") or acct.get("domains") or [])}
            if attendee_domains & configured:
                candidates.append(acct.get("account_id") or acct.get("_id") or "")

    uniq = [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]
    if len(uniq) == 1:
        return uniq[0]
    if len(uniq) > 1:
        log.warning("csm.route.ambiguous kind=%s candidates=%s", kind, ",".join(uniq))
        return ""
    return ""
