"""mail-widget-daemon: boucle de poll (3 min) qui écrit ~/.cache/mail-widget/state.json."""
from __future__ import annotations

import asyncio
import logging
import signal

import groq

from .cache import Cache
from .config import load_config
from .poller import run_poll_cycle
from .state_writer import write_state

logger = logging.getLogger("mail_daemon")


async def _run_forever() -> None:
    config = load_config()
    groq_client = groq.AsyncGroq(api_key=config.groq_api_key)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    with Cache(config.cache_db_path) as cache:
        while not stop_event.is_set():
            try:
                threads = await run_poll_cycle(config, cache, groq_client)
                write_state(config.state_path, threads)
                logger.info("Poll terminé: %d fils écrits dans %s", len(threads), config.state_path)
            except Exception:
                logger.exception("Cycle de poll échoué, nouvelle tentative au prochain intervalle")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=config.poll_interval_seconds)
            except asyncio.TimeoutError:
                pass


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(_run_forever())


if __name__ == "__main__":
    main()
