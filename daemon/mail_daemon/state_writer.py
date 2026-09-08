"""Écriture atomique de l'état lu par le widget: jamais de fichier tronqué en cas de crash."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any


def write_state(path: Path, threads: list[dict[str, Any]]) -> None:
    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "threads": threads,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)
