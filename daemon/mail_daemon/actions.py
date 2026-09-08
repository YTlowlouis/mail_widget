"""Actions d'écriture: appelées directement par la CLI (donc par le widget), jamais par le modèle.

Chaque fonction ouvre sa propre session MCP courte, appelle un seul tool d'écriture, et se
termine — pas de boucle d'agent, pas de decision du modèle, juste un appel direct au serveur MCP.
"""
from __future__ import annotations

import logging
from typing import Any

import groq

from . import mcp_tools
from .cache import Cache
from .config import Config
from .poller import run_poll_cycle
from .state_writer import write_state

logger = logging.getLogger(__name__)


async def _call_write_tool(config: Config, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with mcp_tools.mcp_session(config.mail_mcp_command) as session:
        result = await session.call_tool(tool_name, arguments)
        return mcp_tools.parse_tool_result(result)


async def trash(config: Config, message_id: str) -> dict[str, Any]:
    return await _call_write_tool(config, "move_to_trash", {"message_id": message_id})


async def archive(config: Config, message_id: str, folder: str | None = None) -> dict[str, Any]:
    destination = folder or config.archive_folder
    return await _call_write_tool(config, "move_to_folder", {"message_id": message_id, "folder": destination})


async def restore(config: Config, message_id: str) -> dict[str, Any]:
    return await _call_write_tool(config, "restore", {"message_id": message_id})


async def unsubscribe(config: Config, message_id: str) -> dict[str, Any]:
    return await _call_write_tool(config, "unsubscribe", {"message_id": message_id})


async def reply(config: Config, message_id: str, body: str) -> dict[str, Any]:
    """Enregistre un brouillon de réponse. N'envoie jamais rien (voir mcp_server.save_draft_reply)."""
    return await _call_write_tool(config, "save_draft_reply", {"message_id": message_id, "body": body})


async def reload(config: Config) -> dict[str, Any]:
    """Force un cycle de poll immédiat (bouton "Recharger" du widget), sans attendre le
    prochain tick du daemon (jusqu'à MAIL_WIDGET_POLL_SECONDS). Ouvre sa propre instance de
    Cache/client Groq, indépendante de celle du daemon s'il tourne déjà — SQLite sérialise
    les écritures concurrentes, pas de corruption possible, au pire une brève attente.
    """
    if not config.groq_api_key:
        return {
            "status": "error",
            "detail": "GROQ_API_KEY manquante: impossible de classer de nouveaux mails",
        }

    groq_client = groq.AsyncGroq(api_key=config.groq_api_key)
    try:
        with Cache(config.cache_db_path) as cache:
            threads = await run_poll_cycle(config, cache, groq_client)
    except Exception as exc:  # noqa: BLE001 - toujours renvoyer un résultat structuré à la CLI
        logger.exception("Rechargement manuel échoué")
        return {"status": "error", "detail": str(exc)}

    write_state(config.state_path, threads)
    return {"status": "ok", "thread_count": len(threads)}
