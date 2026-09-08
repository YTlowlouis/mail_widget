import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import mail_daemon.poller as poller
from mail_daemon.cache import Cache
from mail_daemon.config import Config
from mail_daemon.poller import _build_state_entries, _group_new_by_thread
from mail_daemon.schema import EmailClassification


def _summary(message_id, subject, date, *, unread=True, in_reply_to=None, references=None, from_="a@x.com"):
    return {
        "message_id": message_id,
        "from": from_,
        "subject": subject,
        "date": date,
        "is_unread": unread,
        "list_unsubscribe": None,
        "list_unsubscribe_post": None,
        "auth_results": {"spf": "pass", "dkim": "pass", "dmarc": "pass"},
        "in_reply_to": in_reply_to,
        "references": references,
    }


def _config(tmp_path):
    return Config(
        anthropic_api_key="x",
        model="claude-haiku-4-5-20251001",
        poll_interval_seconds=180,
        poll_limit=30,
        poll_folder="INBOX",
        mail_mcp_command="mail-mcp",
        archive_folder="[Gmail]/All Mail",
        cache_dir=tmp_path,
        state_path=tmp_path / "state.json",
        cache_db_path=tmp_path / "cache.sqlite3",
    )


# -- _group_new_by_thread ----------------------------------------------------


def test_group_new_by_thread_groups_same_root():
    summaries = [
        _summary("<a@x>", "sujet", "2026-01-01T00:00:00", references="<root@x>"),
        _summary("<b@x>", "sujet", "2026-01-02T00:00:00", references="<root@x> <a@x>"),
    ]
    groups = _group_new_by_thread(summaries)
    assert list(groups.keys()) == ["<root@x>"]
    assert len(groups["<root@x>"]) == 2


def test_group_new_by_thread_separates_unrelated_messages():
    summaries = [_summary("<a@x>", "s1", "2026-01-01T00:00:00"), _summary("<b@x>", "s2", "2026-01-02T00:00:00")]
    groups = _group_new_by_thread(summaries)
    assert set(groups.keys()) == {"<a@x>", "<b@x>"}


# -- _build_state_entries -----------------------------------------------------


def test_build_state_entries_uses_cached_classification(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.mark_messages_seen(["<a@x>"], "<a@x>")
        cache.upsert_thread("<a@x>", "Un résumé", "action", "réponse attendue")
        entries = _build_state_entries([_summary("<a@x>", "Sujet original", "2026-01-01T00:00:00")], cache)

    assert len(entries) == 1
    assert entries[0]["resume"] == "Un résumé"
    assert entries[0]["urgence"] == "action"


def test_build_state_entries_falls_back_when_never_classified(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        entries = _build_state_entries([_summary("<a@x>", "Sujet original", "2026-01-01T00:00:00")], cache)

    assert entries[0]["resume"] == "Sujet original"
    assert entries[0]["urgence"] == "info"


def test_build_state_entries_aggregates_message_count_and_unread(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.mark_messages_seen(["<a@x>", "<b@x>"], "<a@x>")
        cache.upsert_thread("<a@x>", "7 notifs PR #42", "bruit", "notifications groupées")
        summaries = [
            _summary("<a@x>", "s", "2026-01-01T00:00:00", unread=False, references="<a@x>"),
            _summary("<b@x>", "s", "2026-01-02T00:00:00", unread=True, references="<a@x>"),
        ]
        entries = _build_state_entries(summaries, cache)

    assert len(entries) == 1
    assert entries[0]["message_count"] == 2
    assert entries[0]["is_unread"] is True  # au moins un message non lu dans le fil
    assert entries[0]["date"] == "2026-01-02T00:00:00"  # date du message le plus récent


# -- run_poll_cycle (intégration, MCP + Claude mockés) ------------------------


class FakeSession:
    def __init__(self, list_recent_result, bodies):
        self.list_recent_result = list_recent_result
        self.bodies = bodies
        self.calls: list[tuple[str, dict]] = []

    async def list_tools(self):
        names = ["list_recent", "get_email", "search_emails", "move_to_trash", "move_to_folder", "restore", "unsubscribe"]
        return SimpleNamespace(tools=[SimpleNamespace(name=n) for n in names])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "list_recent":
            return SimpleNamespace(is_error=False, structured_content={"result": self.list_recent_result}, content=[])
        if name == "get_email":
            body = self.bodies[arguments["message_id"]]
            return SimpleNamespace(is_error=False, structured_content=None, content=[SimpleNamespace(text=json.dumps(body))])
        raise AssertionError(f"tool d'écriture appelé depuis le poller: {name}")


def _run_poll_cycle_with_fakes(config, cache, summaries, bodies, classification, monkeypatch):
    session = FakeSession(summaries, bodies)

    @asynccontextmanager
    async def fake_mcp_session(command):
        yield session

    monkeypatch.setattr(poller.mcp_tools, "mcp_session", fake_mcp_session)

    call_count = 0

    async def fake_classify_thread(anthropic_client, session_, read_tools, model, context):
        nonlocal call_count
        call_count += 1
        assert session_ is session
        assert {t.name for t in read_tools} == {"list_recent", "get_email", "search_emails"}
        return classification

    monkeypatch.setattr(poller, "classify_thread", fake_classify_thread)

    threads = asyncio.run(poller.run_poll_cycle(config, cache, anthropic_client=None))
    return threads, call_count, session


def test_seven_github_notifications_trigger_a_single_claude_call(monkeypatch, tmp_path):
    root = "<pr-42@github.com>"
    summaries = []
    bodies = {}
    for i in range(1, 8):
        mid = f"<notif{i}@github.com>"
        prev = f"<notif{i - 1}@github.com>" if i > 1 else None
        refs = root if prev is None else f"{root} {prev}"
        summaries.append(
            _summary(
                mid, f"PR #42 update {i}", f"2026-01-01T00:0{i}:00",
                from_="notifications@github.com", in_reply_to=prev, references=refs,
            )
        )
        bodies[mid] = {
            "message_id": mid, "from": "notifications@github.com", "subject": f"PR #42 update {i}",
            "date": f"2026-01-01T00:0{i}:00", "body_text": "...", "truncated": False,
        }

    classification = EmailClassification(
        resume="7 mises à jour sur la PR #42", urgence="bruit", raison="notifications automatiques groupées"
    )
    config = _config(tmp_path)
    with Cache(config.cache_db_path) as cache:
        threads, call_count, session = _run_poll_cycle_with_fakes(
            config, cache, summaries, bodies, classification, monkeypatch
        )

    assert call_count == 1  # sept notifications -> un seul appel Claude
    assert len(threads) == 1
    assert threads[0]["message_count"] == 7
    assert threads[0]["resume"] == "7 mises à jour sur la PR #42"
    # get_email n'a été appelé qu'une fois (le message représentatif du groupe)
    get_email_calls = [c for c in session.calls if c[0] == "get_email"]
    assert len(get_email_calls) == 1


def test_already_seen_message_is_never_resent_to_claude(monkeypatch, tmp_path):
    config = _config(tmp_path)
    with Cache(config.cache_db_path) as cache:
        cache.mark_messages_seen(["<a@x>"], "<a@x>")
        cache.upsert_thread("<a@x>", "déjà résumé", "info", "déjà traité")

        summaries = [_summary("<a@x>", "Sujet", "2026-01-01T00:00:00")]
        threads, call_count, session = _run_poll_cycle_with_fakes(
            config, cache, summaries, bodies={}, classification=None, monkeypatch=monkeypatch
        )

    assert call_count == 0  # jamais renvoyé à l'API
    assert [c for c in session.calls if c[0] == "get_email"] == []
    assert threads[0]["resume"] == "déjà résumé"


def test_invalid_classification_leaves_thread_unmarked_for_retry(monkeypatch, tmp_path):
    config = _config(tmp_path)
    with Cache(config.cache_db_path) as cache:
        summaries = [_summary("<a@x>", "Sujet", "2026-01-01T00:00:00")]
        bodies = {"<a@x>": {"message_id": "<a@x>", "from": "a@x.com", "subject": "Sujet", "date": "2026-01-01", "body_text": "...", "truncated": False}}

        threads, call_count, _ = _run_poll_cycle_with_fakes(
            config, cache, summaries, bodies, classification=None, monkeypatch=monkeypatch
        )

        assert call_count == 1
        assert cache.known_message_ids(["<a@x>"]) == set()  # pas marqué vu, sera retenté
        assert threads[0]["urgence"] == "info"
        assert "pas encore classé" in threads[0]["raison"]
