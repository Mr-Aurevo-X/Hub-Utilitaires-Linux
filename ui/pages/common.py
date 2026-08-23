# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from core import i18n
from ui.helpers import show_toast


def clear_list(box: Gtk.ListBox) -> None:
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


def scrolled(child: Gtk.Widget) -> Gtk.ScrolledWindow:
    sc = Gtk.ScrolledWindow()
    sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    sc.set_vexpand(True)
    sc.set_child(child)
    return sc


def padded(child: Gtk.Widget) -> Gtk.Widget:
    child.set_margin_top(12)
    child.set_margin_bottom(12)
    child.set_margin_start(16)
    child.set_margin_end(16)
    return child


def copy_text(text: str, toast: Gtk.Widget | None = None) -> None:
    display = Gdk.Display.get_default()
    if display is None:
        return
    clip = display.get_clipboard()
    setter = getattr(clip, "set", None)
    try:
        if callable(setter):
            setter(text)
        else:
            clip.set_content(Gdk.ContentProvider.new_for_value(text))
    except (TypeError, GLib.Error):
        clip.set_content(Gdk.ContentProvider.new_for_value(text))
    if toast is not None:
        show_toast(toast, i18n.t("copied"))


def gio_paths(files: Gio.ListModel | None) -> list[Path]:
    if files is None:
        return []
    paths: list[Path] = []
    for i in range(files.get_n_items()):
        item = files.get_item(i)
        if isinstance(item, Gio.File) and item.get_path():
            paths.append(Path(item.get_path()))
    return paths


def action_row(title: str, button: Gtk.Widget, subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    button.set_valign(Gtk.Align.CENTER)
    row.add_suffix(button)
    return row


def prefs_group(title: str, rows: list[Gtk.Widget], description: str = "") -> Adw.PreferencesGroup:
    group = Adw.PreferencesGroup(title=title, description=description)
    for row in rows:
        group.add(row)
    return group


def button_row(title: str, handler: Callable[..., object], *, suggested: bool = False) -> Adw.ActionRow:
    btn = Gtk.Button(label=title)
    if suggested:
        btn.add_css_class("suggested-action")
    btn.connect("clicked", handler)
    return action_row(title, btn)


def wrap_prefs(*groups: Adw.PreferencesGroup) -> Gtk.Widget:
    page = Adw.PreferencesPage()
    for group in groups:
        page.add(group)
    return page
