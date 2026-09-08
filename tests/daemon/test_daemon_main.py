import asyncio

import pytest

import mail_daemon.daemon_main as daemon_main
from mail_daemon.config import Config


def _config(tmp_path, groq_api_key=""):
    return Config(
        groq_api_key=groq_api_key,
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


def test_run_forever_raises_immediately_when_groq_api_key_missing(monkeypatch, tmp_path):
    # La CLI (mail-widget-ctl) n'a pas besoin de GROQ_API_KEY (elle n'appelle jamais le
    # modèle), donc load_config() ne l'exige plus. C'est mail-widget-daemon qui doit
    # échouer vite et clairement s'il en a besoin et qu'elle manque.
    monkeypatch.setattr(daemon_main, "load_config", lambda: _config(tmp_path, groq_api_key=""))

    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        asyncio.run(daemon_main._run_forever())
