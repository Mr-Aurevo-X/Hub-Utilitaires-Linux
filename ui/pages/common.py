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


def _i18n_key(title_or_key: str) -> str | None:
    return title_or_key if title_or_key in i18n._FR else None


def apply_i18n(widget: Gtk.Widget) -> None:
    key = getattr(widget, "_hu_i18n_key", None)
    kind = getattr(widget, "_hu_i18n_kind", "label")
    if not key:
        return
    text = i18n.t(key)
    if kind == "label":
        widget.set_label(text)
        return
    if kind == "title":
        widget.set_title(text)
        return
    if kind == "subtitle":
        widget.set_subtitle(text)
        return
    if kind == "description":
        widget.set_description(text)
        return
    if kind == "placeholder":
        widget.set_placeholder_text(text)
        return
    if kind == "tooltip":
        widget.set_tooltip_text(text)


def bind_i18n(widget: Gtk.Widget, key: str, kind: str = "label") -> Gtk.Widget:
    widget._hu_i18n_key = key
    widget._hu_i18n_kind = kind
    apply_i18n(widget)
    return widget


def relabel_tree(root: Gtk.Widget) -> None:
    apply_i18n(root)
    getter = getattr(root, "get_first_child", None)
    if not callable(getter):
        return
    child = getter()
    while child is not None:
        relabel_tree(child)
        child = child.get_next_sibling()


def relabel_stack(stack: Gtk.Widget, titles: tuple[tuple[str, str], ...]) -> None:
    get_child = getattr(stack, "get_child_by_name", None)
    get_page = getattr(stack, "get_page", None)
    if not callable(get_child) or not callable(get_page):
        return
    for name, key in titles:
        child = get_child(name)
        if child is None:
            continue
        page = get_page(child)
        setter = getattr(page, "set_title", None)
        if callable(setter):
            setter(i18n.t(key))


def t_button(key: str) -> Gtk.Button:
    btn = Gtk.Button()
    bind_i18n(btn, key, "label")
    return btn


def t_label(key: str, **kwargs: object) -> Gtk.Label:
    lab = Gtk.Label(**kwargs)
    bind_i18n(lab, key, "label")
    return lab


def t_check(key: str) -> Gtk.CheckButton:
    btn = Gtk.CheckButton()
    bind_i18n(btn, key, "label")
    return btn


def t_entry(key: str, **kwargs: object) -> Gtk.Entry:
    entry = Gtk.Entry(**kwargs)
    bind_i18n(entry, key, "placeholder")
    return entry


def t_expander(key: str) -> Gtk.Expander:
    exp = Gtk.Expander()
    bind_i18n(exp, key, "label")
    return exp


def action_row(title: str, button: Gtk.Widget, subtitle: str = "") -> Adw.ActionRow:
    key = _i18n_key(title)
    label = i18n.t(title) if key else title
    sub_key = _i18n_key(subtitle) if subtitle else None
    sub = i18n.t(subtitle) if sub_key else subtitle
    row = Adw.ActionRow(title=label, subtitle=sub)
    if key:
        bind_i18n(row, key, "title")
    if sub_key:
        bind_i18n(row, sub_key, "subtitle")
    button.set_valign(Gtk.Align.CENTER)
    row.add_suffix(button)
    return row


def prefs_group(title: str, rows: list[Gtk.Widget], description: str = "") -> Adw.PreferencesGroup:
    key = _i18n_key(title)
    label = i18n.t(title) if key else title
    desc_key = _i18n_key(description) if description else None
    desc = i18n.t(description) if desc_key else description
    group = Adw.PreferencesGroup(title=label, description=desc)
    if key:
        bind_i18n(group, key, "title")
    if desc_key:
        bind_i18n(group, desc_key, "description")
    for row in rows:
        group.add(row)
    return group


def button_row(title: str, handler: Callable[..., object], *, suggested: bool = False) -> Adw.ActionRow:
    key = _i18n_key(title)
    label = i18n.t(title) if key else title
    btn = Gtk.Button(label=label)
    if key:
        bind_i18n(btn, key, "label")
    if suggested:
        btn.add_css_class("suggested-action")
    btn.connect("clicked", handler)
    return action_row(title, btn)


def relabel_page(page: object) -> None:
    widget = getattr(page, "widget", None)
    if widget is not None:
        relabel_tree(widget)
    bar = getattr(page, "_bar", None)
    bar_relabel = getattr(bar, "relabel", None) if bar is not None else None
    if callable(bar_relabel):
        bar_relabel()
    stack = getattr(page, "_stack", None)
    titles = getattr(page, "_tab_titles", None)
    if stack is not None and titles:
        relabel_stack(stack, titles)


def wrap_prefs(*groups: Adw.PreferencesGroup) -> Gtk.Widget:
    page = Adw.PreferencesPage()
    for group in groups:
        page.add(group)
    return page
