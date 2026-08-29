from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from typing import Any

from .paging import omit_fields, row_matches, sort_rows


class MemoryStore:
    """In-process document store used by unit tests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, dict[str, Any]]] = {}

    def ensure_collections(self, names: list[str]) -> None:
        with self._lock:
            for name in names:
                self._data.setdefault(name, {})

    def save(self, collection: str, doc_id: str, doc: dict) -> None:
        with self._lock:
            self._data.setdefault(collection, {})[doc_id] = copy.deepcopy(doc)

    def get(self, collection: str, doc_id: str) -> dict | None:
        with self._lock:
            doc = self._data.get(collection, {}).get(doc_id)
            if doc is None:
                return None
            return copy.deepcopy(doc)

    def purge(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._data.get(collection, {}).pop(doc_id, None)

    def list_all(self, collection: str) -> list[dict]:
        with self._lock:
            out = []
            for doc_id, doc in self._data.get(collection, {}).items():
                item = copy.deepcopy(doc)
                item["_id"] = doc_id
                out.append(item)
            return out

    def count(self, collection: str) -> int:
        with self._lock:
            return len(self._data.get(collection, {}))

    def query_all(self, collection: str) -> list[dict]:
        return self.list_all(collection)

    def query_by_account(self, collection: str, account_id: str) -> list[dict]:
        return [r for r in self.list_all(collection) if r.get("account_id") == account_id]

    def query_eq(self, collection: str, field: str, value: object) -> list[dict]:
        return [r for r in self.list_all(collection) if r.get(field) == value]

    def count_account(self, collection: str, account_id: str, *, filters: dict | None = None) -> int:
        return sum(
            1
            for row in self.query_by_account(collection, account_id)
            if row_matches(row, filters)
        )

    def page_account(
        self,
        collection: str,
        account_id: str,
        *,
        order: str = "updated_at",
        desc: bool = True,
        limit: int = 50,
        offset: int = 0,
        filters: dict | None = None,
        omit: tuple[str, ...] | list[str] | None = None,
        fields: tuple[str, ...] | list[str] | None = None,
    ) -> tuple[list[dict], int]:
        rows = [r for r in self.query_by_account(collection, account_id) if row_matches(r, filters)]
        sort_rows(rows, order, desc=desc)
        total = len(rows)
        lim = max(0, int(limit))
        off = max(0, int(offset))
        sliced = rows[off : off + lim] if lim else rows[off:]
        if fields:
            keep = set(fields) | {"_id"}
            sliced = [{k: v for k, v in row.items() if k in keep} for row in sliced]
        elif omit:
            sliced = [omit_fields(row, omit) for row in sliced]
        return sliced, total

    def close(self) -> None:
        return None
