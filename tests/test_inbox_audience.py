from __future__ import annotations

from csm_dashboard.storage.repo import inbox_audience


def test_mail_to_operator_is_me():
    assert (
        inbox_audience(
            kind="email",
            to_addrs=["jordan@example.com"],
            me="jordan@example.com",
            them_emails={"pat@acme.com"},
            them_domains={"acme.com"},
            us_domains={"example.com"},
        )
        == "me"
    )


def test_mail_to_customer_is_them():
    assert (
        inbox_audience(
            kind="email",
            to_addrs=["pat@acme.com"],
            me="jordan@example.com",
            them_emails={"pat@acme.com"},
            them_domains={"acme.com"},
            us_domains={"example.com"},
        )
        == "them"
    )


def test_mail_to_teammate_is_us():
    assert (
        inbox_audience(
            kind="email",
            to_addrs=["riley@example.com"],
            cc_addrs=["jordan@example.com"],
            me="jordan@example.com",
            us_emails={"riley@example.com"},
            us_domains={"example.com"},
            them_domains={"acme.com"},
        )
        == "us"
    )


def test_mail_to_both_sides_is_all():
    assert (
        inbox_audience(
            kind="email",
            to_addrs=["jordan@example.com", "pat@acme.com"],
            me="jordan@example.com",
            them_emails={"pat@acme.com"},
            them_domains={"acme.com"},
            us_domains={"example.com"},
        )
        == "all"
    )


def test_unknown_address_is_question_marks():
    assert (
        inbox_audience(
            kind="email",
            to_addrs=["mystery@somewhere.test"],
            me="jordan@example.com",
            us_domains={"example.com"},
            them_domains={"acme.com"},
        )
        == "unknown"
    )


def test_empty_mail_addrs_unknown_other_kinds_na():
    assert inbox_audience(kind="email", to_addrs=[], me="jordan@example.com") == "unknown"
    assert inbox_audience(kind="note") == "na"


def test_task_to_me_is_me():
    assert (
        inbox_audience(
            kind="task",
            to_addrs=["jordan@example.com"],
            me="jordan@example.com",
            us_domains={"example.com"},
        )
        == "me"
    )


def test_shared_channel_is_all_dm_is_me():
    assert inbox_audience(kind="slack", channel_id="C0ACME1") == "all"
    assert inbox_audience(kind="teams", channel_id="19:acme-success") == "all"
    assert inbox_audience(kind="slack", channel_id="D0123ABC") == "me"
    assert inbox_audience(kind="teams", channel_id="19:dm-pat", is_im=True) == "me"
    assert inbox_audience(kind="slack") == "unknown"
