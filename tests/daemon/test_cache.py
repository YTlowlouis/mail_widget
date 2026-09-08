import sqlite3

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


def test_migrates_pre_existing_db_missing_otp_code_column(tmp_path):
    db_path = tmp_path / "cache.sqlite3"
    # Simule une base créée avant l'ajout d'otp_code: CREATE TABLE IF NOT EXISTS ne
    # modifierait jamais ce schéma tout seul, il faut une vraie migration.
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE messages (
            message_id TEXT PRIMARY KEY, thread_key TEXT NOT NULL, seen_at TEXT NOT NULL
        );
        CREATE TABLE threads (
            thread_key TEXT PRIMARY KEY, resume TEXT NOT NULL, urgence TEXT NOT NULL,
            raison TEXT NOT NULL, processed_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO threads (thread_key, resume, urgence, raison, processed_at) VALUES (?, ?, ?, ?, ?)",
        ("<old@x>", "ancien résumé", "info", "ancienne raison", "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()

    with Cache(db_path) as cache:
        # Une ligne créée avant la migration doit rester lisible, avec otp_code à None.
        old_record = cache.get_thread("<old@x>")
        assert old_record.resume == "ancien résumé"
        assert old_record.otp_code is None

        # Et upsert_thread avec un otp_code doit maintenant fonctionner sans erreur SQL.
        cache.upsert_thread("<new@x>", "résumé", "action", "code de connexion", otp_code="482913")
        assert cache.get_thread("<new@x>").otp_code == "482913"
