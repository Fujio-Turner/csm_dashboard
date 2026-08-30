from __future__ import annotations

from csm_dashboard.chat.desk_answer import answer_desk
from csm_dashboard.chat.format import humanize_chat_text


def test_humanize_ticket_json():
    raw = (
        '[{"key": "ACME-12", "summary": "Scanner firmware", "status": "open", "priority": "p1"},'
        '{"key": "ACME-9", "summary": "Label printer", "status": "done", "priority": "p3"}]'
    )
    text = humanize_chat_text(raw)
    assert '"key"' not in text
    assert "ACME-12" in text
    assert "open ticket" in text
    assert "Recently closed" in text
    assert "ACME-9" in text


def test_humanize_leaves_prose():
    src = "3 open tickets on #{ACME}."
    assert humanize_chat_text(src) == src


def test_desk_wide_without_book(repo):
    from csm_dashboard.config import fixtures_dir
    from csm_dashboard.seed.load import apply_seed

    apply_seed(repo, fixtures_dir() / "seed")
    text = answer_desk(repo, "What tasks are due this week?", None)
    assert "Which book?" not in text
    assert "due this week" in text.lower()
