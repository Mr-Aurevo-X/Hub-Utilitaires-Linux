# SPDX-License-Identifier: GPL-3.0-or-later
"""Append-only local log for destructive operations."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_BYTES = 1_048_576


def _log_path() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = base / "hub-utilitaires"
    path.mkdir(parents=True, exist_ok=True)
    return path / "ops.log"


def append(action: str, **fields: Any) -> None:
    path = _log_path()
    payload = {
        "ts": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": action,
        **fields,
    }
    line = json.dumps(payload, ensure_ascii=False) + "\n"
    try:
        if path.is_file() and path.stat().st_size > _MAX_BYTES:
            backup = path.with_suffix(".log.old")
            path.replace(backup)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        return


def read_tail(*, max_lines: int = 200) -> str:
    path = _log_path()
    if not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[-max(1, min(max_lines, 2000)) :])
