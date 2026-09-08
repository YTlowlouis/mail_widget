import pytest
from fakes import FakeMailBox, FakeMessage, const_session
from imap_tools.folder import FolderInfo

from mail_mcp import imap_client


def _mailbox_with_trash(flags=("\\Trash",), trash_name="[Gmail]/Trash"):
    return [
        FolderInfo(name="INBOX", delim="/", flags=()),
        FolderInfo(name=trash_name, delim="/", flags=flags),
    ]


def test_locate_finds_message_in_inbox():
    msg = FakeMessage("<a@example.com>", "101")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    folder, uid = imap_client._locate(mb, "<a@example.com>", "[Gmail]/Trash")
    assert (folder, uid) == ("INBOX", "101")


def test_locate_finds_message_in_trash():
    msg = FakeMessage("<a@example.com>", "202")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [], "[Gmail]/Trash": [msg]})
    folder, uid = imap_client._locate(mb, "<a@example.com>", "[Gmail]/Trash")
    assert (folder, uid) == ("[Gmail]/Trash", "202")


def test_locate_raises_when_message_nowhere():
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [], "[Gmail]/Trash": []})
    with pytest.raises(imap_client.MessageNotFoundError):
        imap_client._locate(mb, "<missing@example.com>", "[Gmail]/Trash")


def test_trash_folder_uses_special_use_flag():
    mb = FakeMailBox(_mailbox_with_trash(trash_name="Corbeille perso"), {})
    assert imap_client.trash_folder(mb) == "Corbeille perso"


def test_trash_folder_falls_back_to_known_name_without_flag():
    folders = [FolderInfo(name="INBOX", delim="/", flags=()), FolderInfo(name="Trash", delim="/", flags=())]
    mb = FakeMailBox(folders, {})
    assert imap_client.trash_folder(mb) == "Trash"


def test_trash_folder_raises_when_not_found():
    folders = [FolderInfo(name="INBOX", delim="/", flags=())]
    mb = FakeMailBox(folders, {})
    with pytest.raises(imap_client.ImapConfigError):
        imap_client.trash_folder(mb)


def test_move_to_trash_then_restore_roundtrip(monkeypatch, tmp_path):
    msg = FakeMessage("<m1@example.com>", "55")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))
    monkeypatch.setenv("MAIL_MCP_STATE_DIR", str(tmp_path))

    trash_result = imap_client.move_to_trash("<m1@example.com>")
    assert trash_result["status"] == "ok"
    assert mb.moves == [("INBOX", ("55",), "[Gmail]/Trash")]
    assert mb._messages_by_folder["INBOX"] == []
    assert mb._messages_by_folder["[Gmail]/Trash"] == [msg]

    restore_result = imap_client.restore("<m1@example.com>")
    assert restore_result == {
        "status": "ok",
        "message_id": "<m1@example.com>",
        "restored_to": "INBOX",
        "detail": None,
    }
    assert mb._messages_by_folder["INBOX"] == [msg]
    assert mb._messages_by_folder["[Gmail]/Trash"] == []


def test_move_to_trash_is_idempotent_when_already_in_trash(monkeypatch, tmp_path):
    msg = FakeMessage("<m2@example.com>", "77")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [], "[Gmail]/Trash": [msg]})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))
    monkeypatch.setenv("MAIL_MCP_STATE_DIR", str(tmp_path))

    result = imap_client.move_to_trash("<m2@example.com>")
    assert result["status"] == "ok"
    assert mb.moves == []  # aucun déplacement, déjà à la bonne place


def test_restore_without_prior_trash_entry_errors_without_touching_mailbox(monkeypatch, tmp_path):
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))
    monkeypatch.setenv("MAIL_MCP_STATE_DIR", str(tmp_path))

    result = imap_client.restore("<never-trashed@example.com>")
    assert result["status"] == "error"
    assert result["restored_to"] is None
    assert mb.moves == []


def test_get_email_prefers_plain_text_body(monkeypatch):
    msg = FakeMessage("<g1@example.com>", "9", text="Bonjour")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))

    body = imap_client.get_email("<g1@example.com>")
    assert body["body_text"] == "Bonjour"
    assert body["message_id"] == "<g1@example.com>"


def test_search_emails_matches_subject_and_text(monkeypatch):
    matching = FakeMessage("<s1@example.com>", "1", subject="Facture de septembre", text="")
    other = FakeMessage("<s2@example.com>", "2", subject="Autre chose", text="")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [matching, other], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))

    results = imap_client.search_emails("facture")
    assert [r["message_id"] for r in results] == ["<s1@example.com>"]


def test_unsubscribe_posts_one_click_when_supported(monkeypatch):
    msg = FakeMessage(
        "<u1@example.com>",
        "1",
        headers={
            "list-unsubscribe": ("<https://example.com/unsub?id=1>",),
            "list-unsubscribe-post": ("List-Unsubscribe=One-Click",),
        },
    )
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))

    posted_requests = []

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fake_urlopen(request, timeout=10):
        posted_requests.append(request)
        return _FakeResponse()

    monkeypatch.setattr(imap_client.urllib.request, "urlopen", _fake_urlopen)

    result = imap_client.unsubscribe("<u1@example.com>")
    assert result["status"] == "posted"
    assert result["url"] == "https://example.com/unsub?id=1"
    assert len(posted_requests) == 1
    assert posted_requests[0].method == "POST"


def test_unsubscribe_returns_link_only_without_one_click_header(monkeypatch):
    msg = FakeMessage(
        "<u2@example.com>",
        "2",
        headers={"list-unsubscribe": ("<https://example.com/unsub?id=2>",)},
    )
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))

    def _unexpected_urlopen(*args, **kwargs):
        raise AssertionError("unsubscribe ne doit jamais POSTer sans List-Unsubscribe-Post")

    monkeypatch.setattr(imap_client.urllib.request, "urlopen", _unexpected_urlopen)

    result = imap_client.unsubscribe("<u2@example.com>")
    assert result["status"] == "link_only"
    assert result["url"] == "https://example.com/unsub?id=2"


def test_unsubscribe_without_header_errors(monkeypatch):
    msg = FakeMessage("<u3@example.com>", "3")
    mb = FakeMailBox(_mailbox_with_trash(), {"INBOX": [msg], "[Gmail]/Trash": []})
    monkeypatch.setattr(imap_client, "session", lambda: const_session(mb))

    result = imap_client.unsubscribe("<u3@example.com>")
    assert result["status"] == "error"
    assert result["url"] is None
