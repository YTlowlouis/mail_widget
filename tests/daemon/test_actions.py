import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import mail_daemon.actions as actions
from mail_daemon.config import Config


def _config(tmp_path):
    return Config(
        groq_api_key="x",
        model="m",
        poll_interval_seconds=180,
        poll_limit=30,
        poll_folder="INBOX",
        thread_delay_seconds=0,
        mail_mcp_command="mail-mcp",
        archive_folder="[Gmail]/All Mail",
        cache_dir=tmp_path,
        state_path=tmp_path / "state.json",
        cache_db_path=tmp_path / "cache.sqlite3",
    )


class FakeSession:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(is_error=False, structured_content={"status": "ok"}, content=[])


def _patch_session(monkeypatch):
    session = FakeSession()

    @asynccontextmanager
    async def fake_mcp_session(command):
        yield session

    monkeypatch.setattr(actions.mcp_tools, "mcp_session", fake_mcp_session)
    return session


def test_trash_calls_move_to_trash(monkeypatch, tmp_path):
    session = _patch_session(monkeypatch)
    result = asyncio.run(actions.trash(_config(tmp_path), "<a@x>"))
    assert session.calls == [("move_to_trash", {"message_id": "<a@x>"})]
    assert result == {"status": "ok"}


def test_restore_calls_restore(monkeypatch, tmp_path):
    session = _patch_session(monkeypatch)
    asyncio.run(actions.restore(_config(tmp_path), "<a@x>"))
    assert session.calls == [("restore", {"message_id": "<a@x>"})]


def test_unsubscribe_calls_unsubscribe(monkeypatch, tmp_path):
    session = _patch_session(monkeypatch)
    asyncio.run(actions.unsubscribe(_config(tmp_path), "<a@x>"))
    assert session.calls == [("unsubscribe", {"message_id": "<a@x>"})]


def test_archive_uses_configured_default_folder(monkeypatch, tmp_path):
    session = _patch_session(monkeypatch)
    asyncio.run(actions.archive(_config(tmp_path), "<a@x>"))
    assert session.calls == [("move_to_folder", {"message_id": "<a@x>", "folder": "[Gmail]/All Mail"})]


def test_archive_explicit_folder_overrides_default(monkeypatch, tmp_path):
    session = _patch_session(monkeypatch)
    asyncio.run(actions.archive(_config(tmp_path), "<a@x>", folder="Projets/2026"))
    assert session.calls == [("move_to_folder", {"message_id": "<a@x>", "folder": "Projets/2026"})]
