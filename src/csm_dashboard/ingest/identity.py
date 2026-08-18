from __future__ import annotations

import hashlib
import re


def _sha(text: str, n: int) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def email_doc_id(doc: dict) -> str:
    mid = str(doc.get("message_id") or "").strip()
    if mid:
        return f"em:{_sha(mid, 20)}"
    key = "|".join(
        [
            str(doc.get("from_addr") or ""),
            str(doc.get("sent_at") or ""),
            str(doc.get("subject") or ""),
            str(doc.get("body_bytes") or 0),
        ]
    )
    return f"em:{_sha(key, 20)}"


def _strip_subject(subject: str) -> str:
    s = (subject or "").strip().lower()
    while True:
        nxt = re.sub(r"^(re|fw|fwd)\s*(\[\d+\])?\s*:\s*", "", s)
        if nxt == s:
            return s
        s = nxt


def thread_doc_id(doc: dict) -> str:
    refs = str(doc.get("references") or "").strip()
    if refs:
        root = refs.split()[0]
        return f"thr:{_sha(root, 16)}"
    reply = str(doc.get("in_reply_to") or "").strip()
    if reply:
        return f"thr:{_sha(reply, 16)}"
    mid = str(doc.get("message_id") or "").strip()
    if mid:
        return f"thr:{_sha(mid, 16)}"
    parts = {str(doc.get("from_addr") or "").lower()}
    for addr in list(doc.get("to_addrs") or []) + list(doc.get("cc_addrs") or []):
        parts.add(str(addr).lower())
    key = _strip_subject(str(doc.get("subject") or "")) + "|" + ",".join(sorted(p for p in parts if p))
    return f"thr:{_sha(key, 16)}"


def activity_doc_id(source_ref: str) -> str:
    return f"act:{_sha(source_ref, 16)}"
