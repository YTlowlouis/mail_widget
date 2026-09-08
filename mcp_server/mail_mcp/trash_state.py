"""Mémorise le dossier d'origine d'un mail mis à la corbeille, pour permettre restore().

État local au serveur MCP, séparé du cache SQLite du daemon (résumés/classification).
Écriture atomique (fichier temporaire + os.replace) pour ne jamais laisser un fichier tronqué.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "mail-mcp"


class TrashState:
    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            self._path = path
        else:
            state_dir = Path(os.environ.get("MAIL_MCP_STATE_DIR", DEFAULT_STATE_DIR))
            state_dir.mkdir(parents=True, exist_ok=True)
            self._path = state_dir / "trash_state.json"

    def _read(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, str]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp_path, self._path)

    def remember(self, message_id: str, origin_folder: str) -> None:
        data = self._read()
        data[message_id] = origin_folder
        self._write(data)

    def origin_of(self, message_id: str) -> str | None:
        return self._read().get(message_id)

    def forget(self, message_id: str) -> None:
        data = self._read()
        if message_id in data:
            del data[message_id]
            self._write(data)
