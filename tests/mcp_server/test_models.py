from fakes import FakeMessage

from mail_mcp.models import email_body, email_summary


def test_email_summary_shape_and_unread_flag():
    msg = FakeMessage(
        "<abc@example.com>",
        "1",
        flags=(),
        headers={
            "list-unsubscribe": ("<https://example.com/unsub>",),
            "list-unsubscribe-post": ("List-Unsubscribe=One-Click",),
            "authentication-results": ("spf=pass dkim=pass dmarc=pass",),
        },
        from_="newsletter@example.com",
        subject="Une info",
    )
    summary = email_summary(msg)
    assert summary["message_id"] == "<abc@example.com>"
    assert summary["from"] == "newsletter@example.com"
    assert summary["subject"] == "Une info"
    assert summary["is_unread"] is True  # pas de flag \Seen
    assert summary["list_unsubscribe"] == "<https://example.com/unsub>"
    assert summary["list_unsubscribe_post"] == "List-Unsubscribe=One-Click"
    assert summary["auth_results"] == {"spf": "pass", "dkim": "pass", "dmarc": "pass"}


def test_email_summary_seen_flag_marks_read():
    msg = FakeMessage("<x@example.com>", "2", flags=("\\Seen",))
    assert email_summary(msg)["is_unread"] is False


def test_email_summary_missing_headers_default_to_none_and_unknown():
    msg = FakeMessage("<y@example.com>", "3")
    summary = email_summary(msg)
    assert summary["list_unsubscribe"] is None
    assert summary["list_unsubscribe_post"] is None
    assert summary["auth_results"] == {"spf": "unknown", "dkim": "unknown", "dmarc": "unknown"}
    assert summary["in_reply_to"] is None
    assert summary["references"] is None


def test_email_summary_exposes_thread_headers_for_grouping():
    msg = FakeMessage(
        "<reply@example.com>",
        "7",
        headers={
            "in-reply-to": ("<parent@example.com>",),
            "references": ("<root@example.com> <parent@example.com>",),
        },
    )
    summary = email_summary(msg)
    assert summary["in_reply_to"] == "<parent@example.com>"
    assert summary["references"] == "<root@example.com> <parent@example.com>"


def test_email_body_prefers_plain_text():
    msg = FakeMessage("<z@example.com>", "4", text="Texte brut", html="<p>Html</p>")
    body = email_body(msg)
    assert body["body_text"] == "Texte brut"
    assert body["truncated"] is False


def test_email_body_falls_back_to_html_when_no_plain_text():
    msg = FakeMessage("<w@example.com>", "5", text="", html="<p>Seulement du HTML</p>")
    body = email_body(msg)
    assert body["body_text"] == "Seulement du HTML"


def test_email_body_truncates_long_text():
    msg = FakeMessage("<v@example.com>", "6", text="a" * 3000)
    body = email_body(msg, limit=2000)
    assert body["truncated"] is True
    assert len(body["body_text"]) <= 2001
