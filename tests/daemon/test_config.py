import mail_daemon.config as config


def _isolate_dotenv(monkeypatch):
    # load_environment() lirait mcp_server/.env et daemon/.env réels sur la machine du
    # développeur — on la neutralise pour ne dépendre que des monkeypatch.setenv des tests.
    monkeypatch.setattr(config, "load_environment", lambda: None)


def test_load_config_does_not_require_groq_api_key(monkeypatch, tmp_path):
    _isolate_dotenv(monkeypatch)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("MAIL_WIDGET_CACHE_DIR", str(tmp_path))

    cfg = config.load_config()

    assert cfg.groq_api_key == ""


def test_load_config_reads_groq_api_key_when_present(monkeypatch, tmp_path):
    _isolate_dotenv(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("MAIL_WIDGET_CACHE_DIR", str(tmp_path))

    cfg = config.load_config()

    assert cfg.groq_api_key == "gsk_test"


def test_load_config_defaults(monkeypatch, tmp_path):
    _isolate_dotenv(monkeypatch)
    for var in (
        "GROQ_API_KEY",
        "MAIL_WIDGET_MODEL",
        "MAIL_WIDGET_POLL_SECONDS",
        "MAIL_WIDGET_POLL_LIMIT",
        "MAIL_MCP_DEFAULT_FOLDER",
        "MAIL_WIDGET_THREAD_DELAY_SECONDS",
        "MAIL_MCP_COMMAND",
        "MAIL_WIDGET_ARCHIVE_FOLDER",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MAIL_WIDGET_CACHE_DIR", str(tmp_path))

    cfg = config.load_config()

    assert cfg.model == "openai/gpt-oss-20b"
    assert cfg.poll_interval_seconds == 180
    assert cfg.poll_limit == 30
    assert cfg.poll_folder == "INBOX"
    assert cfg.thread_delay_seconds == 2
    assert cfg.mail_mcp_command == "mail-mcp"
    assert cfg.archive_folder == "[Gmail]/All Mail"
    assert cfg.state_path == tmp_path / "state.json"
    assert cfg.cache_db_path == tmp_path / "cache.sqlite3"
