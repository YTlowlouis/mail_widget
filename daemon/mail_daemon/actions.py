"""Actions d'écriture: appelées directement par la CLI (donc par le widget), jamais par le modèle.

Chaque fonction ouvre sa propre session MCP courte, appelle un seul tool d'écriture, et se
termine — pas de boucle d'agent, pas de decision Claude, juste un appel direct au serveur MCP.
"""
from __future__ import annotations

from typing import Any

from . import mcp_tools
from .config import Config


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
