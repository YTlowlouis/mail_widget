from mail_daemon.cache import Cache


def test_unknown_message_ids_are_not_known(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        assert cache.known_message_ids(["<a@x>", "<b@x>"]) == set()


def test_mark_messages_seen_then_known(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.mark_messages_seen(["<a@x>", "<b@x>"], "<a@x>")
        assert cache.known_message_ids(["<a@x>", "<b@x>", "<c@x>"]) == {"<a@x>", "<b@x>"}
        assert cache.thread_key_of("<b@x>") == "<a@x>"
        assert cache.thread_key_of("<c@x>") is None


def test_upsert_thread_then_get(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.upsert_thread("<a@x>", resume="Résumé", urgence="action", raison="besoin d'une réponse")
        record = cache.get_thread("<a@x>")
        assert record.resume == "Résumé"
        assert record.urgence == "action"
        assert record.raison == "besoin d'une réponse"
        assert record.otp_code is None


def test_upsert_thread_stores_otp_code(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.upsert_thread("<a@x>", "résumé", "action", "code de connexion", otp_code="482913")
        assert cache.get_thread("<a@x>").otp_code == "482913"


def test_upsert_thread_overwrites_previous_classification(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        cache.upsert_thread("<a@x>", "premier résumé", "info", "raison 1")
        cache.upsert_thread("<a@x>", "résumé mis à jour", "action", "raison 2")
        record = cache.get_thread("<a@x>")
        assert record.resume == "résumé mis à jour"
        assert record.urgence == "action"


def test_get_unknown_thread_is_none(tmp_path):
    with Cache(tmp_path / "cache.sqlite3") as cache:
        assert cache.get_thread("<missing@x>") is None


def test_cache_persists_across_instances(tmp_path):
    db_path = tmp_path / "cache.sqlite3"
    with Cache(db_path) as cache:
        cache.mark_messages_seen(["<a@x>"], "<a@x>")
        cache.upsert_thread("<a@x>", "résumé", "bruit", "newsletter")

    with Cache(db_path) as cache:
        assert cache.known_message_ids(["<a@x>"]) == {"<a@x>"}
        assert cache.get_thread("<a@x>").urgence == "bruit"
