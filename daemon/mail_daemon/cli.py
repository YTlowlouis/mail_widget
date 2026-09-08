"""mail-widget-ctl: CLI d'actions, appelée par le widget. Jamais par le modèle."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from . import actions
from .config import load_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mail-widget-ctl", description="Actions sur un mail, hors du modèle")
    sub = parser.add_subparsers(dest="command", required=True)

    trash_parser = sub.add_parser("trash", help="Déplace le mail vers la Corbeille")
    trash_parser.add_argument("message_id")

    archive_parser = sub.add_parser("archive", help="Archive le mail")
    archive_parser.add_argument("message_id")
    archive_parser.add_argument("--folder", default=None, help="Dossier de destination (défaut: config)")

    restore_parser = sub.add_parser("restore", help="Restaure le mail depuis la Corbeille")
    restore_parser.add_argument("message_id")

    unsubscribe_parser = sub.add_parser("unsubscribe", help="Tente un désabonnement")
    unsubscribe_parser.add_argument("message_id")

    return parser


async def _dispatch(args: argparse.Namespace) -> dict:
    config = load_config()
    if args.command == "trash":
        return await actions.trash(config, args.message_id)
    if args.command == "archive":
        return await actions.archive(config, args.message_id, folder=args.folder)
    if args.command == "restore":
        return await actions.restore(config, args.message_id)
    if args.command == "unsubscribe":
        return await actions.unsubscribe(config, args.message_id)
    raise ValueError(f"Commande inconnue: {args.command}")


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        result = asyncio.run(_dispatch(args))
    except Exception as exc:  # noqa: BLE001 - on veut toujours un JSON en sortie, jamais une trace brute
        result = {"status": "error", "detail": str(exc)}

    # Toujours une seule ligne de JSON sur stdout, succès ou échec: le widget (ou tout
    # autre appelant programmatique) n'a qu'un seul flux à lire, jamais besoin de choisir
    # entre stdout et stderr selon le cas.
    print(json.dumps(result, ensure_ascii=False))
    if result.get("status") != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
