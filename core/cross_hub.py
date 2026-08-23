# SPDX-License-Identifier: GPL-3.0-or-later
"""Cross-hub handoff files (Utilitaires → Dev textdiff)."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _handoff_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    path = base / "Mr-Aurevo-X" / "cross-hub"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pending_textdiff_path() -> Path:
    return _handoff_dir() / "pending-textdiff.json"


def write_pending_textdiff(paths: list[Path]) -> None:
    payload = {"paths": [str(p) for p in paths if p.exists()]}
    pending_textdiff_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_pending_textdiff() -> list[Path]:
    path = pending_textdiff_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    out: list[Path] = []
    for raw in data.get("paths") or []:
        p = Path(str(raw)).expanduser()
        if p.is_file():
            out.append(p)
    return out


def clear_pending_textdiff() -> None:
    path = pending_textdiff_path()
    if path.is_file():
        path.unlink()
