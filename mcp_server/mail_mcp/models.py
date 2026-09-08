"""Conversion des MailMessage (imap-tools) vers les dicts JSON exposés par les tools MCP."""
from __future__ import annotations

from typing import Any

from imap_tools.message import MailMessage

from .parsing import html_to_text, parse_auth_results, truncate_body

BODY_LIMIT = 2000


def message_id_of(msg: MailMessage) -> str:
    values = msg.headers.get("message-id", ("",))
    return values[0].strip() if values else ""


def email_summary(msg: MailMessage) -> dict[str, Any]:
    auth_header_values = list(msg.headers.get("authentication-results", ()))
    list_unsubscribe = msg.headers.get("list-unsubscribe", (None,))[0]
    list_unsubscribe_post = msg.headers.get("list-unsubscribe-post", (None,))[0]
    in_reply_to = msg.headers.get("in-reply-to", (None,))[0]
    references = msg.headers.get("references", (None,))[0]
    return {
        "message_id": message_id_of(msg),
        "from": msg.from_,
        "subject": msg.subject,
        "date": msg.date.isoformat() if msg.date else "",
        "is_unread": "\\Seen" not in msg.flags,
        "list_unsubscribe": list_unsubscribe,
        "list_unsubscribe_post": list_unsubscribe_post,
        "auth_results": parse_auth_results(auth_header_values),
        "in_reply_to": in_reply_to,
        "references": references,
    }


def email_body(msg: MailMessage, limit: int = BODY_LIMIT) -> dict[str, Any]:
    raw_text = (msg.text or "").strip()
    if not raw_text and msg.html:
        raw_text = html_to_text(msg.html)
    body_text, truncated = truncate_body(raw_text, limit)
    return {
        "message_id": message_id_of(msg),
        "from": msg.from_,
        "subject": msg.subject,
        "date": msg.date.isoformat() if msg.date else "",
        "body_text": body_text,
        "truncated": truncated,
    }
