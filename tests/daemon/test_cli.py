import json

import pytest

import mail_daemon.cli as cli


def _patch_dispatch(monkeypatch, result=None, exc=None):
    async def fake_dispatch(args):
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(cli, "_dispatch", fake_dispatch)


def test_main_prints_result_to_stdout_and_exits_zero_on_success(monkeypatch, capsys):
    _patch_dispatch(monkeypatch, result={"status": "ok", "message_id": "<a@x>", "detail": None})

    cli.main(["trash", "<a@x>"])

    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "ok", "message_id": "<a@x>", "detail": None}
    assert captured.err == ""


def test_main_treats_non_error_non_ok_status_as_success(monkeypatch, capsys):
    # unsubscribe renvoie "posted" ou "link_only" en cas de succès, jamais "ok" littéralement.
    _patch_dispatch(monkeypatch, result={"status": "link_only", "url": "https://example.com/unsub", "detail": None})

    cli.main(["unsubscribe", "<a@x>"])

    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "link_only"
    assert captured.err == ""


def test_main_prints_action_level_error_to_stdout_and_exits_one(monkeypatch, capsys):
    _patch_dispatch(monkeypatch, result={"status": "error", "message_id": "<a@x>", "detail": "dossier d'origine inconnu"})

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["restore", "<a@x>"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "status": "error", "message_id": "<a@x>", "detail": "dossier d'origine inconnu"
    }
    assert captured.err == ""  # jamais sur stderr, même en cas d'erreur "normale"


def test_main_prints_unexpected_exception_to_stdout_as_json_and_exits_one(monkeypatch, capsys):
    _patch_dispatch(monkeypatch, exc=RuntimeError("connexion IMAP impossible"))

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["trash", "<a@x>"])

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "error", "detail": "connexion IMAP impossible"}
    assert captured.err == ""


def test_main_dispatches_archive_folder_option(monkeypatch):
    seen_args = {}

    async def fake_dispatch(args):
        seen_args["folder"] = args.folder
        seen_args["message_id"] = args.message_id
        return {"status": "ok"}

    monkeypatch.setattr(cli, "_dispatch", fake_dispatch)
    cli.main(["archive", "<a@x>", "--folder", "Projets"])

    assert seen_args == {"folder": "Projets", "message_id": "<a@x>"}
