# SPDX-License-Identifier: GPL-3.0-or-later
"""Local preferences (no network)."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from core.paths import config_dir, settings_path

DEFAULTS: dict[str, Any] = {
    "language": "fr",
    "language_chosen": False,
    "auto_update_on_startup": True,
    "find_max_results": 400,
    "last_folder": "",
    "last_page": "find",
}

NAV_GROUP_IDS = (
    "explorer",
    "media",
    "filetools",
    "studio",
)

_LEGACY_NAV_SECTION_KEYS = (
    "nav_explorer",
    "nav_media",
    "nav_filetools",
    "nav_studio",
)

_DEFAULT_NAV_GROUPS_EXPANDED: dict[str, bool] = {
    "explorer": True,
    "media": False,
    "filetools": False,
    "studio": False,
}

_LEGACY_SECTION_TO_GROUP = {
    "nav_explorer": "explorer",
    "nav_media": "media",
    "nav_filetools": "filetools",
    "nav_studio": "studio",
}

PAGE_KEYS = (
    "find",
    "color",
    "atelier",
    "rename",
    "hash",
    "resize",
    "pdf",
    "file",
    "lots",
    "disk",
)


def search_limit(settings: dict[str, Any] | None = None) -> int:
    raw = DEFAULTS["find_max_results"] if settings is None else settings.get("find_max_results", 400)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 400
    return max(1, min(value, 20_000))


def coerce_page(value: object) -> str:
    key = str(value or "find").strip()
    if key == "prefs":
        return "find"
    return key if key in PAGE_KEYS else "find"


def _group_for_page(page_key: str) -> str:
    from ui.nav import group_for_page

    return group_for_page(page_key) or NAV_GROUP_IDS[0]


def _migrate_legacy_nav_expanded(raw: object) -> dict[str, bool]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, bool] = {}
    for legacy_key, group_id in _LEGACY_SECTION_TO_GROUP.items():
        if legacy_key in raw:
            out[group_id] = bool(raw[legacy_key])
    return out


def nav_groups_expanded(settings: dict[str, Any] | None, page_key: str = "find") -> dict[str, bool]:
    data = deepcopy(_DEFAULT_NAV_GROUPS_EXPANDED)
    raw = None if settings is None else settings.get("nav_groups_expanded")
    if not isinstance(raw, dict):
        raw = _migrate_legacy_nav_expanded(None if settings is None else settings.get("nav_expanded"))
    if isinstance(raw, dict):
        for group_id in NAV_GROUP_IDS:
            if group_id in raw:
                data[group_id] = bool(raw[group_id])
    if not isinstance(settings, dict) or (
        "nav_groups_expanded" not in settings and "nav_expanded" not in settings
    ):
        data[_group_for_page(coerce_page(page_key))] = True
    return data


def save_nav_groups_expanded(settings: dict[str, Any], state: dict[str, bool]) -> None:
    merged = {
        group_id: bool(state.get(group_id, _DEFAULT_NAV_GROUPS_EXPANDED[group_id]))
        for group_id in NAV_GROUP_IDS
    }
    settings["nav_groups_expanded"] = merged
    save_settings(settings)


def recent_folders(settings: dict[str, Any] | None) -> list[str]:
    raw = [] if settings is None else settings.get("recent_folders")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out[:10]


def favorite_folders(settings: dict[str, Any] | None) -> list[str]:
    raw = [] if settings is None else settings.get("favorite_folders")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def favorite_searches(settings: dict[str, Any] | None) -> list[dict[str, str]]:
    raw = [] if settings is None else settings.get("favorite_searches")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        row = {
            "folder": str(item.get("folder") or "").strip(),
            "query": str(item.get("query") or "").strip(),
            "content": str(item.get("content") or "").strip(),
        }
        key = (row["folder"], row["query"], row["content"])
        if not any(key) or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out[:20]


def toggle_favorite_search(
    settings: dict[str, Any],
    *,
    folder: str,
    query: str,
    content: str,
) -> list[dict[str, str]]:
    row = {
        "folder": str(folder or "").strip(),
        "query": str(query or "").strip(),
        "content": str(content or "").strip(),
    }
    favs = favorite_searches(settings)
    key = (row["folder"], row["query"], row["content"])
    if not any(key):
        settings["favorite_searches"] = favs
        return favs
    exists = any(
        (item["folder"], item["query"], item["content"]) == key for item in favs
    )
    if exists:
        favs = [item for item in favs if (item["folder"], item["query"], item["content"]) != key]
    else:
        favs = [row, *favs]
    settings["favorite_searches"] = favs[:20]
    return favorite_searches(settings)


def remember_folder(settings: dict[str, Any], path: str) -> None:
    folder = str(path or "").strip()
    if not folder:
        return
    recents = [folder] + [p for p in recent_folders(settings) if p != folder]
    settings["recent_folders"] = recents[:10]
    settings["last_folder"] = folder
    save_settings(settings)


def coerce_language(value: object) -> str:
    raw = str(value or "fr").strip().lower().replace("_", "-")
    code = raw.split("-", 1)[0]
    return code if code in {"fr", "en"} else "fr"


def needs_language_prompt(settings: dict[str, Any] | None = None) -> bool:
    if settings is None:
        return True
    return not bool(settings.get("language_chosen"))


def load_settings() -> dict[str, Any]:
    data = deepcopy(DEFAULTS)
    path = settings_path()
    if not path.exists():
        return data
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return data
    if not isinstance(raw, dict):
        return data
    merged = {k: v for k, v in raw.items() if k in DEFAULTS}
    if not str(merged.get("last_folder") or "").strip():
        legacy = raw.get("find_root")
        if isinstance(legacy, str) and legacy.strip():
            merged["last_folder"] = legacy
    data.update(merged)
    data["last_page"] = coerce_page(data.get("last_page"))
    data["language"] = coerce_language(data.get("language"))
    data["language_chosen"] = bool(raw.get("language_chosen", False))
    data["find_max_results"] = search_limit(data)
    merged_nav = {**data, "nav_groups_expanded": raw.get("nav_groups_expanded"), "nav_expanded": raw.get("nav_expanded")}
    data["nav_groups_expanded"] = nav_groups_expanded(merged_nav, str(data.get("last_page") or "find"))
    data["recent_folders"] = recent_folders(raw)
    data["favorite_folders"] = favorite_folders(raw)
    data["favorite_searches"] = favorite_searches(raw)
    return data


def save_settings(settings: dict[str, Any]) -> None:
    merged = deepcopy(DEFAULTS)
    merged.update({k: v for k, v in settings.items() if k in DEFAULTS})
    merged["last_page"] = coerce_page(merged.get("last_page"))
    merged["language"] = coerce_language(merged.get("language"))
    merged["language_chosen"] = bool(settings.get("language_chosen"))
    merged["find_max_results"] = search_limit(merged)
    payload: dict[str, Any] = dict(merged)
    payload["nav_groups_expanded"] = nav_groups_expanded(settings, str(merged.get("last_page") or "find"))
    payload["recent_folders"] = recent_folders(settings)
    payload["favorite_folders"] = favorite_folders(settings)
    payload["favorite_searches"] = favorite_searches(settings)
    settings_path().write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
