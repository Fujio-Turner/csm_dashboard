from __future__ import annotations

import json
import logging
import threading
from typing import Any

from .cblite import CBL

log = logging.getLogger(__name__)

COLLECTIONS = (
    "accounts",
    "people",
    "projects",
    "tickets",
    "emails",
    "threads",
    "slack_channels",
    "slack_messages",
    "teams_channels",
    "teams_messages",
    "salesforce_opportunities",
    "salesforce_cases",
    "calendar_events",
    "action_items",
    "drafts",
    "reports",
    "chats",
    "sync_jobs",
    "settings",
    "activities",
    "notes",
)

INDEXES = (
    ("accounts", "idx_acct_abbr", "abbr"),
    ("accounts", "idx_acct_slug", "slug"),
    ("accounts", "idx_acct_health", "health.score"),
    ("accounts", "idx_acct_status", "health.status"),
    ("accounts", "idx_acct_renewal", "contract.renewal_on"),
    ("people", "idx_person_account", "account_id"),
    ("people", "idx_person_email", "email"),
    ("people", "idx_person_kind", "kind"),
    ("projects", "idx_proj_account", "account_id"),
    ("projects", "idx_proj_status", "status"),
    ("tickets", "idx_tkt_account", "account_id"),
    ("tickets", "idx_tkt_status", "status"),
    ("tickets", "idx_tkt_pri", "priority"),
    ("tickets", "idx_tkt_updated", "updated_at"),
    ("tickets", "idx_tkt_key", "key"),
    ("tickets", "idx_tkt_acct_updated", "account_id, updated_at"),
    ("emails", "idx_em_account", "account_id"),
    ("emails", "idx_em_thread", "thread_id"),
    ("emails", "idx_em_sent", "sent_at"),
    ("emails", "idx_em_message_id", "message_id"),
    ("emails", "idx_em_acct_sent", "account_id, sent_at"),
    ("threads", "idx_thr_account", "account_id"),
    ("threads", "idx_thr_last", "last_at"),
    ("threads", "idx_thr_acct_last", "account_id, last_at"),
    ("slack_channels", "idx_slc_account", "account_id"),
    ("slack_messages", "idx_slm_account", "account_id"),
    ("slack_messages", "idx_slm_channel", "channel_id"),
    ("slack_messages", "idx_slm_ts", "ts"),
    ("slack_messages", "idx_slm_chan_ts", "channel_id, ts"),
    ("teams_channels", "idx_tmc_account", "account_id"),
    ("teams_messages", "idx_tmm_account", "account_id"),
    ("teams_messages", "idx_tmm_channel", "channel_id"),
    ("teams_messages", "idx_tmm_ts", "ts"),
    ("teams_messages", "idx_tmm_chan_ts", "channel_id, ts"),
    ("salesforce_opportunities", "idx_sfo_account", "account_id"),
    ("salesforce_opportunities", "idx_sfo_stage", "stage"),
    ("salesforce_opportunities", "idx_sfo_close", "close_on"),
    ("salesforce_cases", "idx_sfc_account", "account_id"),
    ("salesforce_cases", "idx_sfc_status", "status"),
    ("salesforce_cases", "idx_sfc_number", "case_number"),
    ("calendar_events", "idx_cal_account", "account_id"),
    ("calendar_events", "idx_cal_start", "start_at"),
    ("calendar_events", "idx_cal_acct_start", "account_id, start_at"),
    ("action_items", "idx_ai_account", "account_id"),
    ("action_items", "idx_ai_due", "due_on"),
    ("action_items", "idx_ai_status", "status"),
    ("action_items", "idx_ai_acct_due", "account_id, due_on"),
    ("drafts", "idx_draft_account", "account_id"),
    ("drafts", "idx_draft_status", "status"),
    ("reports", "idx_rpt_account", "account_id"),
    ("chats", "idx_chat_account", "account_id"),
    ("sync_jobs", "idx_job_conn", "connector"),
    ("sync_jobs", "idx_job_status", "status"),
    ("activities", "idx_act_account", "account_id"),
    ("activities", "idx_act_at", "at"),
    ("activities", "idx_act_kind", "kind"),
    ("activities", "idx_act_acct_at", "account_id, at"),
    ("activities", "idx_act_source_ref", "source_ref"),
    ("notes", "idx_note_account", "account_id"),
)

FTS_INDEXES = (
    ("accounts", "idx_fts_acct", "name, abbr", "name, abbr"),
    ("tickets", "idx_fts_tkt", "key, summary, status_raw", "key, summary"),
    ("emails", "idx_fts_em", "subject, from_addr, snippet", "subject, from_addr"),
    ("people", "idx_fts_person", "name, email, title", "name, email"),
)


def _unwrap_row(row: dict, collection: str) -> dict:
    """Flatten CBL SELECT * rows.

    ``FROM activities`` → ``{activities: {...}, _id}``.
    ``FROM activities AS a`` → ``{a: {...}, _id}``.
    """
    if collection in row and isinstance(row[collection], dict):
        doc = dict(row[collection])
        if row.get("_id"):
            doc["_id"] = row["_id"]
        return doc
    nested = [k for k, v in row.items() if k != "_id" and isinstance(v, dict)]
    if len(nested) == 1:
        doc = dict(row[nested[0]])
        if row.get("_id"):
            doc["_id"] = row["_id"]
        return doc
    return row


def _clamp(n: int | None, default: int, lo: int = 0, hi: int = 500) -> int:
    if n is None:
        return default
    try:
        v = int(n)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


class CBLStore:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.RLock()
        self._cbl = CBL(db_path)
        self._cols: dict[str, Any] = {}
        self.ensure_collections(list(COLLECTIONS))
        self._create_indexes()

    @property
    def edition(self) -> str:
        return "community"

    def ensure_collections(self, names: list[str]) -> None:
        with self._lock:
            for name in names:
                self._cols[name] = self._cbl.get_or_create_collection(name)

    def _create_indexes(self) -> None:
        with self._lock:
            for collection, index_name, expr in INDEXES:
                col = self._cols[collection]
                self._cbl.create_value_index(col, index_name, expr)
            for collection, index_name, expr, fallback in FTS_INDEXES:
                col = self._cols[collection]
                try:
                    self._cbl.create_full_text_index(col, index_name, expr)
                except Exception as exc:
                    log.warning("csm.index.fts_failed index=%s err=%s", index_name, exc)
                    try:
                        self._cbl.create_full_text_index(col, index_name, fallback)
                    except Exception as exc2:
                        log.warning("csm.index.fts_failed index=%s fallback err=%s", index_name, exc2)

    def save(self, collection: str, doc_id: str, doc: dict) -> None:
        clean = {k: v for k, v in doc.items() if k != "_id" and k != "_created"}
        payload = json.dumps(clean, default=str)
        with self._lock:
            col = self._cols[collection]
            self._cbl.save_document_json(col, doc_id, payload)

    def get(self, collection: str, doc_id: str) -> dict | None:
        with self._lock:
            col = self._cols[collection]
            raw = self._cbl.get_document_json(col, doc_id)
        if raw is None:
            return None
        return json.loads(raw)

    def purge(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._cbl.purge_document(self._cols[collection], doc_id)

    def count(self, collection: str) -> int:
        with self._lock:
            return self._cbl.collection_count(self._cols[collection])

    def query_all(self, collection: str) -> list[dict]:
        sql = f"SELECT META().id AS _id, * FROM {collection}"
        with self._lock:
            rows = self._cbl.execute_query(sql)
        return [_unwrap_row(row, collection) for row in rows]

    def query_by_account(self, collection: str, account_id: str) -> list[dict]:
        sql = f"SELECT META().id AS _id, * FROM {collection} WHERE account_id = $aid"
        try:
            rows = self.query(sql, {"aid": account_id})
            return [_unwrap_row(row, collection) for row in rows]
        except Exception as exc:
            log.warning("csm.query.by_account_failed collection=%s err=%s", collection, exc)
            return [r for r in self.query_all(collection) if r.get("account_id") == account_id]

    def query_eq(self, collection: str, field: str, value: object) -> list[dict]:
        if field not in {"abbr", "slug", "account_id", "kind", "status"}:
            return [r for r in self.query_all(collection) if r.get(field) == value]
        sql = f"SELECT META().id AS _id, * FROM {collection} WHERE {field} = $v"
        try:
            rows = self.query(sql, {"v": value})
            return [_unwrap_row(row, collection) for row in rows]
        except Exception as exc:
            log.warning("csm.query.eq_failed collection=%s field=%s err=%s", collection, field, exc)
            return [r for r in self.query_all(collection) if r.get(field) == value]

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        params_json = json.dumps(params) if params else None
        with self._lock:
            return self._cbl.execute_query(sql, params_json)

    def page_timeline(
        self,
        account_id: str,
        *,
        since: str | None = None,
        kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        lim = _clamp(limit, 50)
        off = _clamp(offset, 0, hi=100_000)
        where = ["a.account_id = $aid"]
        params: dict[str, Any] = {"aid": account_id}
        if since:
            where.append("a.at >= $since")
            params["since"] = since
        if kind:
            where.append("a.kind = $kind")
            params["kind"] = kind
        sql = (
            f"SELECT META().id AS _id, * FROM activities AS a "
            f"WHERE {' AND '.join(where)} ORDER BY a.at DESC LIMIT {lim} OFFSET {off}"
        )
        rows = self.query(sql, params)
        return [_unwrap_row(row, "activities") for row in rows]

    def close(self) -> None:
        with self._lock:
            if hasattr(self._cbl, "close"):
                self._cbl.close()
