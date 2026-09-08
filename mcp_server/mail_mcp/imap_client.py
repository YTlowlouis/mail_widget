"""Toute la logique IMAP. Identifiants lus uniquement depuis l'environnement, jamais du dépôt."""
from __future__ import annotations

import datetime
import os
import re
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any, Iterator

from imap_tools import AND, Header, MailBox
from imap_tools.message import MailMessage

from .models import email_body, email_summary
from .parsing import extract_unsubscribe_urls
from .trash_state import TrashState

DEFAULT_FOLDER = os.environ.get("MAIL_MCP_DEFAULT_FOLDER", "INBOX")
UNSUBSCRIBE_POST_BODY = b"List-Unsubscribe=One-Click"


class ImapConfigError(RuntimeError):
    """Configuration invalide ou manquante (variables d'environnement)."""


class MessageNotFoundError(RuntimeError):
    """Aucun message avec ce Message-ID n'a été trouvé dans les dossiers surveillés."""


def _env(name: str, *, required: bool = True, default: str | None = None) -> str | None:
    value = os.environ.get(name, default)
    if required and not value:
        raise ImapConfigError(f"Variable d'environnement manquante: {name}")
    return value


@contextmanager
def session() -> Iterator[MailBox]:
    host = _env("IMAP_HOST")
    port = int(_env("IMAP_PORT", default="993"))
    user = _env("IMAP_USER")
    password = _env("IMAP_PASSWORD")
    with MailBox(host, port).login(user, password, initial_folder=None) as mb:
        yield mb


def _special_use_folder(mb: MailBox, attribute: str, fallback_names: tuple[str, ...]) -> str | None:
    infos = mb.folder.list()
    for info in infos:
        if attribute in info.flags:
            return info.name
    existing = {info.name for info in infos}
    for name in fallback_names:
        if name in existing:
            return name
    return None


def trash_folder(mb: MailBox) -> str:
    folder = _special_use_folder(
        mb, "\\Trash", ("[Gmail]/Trash", "[Gmail]/Corbeille", "Trash", "Deleted Items")
    )
    if not folder:
        raise ImapConfigError("Dossier Corbeille introuvable sur le serveur (pas de flag \\Trash ni de nom connu)")
    return folder


def _locate(mb: MailBox, message_id: str, trash: str) -> tuple[str, str]:
    """Cherche un Message-ID dans INBOX puis dans la Corbeille. Retourne (dossier, uid)."""
    for folder in (DEFAULT_FOLDER, trash):
        mb.folder.set(folder)
        uids = mb.uids(AND(header=Header("Message-ID", message_id)))
        if uids:
            return folder, uids[0]
    raise MessageNotFoundError(f"Message introuvable (INBOX et Corbeille): {message_id}")


def list_recent(folder: str = DEFAULT_FOLDER, limit: int = 20, since: str | None = None) -> list[dict[str, Any]]:
    with session() as mb:
        mb.folder.set(folder)
        criteria: Any = "ALL"
        if since:
            criteria = AND(date_gte=datetime.datetime.strptime(since, "%Y-%m-%d").date())
        messages = mb.fetch(criteria, limit=limit, reverse=True, mark_seen=False, headers_only=True)
        return [email_summary(msg) for msg in messages]


def get_email(message_id: str) -> dict[str, Any]:
    with session() as mb:
        trash = trash_folder(mb)
        folder, uid = _locate(mb, message_id, trash)
        mb.folder.set(folder)
        messages = list(mb.fetch(AND(uid=uid), mark_seen=False, headers_only=False))
        if not messages:
            raise MessageNotFoundError(message_id)
        return email_body(messages[0])


def search_emails(query: str, limit: int = 20) -> list[dict[str, Any]]:
    with session() as mb:
        mb.folder.set(DEFAULT_FOLDER)
        messages = mb.fetch(AND(text=query), limit=limit, reverse=True, mark_seen=False, headers_only=True)
        return [email_summary(msg) for msg in messages]


def move_to_folder(message_id: str, folder: str) -> dict[str, Any]:
    with session() as mb:
        trash = trash_folder(mb)
        src_folder, uid = _locate(mb, message_id, trash)
        if src_folder == folder:
            return {"status": "ok", "message_id": message_id, "folder": folder, "detail": "déjà dans ce dossier"}
        mb.folder.set(src_folder)
        mb.move([uid], folder)
        return {"status": "ok", "message_id": message_id, "folder": folder, "detail": None}


def move_to_trash(message_id: str) -> dict[str, Any]:
    with session() as mb:
        trash = trash_folder(mb)
        src_folder, uid = _locate(mb, message_id, trash)
        if src_folder == trash:
            return {"status": "ok", "message_id": message_id, "detail": "déjà dans la corbeille"}
        mb.folder.set(src_folder)
        mb.move([uid], trash)
        TrashState().remember(message_id, src_folder)
        return {"status": "ok", "message_id": message_id, "detail": None}


def restore(message_id: str) -> dict[str, Any]:
    origin = TrashState().origin_of(message_id)
    if not origin:
        return {
            "status": "error",
            "message_id": message_id,
            "restored_to": None,
            "detail": "dossier d'origine inconnu (jamais mis à la corbeille via ce serveur)",
        }
    with session() as mb:
        trash = trash_folder(mb)
        mb.folder.set(trash)
        uids = mb.uids(AND(header=Header("Message-ID", message_id)))
        if not uids:
            return {
                "status": "error",
                "message_id": message_id,
                "restored_to": None,
                "detail": "message introuvable dans la corbeille",
            }
        mb.move([uids[0]], origin)
        TrashState().forget(message_id)
        return {"status": "ok", "message_id": message_id, "restored_to": origin, "detail": None}


def unsubscribe(message_id: str) -> dict[str, Any]:
    with session() as mb:
        trash = trash_folder(mb)
        folder, uid = _locate(mb, message_id, trash)
        mb.folder.set(folder)
        messages = list(mb.fetch(AND(uid=uid), mark_seen=False, headers_only=True))
        if not messages:
            raise MessageNotFoundError(message_id)
        msg: MailMessage = messages[0]

    list_unsubscribe = msg.headers.get("list-unsubscribe", (None,))[0]
    list_unsubscribe_post = msg.headers.get("list-unsubscribe-post", (None,))[0]
    http_urls, mailto_urls = extract_unsubscribe_urls(list_unsubscribe)

    if not list_unsubscribe:
        return {"status": "error", "url": None, "detail": "Pas d'en-tête List-Unsubscribe sur ce mail"}

    if list_unsubscribe_post and http_urls:
        url = http_urls[0]
        request = urllib.request.Request(
            url,
            data=UNSUBSCRIBE_POST_BODY,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return {"status": "posted", "url": url, "detail": f"HTTP {response.status}"}
        except urllib.error.URLError as exc:
            return {"status": "error", "url": url, "detail": str(exc)}

    if http_urls:
        return {
            "status": "link_only",
            "url": http_urls[0],
            "detail": "Pas de List-Unsubscribe-Post (one-click RFC 8058), lien à ouvrir manuellement",
        }

    if mailto_urls:
        return {
            "status": "link_only",
            "url": mailto_urls[0],
            "detail": "Désabonnement par email uniquement, aucun envoi automatique",
        }

    return {"status": "error", "url": None, "detail": "Aucune méthode de désabonnement exploitable dans l'en-tête"}
