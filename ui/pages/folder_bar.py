# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import i18n
from core import settings as app_settings
from ui import compat
from . import common as pages_common


class FolderBar:
    def __init__(
        self,
        window: Gtk.Window,
        settings: dict[str, Any],
        on_folder: Callable[[Path], None] | None = None,
    ) -> None:
        self._window = window
        self._settings = settings
        self._on_folder = on_folder
        self._entry = Gtk.Entry()
        self._entry.set_hexpand(True)
        self._entry.set_text(self._initial())
        pick = Gtk.Button()
        common.bind_i18n(pick, "pick_folder", "label")
        pick.connect("clicked", lambda *_: compat.select_folder(self._window, self.set_folder))
        self._entry.connect("activate", lambda *_: self.set_folder(self.folder()))
        self._pick = pick
        self._recent_btn = Gtk.MenuButton()
        self._recent_btn.set_icon_name("document-open-recent-symbolic")
        common.bind_i18n(self._recent_btn, "folder_recent", "tooltip")
        self._menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        popover = Gtk.Popover()
        popover.set_child(self._menu_box)
        self._recent_btn.set_popover(popover)
        self._fav_btn = Gtk.Button(icon_name="starred-symbolic")
        common.bind_i18n(self._fav_btn, "folder_favorite", "tooltip")
        self._fav_btn.connect("clicked", self._toggle_favorite)
        row = Gtk.Box(spacing=8)
        row.append(self._entry)
        row.append(self._recent_btn)
        row.append(self._fav_btn)
        row.append(pick)
        self.widget = row
        self._rebuild_recent_menu()

    def _initial(self) -> str:
        raw = str(self._settings.get("last_folder") or "").strip()
        if raw:
            return raw
        return str(Path.home())

    def folder(self) -> Path:
        raw = self._entry.get_text().strip() or str(Path.home())
        return Path(raw).expanduser()

    def _rebuild_recent_menu(self) -> None:
        child = self._menu_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._menu_box.remove(child)
            child = nxt
        favorites = app_settings.favorite_folders(self._settings)
        recents = app_settings.recent_folders(self._settings)
        if favorites:
            self._menu_box.append(Gtk.Label(label=i18n.t("folder_favorites"), xalign=0, margin_start=8))
            for path in favorites:
                btn = Gtk.Button(label=path)
                btn.add_css_class("flat")
                btn.connect("clicked", lambda *_a, p=path: self.set_folder(Path(p)))
                self._menu_box.append(btn)
        if recents:
            self._menu_box.append(Gtk.Label(label=i18n.t("folder_recent"), xalign=0, margin_start=8))
            for path in recents:
                btn = Gtk.Button(label=path)
                btn.add_css_class("flat")
                btn.connect("clicked", lambda *_a, p=path: self.set_folder(Path(p)))
                self._menu_box.append(btn)
        if not favorites and not recents:
            self._menu_box.append(Gtk.Label(label=i18n.t("folder_empty"), margin_top=8, margin_bottom=8, margin_start=8, margin_end=8))

    def _toggle_favorite(self, *_args: object) -> None:
        folder = str(self.folder())
        favs = app_settings.favorite_folders(self._settings)
        if folder in favs:
            favs = [p for p in favs if p != folder]
        else:
            favs = [folder] + favs
        self._settings["favorite_folders"] = favs[:20]
        app_settings.save_settings(self._settings)
        self._rebuild_recent_menu()

    def set_folder(self, path: Path, *, notify: bool = True) -> None:
        resolved = Path(path).expanduser()
        self._entry.set_text(str(resolved))
        app_settings.remember_folder(self._settings, str(resolved))
        self._rebuild_recent_menu()
        if notify and self._on_folder is not None:
            self._on_folder(resolved)

    def relabel(self) -> None:
        common.relabel_tree(self.widget)
        self._rebuild_recent_menu()
