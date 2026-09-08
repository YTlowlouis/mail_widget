"""Un cycle de poll: liste l'INBOX, regroupe les fils nouveaux, les fait classer par le modèle."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import groq

from . import mcp_tools
from .cache import Cache
from .classifier import build_email_context, classify_thread
from .config import Config
from .otp import extract_otp_code
from .threading_utils import thread_key_for

logger = logging.getLogger(__name__)


def _group_new_by_thread(new_summaries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for summary in new_summaries:
        key = thread_key_for(summary["message_id"], summary.get("in_reply_to"), summary.get("references"))
        groups.setdefault(key, []).append(summary)
    return groups


async def run_poll_cycle(
    config: Config, cache: Cache, groq_client: groq.AsyncGroq
) -> list[dict[str, Any]]:
    async with mcp_tools.mcp_session(config.mail_mcp_command) as session:
        read_tools = await mcp_tools.list_read_tools(session)

        list_result = await session.call_tool(
            "list_recent", {"folder": config.poll_folder, "limit": config.poll_limit}
        )
        summaries: list[dict[str, Any]] = mcp_tools.parse_tool_result(list_result)

        seen_ids = cache.known_message_ids(s["message_id"] for s in summaries)
        new_summaries = [s for s in summaries if s["message_id"] not in seen_ids]

        for i, (thread_key, group) in enumerate(_group_new_by_thread(new_summaries).items()):
            if i > 0 and config.thread_delay_seconds > 0:
                # Étale les appels au modèle pour éviter de marteler le rate limit du tier
                # gratuit lors d'un gros rattrapage initial (beaucoup de fils jamais vus).
                await asyncio.sleep(config.thread_delay_seconds)
            await _process_new_thread(config, cache, groq_client, session, read_tools, thread_key, group)

        return _build_state_entries(summaries, cache)


async def _process_new_thread(
    config: Config,
    cache: Cache,
    groq_client: groq.AsyncGroq,
    session: Any,
    read_tools: list[Any],
    thread_key: str,
    group: list[dict[str, Any]],
) -> None:
    representative = max(group, key=lambda s: s["date"])
    body_result = await session.call_tool("get_email", {"message_id": representative["message_id"]})
    representative_body = mcp_tools.parse_tool_result(body_result)

    context = build_email_context(representative_body, group)
    classification = await classify_thread(groq_client, session, read_tools, config.model, context)

    if classification is None:
        # Sortie invalide ou appel échoué: rien n'est marqué comme vu, on retentera ce fil
        # au prochain cycle plutôt que d'afficher une classification inventée.
        logger.info("Fil %s non classé ce cycle, retenté au prochain poll", thread_key)
        return

    otp_code = extract_otp_code(representative_body["body_text"])
    cache.upsert_thread(thread_key, classification.resume, classification.urgence, classification.raison, otp_code)
    cache.mark_messages_seen([s["message_id"] for s in group], thread_key)


def _build_state_entries(summaries: list[dict[str, Any]], cache: Cache) -> list[dict[str, Any]]:
    threads: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        thread_key = cache.thread_key_of(summary["message_id"]) or thread_key_for(
            summary["message_id"], summary.get("in_reply_to"), summary.get("references")
        )
        record = cache.get_thread(thread_key)
        entry = threads.get(thread_key)
        if entry is None:
            entry = {
                "thread_key": thread_key,
                "message_ids": [],
                "subject": summary["subject"],
                "from": summary["from"],
                "date": summary["date"],
                "is_unread": False,
                "message_count": 0,
                "resume": record.resume if record else summary["subject"],
                "urgence": record.urgence if record else "info",
                "raison": record.raison if record else "pas encore classé (retenté au prochain poll)",
                "otp_code": record.otp_code if record else None,
                "can_unsubscribe": False,
            }
            threads[thread_key] = entry

        entry["message_ids"].append(summary["message_id"])
        entry["message_count"] += 1
        entry["is_unread"] = entry["is_unread"] or summary["is_unread"]
        # Déterministe (lu directement dans l'en-tête List-Unsubscribe côté mcp_server),
        # jamais deviné: le bouton Désabonner du widget ne s'affiche que si ça vaut le coup.
        entry["can_unsubscribe"] = entry["can_unsubscribe"] or bool(summary.get("list_unsubscribe"))
        if summary["date"] > entry["date"]:
            entry["date"] = summary["date"]
            entry["subject"] = summary["subject"]
            entry["from"] = summary["from"]

    return sorted(threads.values(), key=lambda t: t["date"], reverse=True)
