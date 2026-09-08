"""Configuration du daemon, lue depuis l'environnement (mcp_server/.env puis daemon/.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MCP_SERVER_ENV = _REPO_ROOT / "mcp_server" / ".env"
_DAEMON_ENV = _REPO_ROOT / "daemon" / ".env"


def load_environment() -> None:
    """Charge mcp_server/.env (identifiants IMAP, réutilisés par le sous-processus mail-mcp)
    puis daemon/.env (GROQ_API_KEY et réglages du daemon). N'écrase jamais une variable
    déjà présente dans l'environnement (ex: EnvironmentFile de systemd)."""
    if _MCP_SERVER_ENV.exists():
        load_dotenv(_MCP_SERVER_ENV, override=False)
    if _DAEMON_ENV.exists():
        load_dotenv(_DAEMON_ENV, override=False)


@dataclass(frozen=True)
class Config:
    groq_api_key: str
    model: str
    poll_interval_seconds: int
    poll_limit: int
    poll_folder: str
    thread_delay_seconds: float
    mail_mcp_command: str
    archive_folder: str
    cache_dir: Path
    state_path: Path
    cache_db_path: Path


def load_config() -> Config:
    """Charge la config partagée par le daemon et la CLI (mail-widget-ctl).

    GROQ_API_KEY n'est PAS exigée ici: la CLI (trash/archive/restore/unsubscribe) n'appelle
    jamais le modèle, ce serait une dépendance artificielle. C'est mail-widget-daemon qui
    vérifie sa présence avant de construire le client Groq.
    """
    load_environment()
    api_key = os.environ.get("GROQ_API_KEY", "")

    cache_dir = Path(
        os.environ.get("MAIL_WIDGET_CACHE_DIR", str(Path.home() / ".cache" / "mail-widget"))
    )
    return Config(
        groq_api_key=api_key,
        model=os.environ.get("MAIL_WIDGET_MODEL", "openai/gpt-oss-20b"),
        poll_interval_seconds=int(os.environ.get("MAIL_WIDGET_POLL_SECONDS", "180")),
        poll_limit=int(os.environ.get("MAIL_WIDGET_POLL_LIMIT", "30")),
        poll_folder=os.environ.get("MAIL_MCP_DEFAULT_FOLDER", "INBOX"),
        # Espacement entre deux appels au modèle dans un même cycle, pour ne pas dépasser le
        # rate limit du tier gratuit lors d'un gros rattrapage initial (beaucoup de mails jamais vus).
        thread_delay_seconds=float(os.environ.get("MAIL_WIDGET_THREAD_DELAY_SECONDS", "2")),
        mail_mcp_command=os.environ.get("MAIL_MCP_COMMAND", "mail-mcp"),
        # Gmail n'a pas de dossier "Archive": archiver = retirer de INBOX en gardant le mail
        # visible dans "Tous les messages". Pas de résolution dynamique possible ici (le daemon
        # ne parle pas IMAP directement) donc c'est un nom configurable plutôt qu'une devinette.
        archive_folder=os.environ.get("MAIL_WIDGET_ARCHIVE_FOLDER", "[Gmail]/All Mail"),
        cache_dir=cache_dir,
        state_path=cache_dir / "state.json",
        cache_db_path=cache_dir / "cache.sqlite3",
    )
