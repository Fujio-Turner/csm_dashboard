"""Mine customer people from mail, meetings, tickets, Slack, and Teams.

De-dupes by email. Turns ``Last, First`` headers and ``first.last@domain``
locals into a display name. Never auto-creates a person — callers tick who to add.
"""

from __future__ import annotations

import logging
import re
from email.utils import getaddresses

log = logging.getLogger(__name__)

SKIP_LOCALS = frozenset(
    {
        "noreply",
        "no-reply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "mailer-daemon",
        "mailerdaemon",
        "postmaster",
        "notifications",
        "notification",
        "notify",
        "bounce",
        "bounces",
        "calendar-notification",
        "calendarnotification",
    }
)
ND_TAIL = re.compile(r"[\s._-]+nd$", re.I)
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}")
SOURCE_RANK = ("email", "calendar", "ticket", "slack", "teams")
LAST_PARTICLES = frozenset({"van", "von", "de", "da", "del", "di", "la", "le", "st", "der", "den"})


def clean_email(raw: str) -> str:
    return str(raw or "").strip().lower()


def domain_of(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[-1].strip().lower()


def skip_local(local: str) -> bool:
    token = str(local or "").split("+", 1)[0].strip().lower()
    return token in SKIP_LOCALS


def skip_email(email: str, *, operator_email: str = "", operator_domains: set[str] | None = None) -> bool:
    addr = clean_email(email)
    if "@" not in addr:
        return True
    local, domain = addr.split("@", 1)
    if skip_local(local):
        return True
    me = clean_email(operator_email)
    if me and addr == me:
        return True
    ours = {str(d).lower().lstrip("@") for d in (operator_domains or set()) if d}
    if domain in ours:
        return True
    return False


def title_case_name(raw: str) -> str:
    bits: list[str] = []
    for part in re.split(r"[.\s_]+", str(raw or "").strip()):
        token = ND_TAIL.sub("", part).strip(" .-_")
        if not token or token.lower() == "nd":
            continue
        if len(token) == 1:
            bits.append(token.upper())
        else:
            bits.append(token[:1].upper() + token[1:])
    return " ".join(bits)


def name_from_local(local: str) -> str:
    text = ND_TAIL.sub("", str(local or "").split("+", 1)[0])
    text = text.replace("-nd", "").replace("_nd", "")
    return title_case_name(text.replace(".", " ").replace("_", " ").replace("-", " "))


def parse_display_name(raw: str) -> dict[str, str]:
    """Split a From / attendee display name into name, title, group."""
    text = re.sub(r"\s+", " ", str(raw or "").strip().strip("\"'"))
    text = re.sub(r"\s+-nd\b", "", text, flags=re.I).strip()
    empty = {"name": "", "title": "", "group": ""}
    if not text or "@" in text:
        return empty
    if " | " in text:
        left, right = text.split(" | ", 1)
        return {"name": title_case_name(left) or left.strip(), "title": right.strip(), "group": ""}
    if "," in text:
        parts = [p.strip() for p in text.split(",") if p.strip()]
        left = parts[0]
        rest = parts[1:]
        left_words = left.split()
        first = rest[0] if rest else ""
        extra = rest[1:]
        first_words = first.split()
        last_style = bool(left_words) and (
            len(left_words) == 1
            or (len(left_words) == 2 and left_words[0].lower().strip(".") in LAST_PARTICLES)
        )
        if last_style and first_words and len(first_words) <= 3:
            name = title_case_name(first + " " + left)
            title = extra[0] if extra else ""
            group = extra[1] if len(extra) > 1 else ""
            return {"name": name or first, "title": title, "group": group}
        return {
            "name": title_case_name(left) or left,
            "title": rest[0] if rest else "",
            "group": rest[1] if len(rest) > 1 else "",
        }
    if " - " in text:
        left, right = text.split(" - ", 1)
        if 0 < len(right.split()) <= 4:
            return {"name": title_case_name(left) or left.strip(), "title": right.strip(), "group": ""}
    return {"name": title_case_name(text) or text, "title": "", "group": ""}


def parse_named_addrs(raw: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for name, addr in getaddresses([str(raw or "")]):
        email = clean_email(addr)
        if email and "@" in email:
            out.append((str(name or "").strip(), email))
    return out


def pick_phone(text: str) -> str:
    blob = str(text or "")
    for match in PHONE_RE.finditer(blob):
        digits = re.sub(r"\D", "", match.group(0))
        if 10 <= len(digits) <= 15:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def name_quality(name: str) -> int:
    text = str(name or "").strip()
    if not text:
        return 0
    if "@" in text:
        return 1
    words = [w for w in re.split(r"\s+", text) if w]
    return min(10, len(words) + (2 if "," not in text else 0))


def _blank_row(email: str) -> dict:
    return {
        "email": email,
        "name": "",
        "title": "",
        "group": "",
        "phone": "",
        "job_description": "",
        "sources": [],
        "hits": 0,
        "existing_id": "",
    }


def _add_source(row: dict, source: str) -> None:
    if source and source not in row["sources"]:
        row["sources"].append(source)


def _merge(row: dict, *, name: str = "", title: str = "", group: str = "", phone: str = "", job: str = "", source: str = "") -> None:
    incoming = str(name or "").strip()
    if incoming and name_quality(incoming) >= name_quality(row.get("name") or ""):
        row["name"] = incoming
    if title and not row.get("title"):
        row["title"] = str(title).strip()
    if group and not row.get("group"):
        row["group"] = str(group).strip()
    if phone and not row.get("phone"):
        row["phone"] = str(phone).strip()
    if job and not row.get("job_description"):
        row["job_description"] = str(job).strip()
    _add_source(row, source)
    row["hits"] = int(row.get("hits") or 0) + 1


def mine_account_people(repo, account: dict) -> list[dict]:
    """Return de-duped customer people for a book. Does not write."""
    aid = str((account or {}).get("account_id") or (account or {}).get("_id") or "")
    domains = {str(d).lower().lstrip("@") for d in ((account or {}).get("domains") or []) if d}
    op = (repo.get_settings() or {}).get("operator") if repo is not None else {}
    op = op if isinstance(op, dict) else {}
    me = clean_email(str(op.get("email") or ""))
    ours = set()
    if me and "@" in me:
        ours.add(me.split("@", 1)[1])
    ours.update(str(d).lower().lstrip("@") for d in (getattr(repo, "operator_domains", lambda: [])() or []) if d)

    buckets: dict[str, dict] = {}

    def accept(email: str) -> dict | None:
        addr = clean_email(email)
        if skip_email(addr, operator_email=me, operator_domains=ours):
            return None
        if domains and domain_of(addr) not in domains:
            return None
        row = buckets.get(addr)
        if row is None:
            row = _blank_row(addr)
            buckets[addr] = row
        return row

    def ingest(email: str, *, name: str = "", title: str = "", group: str = "", phone: str = "", job: str = "", source: str = "") -> None:
        row = accept(email)
        if not row:
            return
        parsed = parse_display_name(name)
        display = parsed.get("name") or ""
        local = email.split("@", 1)[0] if "@" in email else ""
        if not display:
            display = name_from_local(local)
        _merge(
            row,
            name=display,
            title=title or parsed.get("title") or "",
            group=group or parsed.get("group") or "",
            phone=phone,
            job=job,
            source=source,
        )

    if not aid or repo is None:
        return []

    for mail in repo._account_rows("emails", aid):
        from_addr = clean_email(str(mail.get("from_addr") or ""))
        from_name = str(mail.get("from_name") or "")
        snippet = str(mail.get("snippet") or mail.get("body_text") or "")
        phone = pick_phone(snippet) if from_addr else ""
        ingest(from_addr, name=from_name, phone=phone, source="email")
        for addr in list(mail.get("to_addrs") or []) + list(mail.get("cc_addrs") or []):
            ingest(str(addr or ""), source="email")

    for event in repo._account_rows("calendar_events", aid):
        for att in event.get("attendees") or []:
            if not isinstance(att, dict):
                continue
            ingest(str(att.get("email") or ""), name=str(att.get("name") or ""), source="calendar")

    for ticket in repo._account_rows("tickets", aid):
        ingest(str(ticket.get("reporter_email") or ""), source="ticket")
        ingest(str(ticket.get("assignee_email") or ""), source="ticket")
        for comment in ticket.get("comments") or []:
            if isinstance(comment, dict):
                ingest(str(comment.get("author") or ""), source="ticket")

    for msg in repo._account_rows("slack_messages", aid):
        user = str(msg.get("user_name") or msg.get("user") or "")
        if "@" in user:
            ingest(user, source="slack")

    for msg in repo._account_rows("teams_messages", aid):
        user = str(msg.get("user_name") or "")
        if "@" in user:
            ingest(user, name=user, source="teams")
        email = str(msg.get("email") or "")
        if email:
            ingest(email, name=str(msg.get("user_name") or ""), source="teams")

    existing: dict[str, str] = {}
    for person in repo.list_people(aid):
        addr = clean_email(str(person.get("email") or ""))
        pid = str(person.get("_id") or person.get("person_id") or "")
        if addr and pid:
            existing[addr] = pid

    out: list[dict] = []
    for email, row in buckets.items():
        if not row.get("name"):
            row["name"] = name_from_local(email.split("@", 1)[0])
        row["existing_id"] = existing.get(email) or ""
        row["sources"] = [s for s in SOURCE_RANK if s in set(row.get("sources") or [])]
        out.append(row)
    out.sort(key=lambda r: (-int(r.get("hits") or 0), str(r.get("name") or "").lower(), r.get("email") or ""))
    log.info("csm.people.mined account_id=%s count=%s", aid, len(out))
    return out
