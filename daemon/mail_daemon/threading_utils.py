"""Regroupement de mails en fils de discussion via In-Reply-To / References (RFC 5322)."""
from __future__ import annotations

import re

_MESSAGE_ID_RE = re.compile(r"<[^<>]+>")


def extract_message_ids(header_value: str | None) -> list[str]:
    if not header_value:
        return []
    return _MESSAGE_ID_RE.findall(header_value)


def thread_key_for(message_id: str, in_reply_to: str | None, references: str | None) -> str:
    """Clé de regroupement d'un fil.

    References contient la chaîne complète (racine en premier) quand il est présent,
    c'est la source la plus fiable. À défaut, In-Reply-To donne le message parent direct.
    Sans aucun des deux, le mail est son propre fil.
    """
    reference_ids = extract_message_ids(references)
    if reference_ids:
        return reference_ids[0]
    reply_ids = extract_message_ids(in_reply_to)
    if reply_ids:
        return reply_ids[0]
    return message_id
