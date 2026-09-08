"""Doublures de test pour imap-tools. Aucun accès réseau réel n'est fait dans les tests."""
from __future__ import annotations

import datetime
from contextlib import contextmanager

from imap_tools.folder import FolderInfo


class FakeMessage:
    def __init__(
        self,
        message_id: str,
        uid: str,
        *,
        headers: dict[str, tuple[str, ...]] | None = None,
        flags: tuple[str, ...] = (),
        date: datetime.datetime | None = None,
        from_: str = "sender@example.com",
        subject: str = "Sujet",
        text: str = "",
        html: str = "",
    ) -> None:
        self.uid = uid
        self.message_id = message_id
        self.flags = flags
        self.date = date or datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
        self.from_ = from_
        self.subject = subject
        self.text = text
        self.html = html
        self._headers: dict[str, tuple[str, ...]] = {"message-id": (message_id,)}
        if headers:
            self._headers.update(headers)

    @property
    def headers(self) -> dict[str, tuple[str, ...]]:
        return self._headers


class FakeFolderManager:
    def __init__(self, folders: list[FolderInfo]) -> None:
        self._folders = folders
        self.current: str | None = None

    def list(self) -> list[FolderInfo]:
        return self._folders

    def set(self, name: str, readonly: bool = False) -> None:
        self.current = name


class FakeMailBox:
    """Reproduit juste assez de l'API imap_tools.MailBox pour les tests."""

    def __init__(self, folders: list[FolderInfo], messages_by_folder: dict[str, list[FakeMessage]]) -> None:
        self.folder = FakeFolderManager(folders)
        self._messages_by_folder = {k: list(v) for k, v in messages_by_folder.items()}
        self.moves: list[tuple[str, tuple[str, ...], str]] = []

    def uids(self, criteria) -> list[str]:
        criteria_str = str(criteria)
        folder = self.folder.current
        return [
            msg.uid
            for msg in self._messages_by_folder.get(folder, [])
            if msg.message_id in criteria_str
        ]

    def fetch(self, criteria, **kwargs) -> list[FakeMessage]:
        criteria_str = str(criteria)
        folder = self.folder.current
        candidates = self._messages_by_folder.get(folder, [])
        if criteria_str == "ALL":
            return list(candidates)
        if "TEXT" in criteria_str:
            needle = criteria_str.split('"')[1].lower() if '"' in criteria_str else ""
            return [msg for msg in candidates if needle in (msg.subject + msg.text).lower()]
        return [msg for msg in candidates if msg.uid in criteria_str or msg.message_id in criteria_str]

    def move(self, uid_list: list[str], destination_folder: str) -> None:
        src_folder = self.folder.current
        src_messages = self._messages_by_folder.setdefault(src_folder, [])
        dest_messages = self._messages_by_folder.setdefault(destination_folder, [])
        for uid in uid_list:
            for msg in list(src_messages):
                if msg.uid == uid:
                    src_messages.remove(msg)
                    dest_messages.append(msg)
        self.moves.append((src_folder, tuple(uid_list), destination_folder))


@contextmanager
def const_session(mb: FakeMailBox):
    yield mb
