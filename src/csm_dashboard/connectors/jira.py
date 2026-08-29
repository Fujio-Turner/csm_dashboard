"""Jira Cloud / Data Center read-only pull (email + API token)."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from csm_dashboard.connectors.base import NormalizedEvent
from csm_dashboard.connectors.http import HttpError, json_get, json_post
from csm_dashboard.connectors.live import LiveConnector, jira_day
from csm_dashboard.storage.repo import utcnow

log = logging.getLogger(__name__)

JIRA_FIELDS = [
    "summary",
    "status",
    "priority",
    "issuetype",
    "assignee",
    "reporter",
    "labels",
    "created",
    "updated",
    "resolutiondate",
    "comment",
    "project",
]

STATUS_BY_NAME = {
    "open": "open",
    "to do": "open",
    "todo": "open",
    "backlog": "open",
    "new": "open",
    "in progress": "in_progress",
    "in development": "in_progress",
    "developing": "in_progress",
    "waiting": "waiting",
    "pending": "waiting",
    "blocked": "waiting",
    "on hold": "waiting",
    "done": "done",
    "resolved": "done",
    "closed": "done",
    "complete": "done",
    "completed": "done",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "won't do": "cancelled",
    "won't fix": "cancelled",
}

STATUS_BY_CATEGORY = {
    "new": "open",
    "indeterminate": "in_progress",
    "done": "done",
}

PRIORITY_BY_NAME = {
    "highest": "p1",
    "blocker": "p1",
    "high": "p2",
    "medium": "p3",
    "low": "p4",
    "lowest": "p4",
}


def adf_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return " ".join(part for part in (adf_text(item) for item in node) if part)
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text") or "")
        return adf_text(node.get("content"))
    return ""


def jira_time(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.replace("+0000", "Z").replace("+00:00", "Z")
    if text.endswith("Z") and len(text) >= 19:
        return text[:19] + "Z"
    if "T" in text:
        return text[:19] + "Z"
    return text


def map_status(fields: dict) -> tuple[str, str]:
    status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
    raw = str(status.get("name") or "Open")
    category = str(((status.get("statusCategory") or {}) if isinstance(status.get("statusCategory"), dict) else {}).get("key") or "")
    mapped = STATUS_BY_NAME.get(raw.lower().strip()) or STATUS_BY_CATEGORY.get(category.lower()) or "open"
    return mapped, raw


def map_priority(fields: dict) -> tuple[str, str]:
    priority = fields.get("priority") if isinstance(fields.get("priority"), dict) else {}
    raw = str(priority.get("name") or "Medium")
    return PRIORITY_BY_NAME.get(raw.lower().strip()) or "p3", raw


def person_email(user: dict | None) -> str:
    if not isinstance(user, dict):
        return ""
    return str(user.get("emailAddress") or user.get("displayName") or "").strip()


def map_comments(fields: dict) -> tuple[list[dict], int, str]:
    blob = fields.get("comment") if isinstance(fields.get("comment"), dict) else {}
    rows = blob.get("comments") if isinstance(blob.get("comments"), list) else []
    total = int(blob.get("total") or len(rows) or 0)
    out: list[dict] = []
    last = ""
    for row in rows[-10:]:
        if not isinstance(row, dict):
            continue
        text = adf_text(row.get("body"))[:2000]
        at = jira_time(str(row.get("created") or ""))
        author = person_email(row.get("author") if isinstance(row.get("author"), dict) else {})
        out.append({"at": at, "author": author, "text": text})
        if at:
            last = at
    return out, total, last


def map_issue(issue: dict, *, base_url: str) -> dict:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    key = str(issue.get("key") or "")
    project = fields.get("project") if isinstance(fields.get("project"), dict) else {}
    project_key = str(project.get("key") or (key.split("-", 1)[0] if "-" in key else ""))
    status, status_raw = map_status(fields)
    priority, priority_raw = map_priority(fields)
    comments, comment_count, last_comment_at = map_comments(fields)
    itype = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    created = jira_time(str(fields.get("created") or ""))
    updated = jira_time(str(fields.get("updated") or created))
    resolved = jira_time(str(fields.get("resolutiondate") or ""))
    labels = [str(item) for item in (fields.get("labels") or []) if item]
    root = str(base_url).rstrip("/")
    return {
        "type": "ticket",
        "source": "jira",
        "key": key,
        "external_id": str(issue.get("id") or ""),
        "summary": str(fields.get("summary") or ""),
        "status": status,
        "status_raw": status_raw,
        "priority": priority,
        "priority_raw": priority_raw,
        "issue_type": str(itype.get("name") or "").lower(),
        "assignee_email": person_email(fields.get("assignee") if isinstance(fields.get("assignee"), dict) else None),
        "reporter_email": person_email(fields.get("reporter") if isinstance(fields.get("reporter"), dict) else None),
        "url": f"{root}/browse/{key}" if key else "",
        "project_key": project_key,
        "labels": labels,
        "created_at": created,
        "updated_at": updated,
        "resolved_at": resolved,
        "comment_count": comment_count,
        "last_comment_at": last_comment_at,
        "comments": comments,
        "sources": {"jira": {"fetched_at": utcnow()}},
    }


def build_jql(*, keys: list[str], custom: str = "", since: str | None = None) -> str:
    parts: list[str] = []
    custom_jql = str(custom or "").strip()
    if custom_jql:
        parts.append(f"({custom_jql})")
    elif keys:
        joined = ", ".join(keys)
        parts.append(f"project in ({joined})")
    else:
        parts.append("(assignee = currentUser() OR reporter = currentUser())")
    day = jira_day(since)
    if day:
        parts.append(f'updated >= "{day}"')
    return " AND ".join(parts) + " ORDER BY updated DESC"


def project_keys(accounts: list[dict]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for acct in accounts:
        for key in ((acct.get("connectors") or {}).get("jira") or {}).get("project_keys") or []:
            value = str(key or "").strip()
            if value and value not in seen:
                seen.add(value)
                keys.append(value)
    return keys


class JiraConnector(LiveConnector):
    name = "jira"

    def ready(self) -> bool:
        secret = self.secret()
        return bool(
            str(secret.get("base_url") or "").strip()
            and str(secret.get("email") or "").strip()
            and str(secret.get("api_token") or "").strip()
        )

    def _auth(self) -> tuple[str, str, str]:
        secret = self.secret()
        base = str(secret.get("base_url") or "").strip().rstrip("/")
        email = str(secret.get("email") or "").strip()
        token = str(secret.get("api_token") or "").strip()
        if not (base and email and token):
            raise RuntimeError("not_connected")
        return base, email, token

    def probe(self) -> dict:
        health = self.health()
        if not health.get("ok"):
            return health
        base, email, token = self._auth()
        try:
            json_get(urljoin(base + "/", "rest/api/3/myself"), auth=(email, token))
            health["message"] = "ok"
            health["last_ok_at"] = utcnow()
        except HttpError as exc:
            health["ok"] = False
            health["message"] = str(exc)
            log.info("csm.connector.probe name=jira ok=false err=%s", exc)
        return health

    def _search(self, base: str, email: str, token: str, jql: str) -> list[dict]:
        issues: list[dict] = []
        token_page = ""
        start_at = 0
        use_legacy = False
        while len(issues) < 100:
            try:
                if use_legacy:
                    payload = json_get(
                        urljoin(base + "/", "rest/api/3/search"),
                        params={
                            "jql": jql,
                            "startAt": start_at,
                            "maxResults": 50,
                            "fields": ",".join(JIRA_FIELDS),
                        },
                        auth=(email, token),
                    )
                else:
                    body = {"jql": jql, "maxResults": 50, "fields": JIRA_FIELDS}
                    if token_page:
                        body["nextPageToken"] = token_page
                    payload = json_post(
                        urljoin(base + "/", "rest/api/3/search/jql"),
                        json=body,
                        auth=(email, token),
                    )
            except HttpError as exc:
                if not use_legacy and exc.status in {404, 410}:
                    use_legacy = True
                    continue
                raise
            if not isinstance(payload, dict):
                break
            batch = payload.get("issues") if isinstance(payload.get("issues"), list) else []
            issues.extend(row for row in batch if isinstance(row, dict))
            if use_legacy:
                start_at += len(batch)
                total = int(payload.get("total") or 0)
                if start_at >= total or not batch:
                    break
            else:
                token_page = str(payload.get("nextPageToken") or "")
                if payload.get("isLast") or not token_page or not batch:
                    break
        return issues[:100]

    def pull(self, since: str | None, account: dict | None) -> list[NormalizedEvent]:
        if not self.ready():
            raise RuntimeError("not_connected")
        base, email, token = self._auth()
        accounts = self.account_rows(account)
        keys = project_keys(accounts)
        custom = ""
        if account:
            custom = str(((account.get("connectors") or {}).get("jira") or {}).get("jql") or "")
        jql = build_jql(keys=keys, custom=custom, since=since)
        log.info("csm.connector.pull name=jira keys=%s", len(keys))
        events: list[NormalizedEvent] = []
        for issue in self._search(base, email, token, jql):
            payload = map_issue(issue, base_url=base)
            events.append(
                NormalizedEvent(
                    connector="jira",
                    kind="ticket",
                    external_id=payload.get("key") or "",
                    occurred_at=payload.get("updated_at") or utcnow(),
                    account_hint={"project_keys": [payload.get("project_key")] if payload.get("project_key") else []},
                    payload=payload,
                )
            )
        return events


def connector(repo=None) -> JiraConnector:
    return JiraConnector(repo)
