# SPDX-License-Identifier: GPL-3.0-or-later
"""Named local text snippets. Not a clipboard history."""

from __future__ import annotations

import json
import os
from pathlib import Path


class SnippetError(Exception):
    pass


def _data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    path = base / "hub-utilitaires"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _store_path() -> Path:
    return _data_dir() / "snippets.json"


def _load() -> list[dict[str, str]]:
    path = _store_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out.append({"name": name, "text": str(item.get("text") or ""), "tags": str(item.get("tags") or "")})
    return out


def _save(rows: list[dict[str, str]]) -> None:
    _store_path().write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def list_all() -> list[dict[str, str]]:
    return _load()


def get(name: str) -> str:
    key = (name or "").strip()
    for item in _load():
        if item["name"] == key:
            return item["text"]
    raise SnippetError(f"snippet introuvable : {name}")


def put(name: str, text: str, *, tags: str = "") -> None:
    key = (name or "").strip()
    if not key:
        raise SnippetError("nom vide")
    rows = [item for item in _load() if item["name"] != key]
    rows.append({"name": key, "text": text if text is not None else "", "tags": tags.strip()})
    rows.sort(key=lambda item: item["name"].lower())
    _save(rows)


def export_json() -> str:
    return json.dumps(_load(), indent=2, ensure_ascii=False) + "\n"


def import_json(payload: str) -> int:
    try:
        raw = json.loads(payload or "[]")
    except json.JSONDecodeError as exc:
        raise SnippetError(str(exc)) from exc
    if not isinstance(raw, list):
        raise SnippetError("JSON invalide")
    rows = _load()
    names = {item["name"] for item in rows}
    added = 0
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name or name in names:
            continue
        rows.append(
            {
                "name": name,
                "text": str(item.get("text") or ""),
                "tags": str(item.get("tags") or ""),
            }
        )
        names.add(name)
        added += 1
    rows.sort(key=lambda item: item["name"].lower())
    _save(rows)
    return added


def filter_by_tag(tag: str) -> list[dict[str, str]]:
    needle = (tag or "").strip().lower()
    if not needle:
        return _load()
    return [item for item in _load() if needle in str(item.get("tags") or "").lower()]


def delete(name: str) -> None:
    key = (name or "").strip()
    rows = [item for item in _load() if item["name"] != key]
    if len(rows) == len(_load()) and key:
        loaded = _load()
        if not any(item["name"] == key for item in loaded):
            raise SnippetError(f"snippet introuvable : {name}")
    _save(rows)
