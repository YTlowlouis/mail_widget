"""Client MCP côté daemon: lance mail-mcp en stdio, expose les tools de lecture au modèle.

Les tools d'écriture sont accessibles ici (call_tool direct, cf. actions.py) mais ne sont
JAMAIS inclus dans la liste passée au modèle — c'est le garde-fou central de
la contrainte de sécurité du projet: le modèle ne doit jamais pouvoir écrire dans la boîte.
"""
from __future__ import annotations

import json
import os
import shlex
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, Tool

READ_TOOL_NAMES = frozenset({"list_recent", "get_email", "search_emails"})


class ToolCallError(RuntimeError):
    """Le tool MCP a retourné isError=True."""


@asynccontextmanager
async def mcp_session(command: str) -> AsyncIterator[ClientSession]:
    """Démarre mail-mcp en subprocess et ouvre une session MCP initialisée.

    Hérite l'environnement du processus courant (IMAP_*, chargés par config.load_environment()
    avant l'appel) plutôt que de dépendre d'un .env local au sous-processus.
    """
    parts = shlex.split(command)
    params = StdioServerParameters(command=parts[0], args=parts[1:], env=os.environ.copy())
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_read_tools(session: ClientSession) -> list[Tool]:
    """Tools de lecture seulement — jamais move_to_folder/move_to_trash/restore/unsubscribe."""
    tools = await session.list_tools()
    return [t for t in tools.tools if t.name in READ_TOOL_NAMES]


def parse_tool_result(result: CallToolResult) -> Any:
    """Reconstruit la valeur Python retournée par un tool, quel que soit son encodage sur le fil.

    Un retour list[...] est encodé en structuredContent={"result": [...]}. Un retour dict simple
    n'a pas toujours de structuredContent (dépend du typage du tool côté serveur) et retombe sur
    un unique bloc texte JSON. On gère les deux cas plutôt que de supposer l'un ou l'autre.
    """
    if result.is_error:
        detail = result.content[0].text if result.content and hasattr(result.content[0], "text") else "erreur inconnue"
        raise ToolCallError(detail)

    if result.structured_content is not None:
        payload = result.structured_content
        if isinstance(payload, dict) and set(payload.keys()) == {"result"}:
            return payload["result"]
        return payload

    texts = [json.loads(block.text) for block in result.content if hasattr(block, "text")]
    if len(texts) == 1:
        return texts[0]
    return texts
