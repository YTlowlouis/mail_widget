"""Serveur MCP stdio pour l'accès mail. Aucun appel LLM ici.

Les 8 tools (lecture + écriture) sont tous enregistrés ici pour rester utilisables
depuis l'inspector MCP ou toute autre CLI. C'est au daemon (phase 2) de ne passer
au modèle que les tools de lecture — jamais les tools d'écriture.
"""
from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from . import imap_client

if os.environ.get("MAIL_MCP_LOAD_DOTENV", "1") != "0":
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

mcp = MCPServer("mail-mcp")


@mcp.tool()
def list_recent(folder: str = "INBOX", limit: int = 20, since: str | None = None) -> list[dict]:
    """Liste les métadonnées des derniers mails d'un dossier, du plus récent au plus ancien.

    since: date ISO "YYYY-MM-DD", optionnelle.
    """
    return imap_client.list_recent(folder=folder, limit=limit, since=since)


@mcp.tool()
def get_email(message_id: str) -> dict:
    """Récupère le corps d'un mail (HTML converti en texte et strippé, tronqué à ~2000 caractères)."""
    return imap_client.get_email(message_id)


@mcp.tool()
def search_emails(query: str, limit: int = 20) -> list[dict]:
    """Recherche des mails par mot-clé sur From/Sujet/Corps (recherche IMAP simple, pas sémantique)."""
    return imap_client.search_emails(query=query, limit=limit)


@mcp.tool()
def move_to_folder(message_id: str, folder: str) -> dict:
    """Déplace un mail vers un dossier donné.

    Outil d'écriture: à appeler uniquement depuis le daemon/widget, jamais par le modèle.
    """
    return imap_client.move_to_folder(message_id, folder)


@mcp.tool()
def move_to_trash(message_id: str) -> dict:
    """Déplace un mail vers la Corbeille (jamais de suppression définitive/EXPUNGE).

    Outil d'écriture: à appeler uniquement depuis le daemon/widget, jamais par le modèle.
    """
    return imap_client.move_to_trash(message_id)


@mcp.tool()
def restore(message_id: str) -> dict:
    """Restaure un mail depuis la Corbeille vers son dossier d'origine.

    Outil d'écriture: à appeler uniquement depuis le daemon/widget, jamais par le modèle.
    """
    return imap_client.restore(message_id)


@mcp.tool()
def unsubscribe(message_id: str) -> dict:
    """Tente un désabonnement one-click (RFC 8058, POST sur List-Unsubscribe-Post).

    Si l'en-tête one-click n'est pas présent, retourne le lien sans jamais l'ouvrir.
    Outil d'écriture: à appeler uniquement depuis le daemon/widget, jamais par le modèle.
    """
    return imap_client.unsubscribe(message_id)


@mcp.tool()
def save_draft_reply(message_id: str, body: str) -> dict:
    """Enregistre une réponse en brouillon dans le dossier Brouillons (threading RFC 5322
    correct: In-Reply-To/References/Re:). N'envoie jamais rien — aucun outil d'envoi de mail
    n'existe dans ce projet, le brouillon reste à valider manuellement par l'utilisateur.

    Outil d'écriture: à appeler uniquement depuis le daemon/widget, jamais par le modèle.
    """
    return imap_client.save_draft_reply(message_id, body)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
