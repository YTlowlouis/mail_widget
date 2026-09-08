from mail_mcp.trash_state import TrashState


def test_remember_and_origin_of(tmp_path):
    state = TrashState(path=tmp_path / "trash_state.json")
    state.remember("<a@example.com>", "INBOX")
    assert state.origin_of("<a@example.com>") == "INBOX"


def test_origin_of_unknown_message_is_none(tmp_path):
    state = TrashState(path=tmp_path / "trash_state.json")
    assert state.origin_of("<missing@example.com>") is None


def test_forget_removes_entry(tmp_path):
    state = TrashState(path=tmp_path / "trash_state.json")
    state.remember("<a@example.com>", "INBOX")
    state.forget("<a@example.com>")
    assert state.origin_of("<a@example.com>") is None


def test_forget_unknown_message_is_a_noop(tmp_path):
    state = TrashState(path=tmp_path / "trash_state.json")
    state.forget("<missing@example.com>")  # ne doit pas lever


def test_state_persists_across_instances(tmp_path):
    path = tmp_path / "trash_state.json"
    TrashState(path=path).remember("<a@example.com>", "Projets")
    assert TrashState(path=path).origin_of("<a@example.com>") == "Projets"


def test_corrupted_state_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "trash_state.json"
    path.write_text("{ceci n'est pas du json", encoding="utf-8")
    state = TrashState(path=path)
    assert state.origin_of("<a@example.com>") is None
    # et l'écriture suivante doit quand même fonctionner
    state.remember("<a@example.com>", "INBOX")
    assert state.origin_of("<a@example.com>") == "INBOX"
