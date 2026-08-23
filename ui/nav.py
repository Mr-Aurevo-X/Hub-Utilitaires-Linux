# SPDX-License-Identifier: GPL-3.0-or-later
"""Grouped collapsible sidebar navigation (Hub-Système pattern)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from core import i18n
from core import settings as app_settings

_DEFAULT_EXPANDED = True
PAGE_KEYS = app_settings.PAGE_KEYS


@dataclass(frozen=True)
class NavPage:
    key: str
    icon: str


@dataclass(frozen=True)
class NavGroup:
    group_id: str
    pages: tuple[NavPage, ...]


def nav_groups() -> tuple[NavGroup, ...]:
    return (
        NavGroup(
            "explorer",
            (
                NavPage("find", "system-search-symbolic"),
                NavPage("rename", "document-edit-symbolic"),
                NavPage("lots", "view-list-symbolic"),
                NavPage("disk", "drive-multiple-symbolic"),
            ),
        ),
        NavGroup(
            "media",
            (
                NavPage("hash", "encryption-symbolic"),
                NavPage("resize", "image-x-generic-symbolic"),
                NavPage("pdf", "x-office-document-symbolic"),
            ),
        ),
        NavGroup(
            "filetools",
            (NavPage("file", "text-x-generic-symbolic"),),
        ),
        NavGroup(
            "studio",
            (
                NavPage("color", "color-select-symbolic"),
                NavPage("atelier", "applications-engineering-symbolic"),
            ),
        ),
    )


def _group_label(group_id: str) -> str:
    return i18n.t(f"nav_{group_id}")


def nav_pages() -> tuple[tuple[str, str], ...]:
    return tuple((page.key, page.key) for group in nav_groups() for page in group.pages)


def flat_nav_items() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for group in nav_groups():
        for page in group.pages:
            out.append((page.key, i18n.t(page.key), page.icon))
    return out


def page_titles() -> dict[str, str]:
    return {key: label for key, label, _icon in flat_nav_items()}


def group_for_page(page_key: str) -> str | None:
    for group in nav_groups():
        for page in group.pages:
            if page.key == page_key:
                return group.group_id
    return None


def validate_nav_registry() -> None:
    flat = [page.key for group in nav_groups() for page in group.pages]
    if set(flat) != set(PAGE_KEYS):
        missing = set(PAGE_KEYS) - set(flat)
        extra = set(flat) - set(PAGE_KEYS)
        raise RuntimeError(f"nav registry mismatch missing={missing!r} extra={extra!r}")


class NavSidebar:
    """Collapsible group sidebar with one ListBox per group."""

    def __init__(
        self,
        *,
        settings: dict[str, Any],
        on_page_selected: Callable[[str], None],
        on_groups_changed: Callable[[dict[str, bool]], None] | None = None,
    ) -> None:
        self._settings = settings
        self._on_page_selected = on_page_selected
        self._on_groups_changed = on_groups_changed
        self._page_lists: dict[str, Gtk.ListBox] = {}
        self._revealers: dict[str, Gtk.Revealer] = {}
        self._chevrons: dict[str, Gtk.Image] = {}
        self._group_labels: dict[str, Gtk.Label] = {}
        self._page_labels: dict[str, Gtk.Label] = {}
        self._selecting = False
        self._expanded: dict[str, bool] = self._load_expanded()
        self.widget = self._build()

    def _load_expanded(self) -> dict[str, bool]:
        raw = self._settings.get("nav_groups_expanded")
        if not isinstance(raw, dict):
            return {group.group_id: _DEFAULT_EXPANDED for group in nav_groups()}
        out: dict[str, bool] = {}
        for group in nav_groups():
            val = raw.get(group.group_id)
            out[group.group_id] = _DEFAULT_EXPANDED if val is None else bool(val)
        return out

    def _persist_expanded(self) -> None:
        if self._on_groups_changed is not None:
            self._on_groups_changed(dict(self._expanded))

    def _set_revealed(self, group_id: str, revealed: bool) -> None:
        self._expanded[group_id] = revealed
        revealer = self._revealers.get(group_id)
        if revealer is not None:
            revealer.set_reveal_child(revealed)
        chevron = self._chevrons.get(group_id)
        if chevron is not None:
            chevron.set_from_icon_name("pan-down-symbolic" if revealed else "pan-end-symbolic")
        self._persist_expanded()

    def _toggle_group(self, group_id: str) -> None:
        self._set_revealed(group_id, not self._expanded.get(group_id, _DEFAULT_EXPANDED))

    def _ensure_group_open_for_page(self, page_key: str) -> None:
        group_id = group_for_page(page_key)
        if group_id is not None:
            self._set_revealed(group_id, True)

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if self._selecting or row is None:
            return
        key = row.get_name()
        if key:
            self._on_page_selected(key)

    def _build(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root.add_css_class("nav-sidebar-root")

        for group in nav_groups():
            header_btn = Gtk.Button()
            header_btn.add_css_class("flat")
            header_btn.add_css_class("nav-group-header")
            header_btn.set_has_frame(False)
            hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hbox.set_margin_start(4)
            hbox.set_margin_end(8)
            hbox.set_margin_top(6)
            hbox.set_margin_bottom(2)
            chevron = Gtk.Image.new_from_icon_name(
                "pan-down-symbolic" if self._expanded.get(group.group_id, True) else "pan-end-symbolic"
            )
            chevron.set_valign(Gtk.Align.CENTER)
            label = Gtk.Label(label=_group_label(group.group_id), xalign=0)
            label.set_hexpand(True)
            label.add_css_class("heading")
            hbox.append(chevron)
            hbox.append(label)
            header_btn.set_child(hbox)
            group_id = group.group_id
            header_btn.connect("clicked", lambda *_args, gid=group_id: self._toggle_group(gid))
            root.append(header_btn)
            self._chevrons[group_id] = chevron
            self._group_labels[group_id] = label

            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
            listbox.add_css_class("navigation-sidebar")
            listbox.add_css_class("sidebar-nav")
            listbox.add_css_class("nav-subitem")
            listbox.connect("row-selected", self._on_row_selected)

            for page in group.pages:
                row = Gtk.ListBoxRow()
                row.set_name(page.key)
                box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                box.set_margin_start(16)
                box.set_margin_end(8)
                box.set_margin_top(4)
                box.set_margin_bottom(4)
                icon = Gtk.Image.new_from_icon_name(page.icon)
                text = Gtk.Label(label=i18n.t(page.key), xalign=0)
                text.set_hexpand(True)
                self._page_labels[page.key] = text
                box.append(icon)
                box.append(text)
                row.set_child(box)
                listbox.append(row)

            self._page_lists[group_id] = listbox
            revealer = Gtk.Revealer()
            revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            revealer.set_reveal_child(self._expanded.get(group_id, _DEFAULT_EXPANDED))
            revealer.set_child(listbox)
            self._revealers[group_id] = revealer
            root.append(revealer)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        scroll.set_child(root)
        return scroll

    def select_page(self, page_key: str, *, notify: bool = True) -> None:
        self._ensure_group_open_for_page(page_key)
        self._selecting = True
        try:
            for listbox in self._page_lists.values():
                listbox.unselect_all()
            for listbox in self._page_lists.values():
                idx = 0
                while True:
                    row = listbox.get_row_at_index(idx)
                    if row is None:
                        break
                    if row.get_name() == page_key:
                        listbox.select_row(row)
                        if notify:
                            self._on_page_selected(page_key)
                        return
                    idx += 1
        finally:
            self._selecting = False

    def relabel(self) -> None:
        for group_id, label in self._group_labels.items():
            label.set_text(_group_label(group_id))
        for key, label in self._page_labels.items():
            label.set_text(i18n.t(key))

    def rebuild_labels(self) -> None:
        self.relabel()

    def update_settings(self, settings: dict[str, Any]) -> None:
        self._settings = settings
        self._expanded = self._load_expanded()
        for group_id, revealer in self._revealers.items():
            revealed = self._expanded.get(group_id, _DEFAULT_EXPANDED)
            revealer.set_reveal_child(revealed)
            chevron = self._chevrons.get(group_id)
            if chevron is not None:
                chevron.set_from_icon_name("pan-down-symbolic" if revealed else "pan-end-symbolic")
