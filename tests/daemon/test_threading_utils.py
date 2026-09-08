from mail_daemon.threading_utils import extract_message_ids, thread_key_for


def test_extract_message_ids_multiple():
    assert extract_message_ids("<root@x> <parent@x>") == ["<root@x>", "<parent@x>"]


def test_extract_message_ids_none_or_empty():
    assert extract_message_ids(None) == []
    assert extract_message_ids("") == []


def test_thread_key_prefers_references_root():
    key = thread_key_for("<reply3@x>", in_reply_to="<reply2@x>", references="<root@x> <reply1@x> <reply2@x>")
    assert key == "<root@x>"


def test_thread_key_falls_back_to_in_reply_to():
    key = thread_key_for("<reply@x>", in_reply_to="<parent@x>", references=None)
    assert key == "<parent@x>"


def test_thread_key_falls_back_to_self_when_no_thread_headers():
    key = thread_key_for("<solo@x>", in_reply_to=None, references=None)
    assert key == "<solo@x>"


def test_seven_github_notifications_share_one_thread_key():
    # Sept notifications GitHub sur la même PR: même racine dans References -> même clé.
    root = "<pr-42@github.com>"
    keys = {
        thread_key_for(f"<notif{i}@github.com>", in_reply_to=f"<notif{i - 1}@github.com>", references=f"{root} <notif{i - 1}@github.com>")
        for i in range(1, 8)
    }
    assert keys == {root}
