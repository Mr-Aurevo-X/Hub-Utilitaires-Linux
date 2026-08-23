# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK 4.6 / libadwaita 1.1 fallbacks (Linux Mint 21.3 / Ubuntu 22.04)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Adw, Gdk, Gio, GLib, Gtk


def set_bin_child(widget: Gtk.Widget, child: Gtk.Widget) -> None:
    for name in ("set_content", "set_child"):
        fn = getattr(widget, name, None)
        if callable(fn):
            fn(child)
            return
    raise RuntimeError("ni set_content ni set_child")


def toolbar_view(header: Gtk.Widget, body: Gtk.Widget) -> Gtk.Widget:
    cls = getattr(Adw, "ToolbarView", None)
    if cls is not None:
        view = cls()
        view.add_top_bar(header)
        view.set_content(body)
        return view
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.append(header)
    body.set_vexpand(True)
    box.append(body)
    return box


def split_view(sidebar: Gtk.Widget, content: Gtk.Widget, title: str) -> Gtk.Widget:
    split_cls = getattr(Adw, "NavigationSplitView", None)
    page_cls = getattr(Adw, "NavigationPage", None)
    if split_cls is not None and page_cls is not None:
        split = split_cls()
        set_min = getattr(split, "set_min_sidebar_width", None)
        if callable(set_min):
            set_min(220)
        split.set_sidebar(page_cls(child=sidebar, title=title))
        split.set_content(page_cls(child=content, title=title))
        return split
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    sidebar.set_size_request(220, -1)
    content.set_hexpand(True)
    content.set_vexpand(True)
    box.append(sidebar)
    box.append(content)
    return box


def load_css_data(provider: Gtk.CssProvider, css: str) -> None:
    raw = css.encode("utf-8")
    attempts = (
        lambda: provider.load_from_data(raw),
        lambda: provider.load_from_string(css),
        lambda: provider.load_from_data(css, -1),
        lambda: provider.load_from_data(raw, len(raw)),
        lambda: provider.load_from_data(css, len(css)),
    )
    for attempt in attempts:
        try:
            attempt()
            return
        except (TypeError, AttributeError, OverflowError, ValueError, GLib.Error):
            continue
    raise RuntimeError("CssProvider.load_from_data indisponible")


def view_switcher_stack() -> tuple[Gtk.Widget, Any]:
    """Switcher + stack with add_titled(). Adw.ViewStack is 1.4+; Mint 21.3 has 1.1."""
    view_stack_cls = getattr(Adw, "ViewStack", None)
    switcher_cls = getattr(Adw, "ViewSwitcher", None)
    if view_stack_cls is not None and switcher_cls is not None:
        stack = view_stack_cls()
        switcher = switcher_cls()
        switcher.set_stack(stack)
        policy = getattr(Adw, "ViewSwitcherPolicy", None)
        setter = getattr(switcher, "set_policy", None)
        if policy is not None and callable(setter):
            setter(policy.WIDE)
        return switcher_scroll_bar(switcher), stack
    stack = Gtk.Stack()
    if switcher_cls is not None:
        switcher = switcher_cls()
        switcher.set_stack(stack)
        return switcher_scroll_bar(switcher), stack
    switcher = Gtk.StackSwitcher()
    switcher.set_stack(stack)
    return switcher_scroll_bar(switcher), stack


def switcher_scroll_bar(switcher: Gtk.Widget) -> Gtk.Widget:
    """Horizontal scroll so tabs (e.g. Atelier → Données) stay reachable on narrow windows."""
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
    scroll.set_propagate_natural_width(True)
    scroll.set_child(switcher)
    return scroll


def open_external_uri(uri: str) -> None:
    try:
        Gio.AppInfo.launch_default_for_uri(uri, None)
    except GLib.Error:
        show = getattr(Gtk, "show_uri", None)
        if callable(show):
            show(None, uri, Gdk.CURRENT_TIME)


def present_about(
    parent: Gtk.Window,
    *,
    application_name: str,
    version: str,
    developer_name: str,
    copyright_line: str,
    comments: str,
    website: str,
    issue_url: str | None = None,
    license_type: Any = None,
    legal_title: str | None = None,
    legal_copyright: str | None = None,
    legal_text: str | None = None,
) -> None:
    about_cls = getattr(Adw, "AboutDialog", None) or getattr(Adw, "AboutWindow", None)
    if about_cls is None:
        win = Gtk.Window(transient_for=parent, modal=True, title=application_name)
        win.set_default_size(420, 320)
        header = Adw.HeaderBar()
        close_btn = Gtk.Button(label="OK")
        close_btn.add_css_class("suggested-action")
        close_btn.connect("clicked", lambda *_: win.close())
        header.pack_end(close_btn)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_start(18)
        box.set_margin_end(18)
        box.set_margin_top(12)
        box.set_margin_bottom(18)
        for line in (application_name, version, copyright_line, comments, developer_name):
            lbl = Gtk.Label(label=line, wrap=True, xalign=0)
            box.append(lbl)
        set_bin_child(win, toolbar_view(header, box))
        win.present()
        return

    dialog = about_cls()
    for name, value in (
        ("set_application_name", application_name),
        ("set_version", version),
        ("set_developer_name", developer_name),
        ("set_copyright", copyright_line),
        ("set_comments", comments),
        ("set_website", website),
        ("set_issue_url", issue_url),
    ):
        if value is None:
            continue
        fn = getattr(dialog, name, None)
        if callable(fn):
            try:
                fn(value)
            except TypeError:
                pass
    devs = getattr(dialog, "set_developers", None)
    if callable(devs):
        try:
            devs([developer_name])
        except TypeError:
            pass
    if license_type is not None:
        setter = getattr(dialog, "set_license_type", None)
        if callable(setter):
            setter(license_type)
    add_legal = getattr(dialog, "add_legal_section", None)
    if callable(add_legal) and legal_title and legal_text:
        try:
            add_legal(
                legal_title,
                legal_copyright or copyright_line,
                getattr(Gtk.License, "CUSTOM", Gtk.License.UNKNOWN),
                legal_text,
            )
        except (TypeError, ValueError):
            pass
    present = getattr(dialog, "present", None)
    if callable(present):
        try:
            present(parent)
        except TypeError:
            present()


def present_donate(parent: Gtk.Window, url: str, heading: str, body: str) -> None:
    from core import i18n

    alert_cls = getattr(Adw, "AlertDialog", None)
    if alert_cls is not None:
        dialog = alert_cls(heading=heading, body=body)
        dialog.add_response("later", i18n.t("don_later"))
        dialog.add_response("open", i18n.t("don_open"))
        appearance = getattr(Adw, "ResponseAppearance", None)
        if appearance is not None:
            dialog.set_response_appearance("open", appearance.SUGGESTED)
        dialog.set_default_response("open")
        dialog.set_close_response("later")

        def on_response(_dlg: object, response: str) -> None:
            if response == "open":
                open_external_uri(url)

        choose = getattr(dialog, "choose", None)
        if callable(choose):
            choose(parent, None, on_response)
        return

    win = Gtk.Window(transient_for=parent, modal=True, title=heading)
    win.set_default_size(480, 320)
    header = Adw.HeaderBar()
    header.set_title_widget(Gtk.Label(label="$"))
    close_btn = Gtk.Button(label="OK")
    close_btn.connect("clicked", lambda *_: win.close())
    header.pack_end(close_btn)
    open_btn = Gtk.Button(label=i18n.t("don_open"))
    open_btn.add_css_class("suggested-action")
    open_btn.connect("clicked", lambda *_: (open_external_uri(url), win.close()))
    header.pack_end(open_btn)
    body_lbl = Gtk.Label(label=body, wrap=True, xalign=0)
    body_lbl.set_margin_start(16)
    body_lbl.set_margin_end(16)
    body_lbl.set_margin_top(12)
    body_lbl.set_margin_bottom(12)
    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    scroll.set_vexpand(True)
    set_bin_child(scroll, body_lbl)
    set_bin_child(win, toolbar_view(header, scroll))
    win.present()


def present_startup_error(message: str, on_close: Callable[[], None] | None = None) -> bool:
    try:
        dialog = Gtk.MessageDialog(modal=True, message_type=Gtk.MessageType.ERROR, text="Hub Utilitaires")
        try:
            dialog.set_property("secondary-text", message)
        except (TypeError, GLib.Error):
            extra = Gtk.Label(label=message, wrap=True, xalign=0)
            dialog.get_content_area().append(extra)
        dialog.add_button("OK", int(Gtk.ResponseType.CLOSE))

        def on_resp(dlg: Gtk.MessageDialog, *_args: object) -> None:
            dlg.destroy()
            if on_close is not None:
                on_close()

        dialog.connect("response", on_resp)
        dialog.present()
        return True
    except Exception:  # noqa: BLE001
        return False


def string_choice(labels: list[str]) -> Gtk.Widget:
    factory = getattr(Gtk.DropDown, "new_from_strings", None) if hasattr(Gtk, "DropDown") else None
    if callable(factory):
        return factory(labels)
    combo = Gtk.ComboBoxText()
    for label in labels:
        combo.append_text(label)
    combo.set_active(0)
    return combo


def choice_index(widget: Gtk.Widget) -> int:
    if hasattr(widget, "get_selected"):
        return int(widget.get_selected())
    get_active = getattr(widget, "get_active", None)
    if callable(get_active):
        return max(0, int(get_active()))
    return 0


def switch_row(title: str, subtitle: str, active: bool) -> tuple[Gtk.Widget, Any]:
    cls = getattr(Adw, "SwitchRow", None)
    if cls is not None:
        row = cls(title=title, subtitle=subtitle)
        row.set_active(active)
        return row, row
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    switch = Gtk.Switch()
    switch.set_active(active)
    switch.set_valign(Gtk.Align.CENTER)
    row.add_suffix(switch)
    row.set_activatable_widget(switch)
    return row, switch


def present_alert(
    parent: Gtk.Window,
    heading: str,
    body: str,
    responses: list[tuple[str, str]],
    *,
    suggested: str | None = None,
    on_response: Callable[[str], None] | None = None,
) -> None:
    alert_cls = getattr(Adw, "AlertDialog", None)
    if alert_cls is not None:
        dialog = alert_cls(heading=heading, body=body)
        for key, label in responses:
            dialog.add_response(key, label)
        if suggested:
            appearance = getattr(Adw, "ResponseAppearance", None)
            if appearance is not None:
                dialog.set_response_appearance(suggested, appearance.SUGGESTED)

        def on_adw(_d: Any, response: str) -> None:
            if on_response is not None:
                on_response(response)

        if on_response is not None:
            dialog.connect("response", on_adw)
        dialog.present(parent)
        return

    msg_cls = getattr(Adw, "MessageDialog", None)
    if msg_cls is not None:
        dialog = msg_cls(transient_for=parent, heading=heading, body=body)
        for key, label in responses:
            dialog.add_response(key, label)

        def on_adw_msg(_d: Any, response: str) -> None:
            if on_response is not None:
                on_response(response)

        if on_response is not None:
            dialog.connect("response", on_adw_msg)
        dialog.present()
        return

    dialog = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=Gtk.MessageType.INFO,
        buttons=Gtk.ButtonsType.NONE,
        text=heading,
    )
    try:
        dialog.set_property("secondary-text", body)
    except (TypeError, GLib.Error):
        extra = Gtk.Label(label=body, wrap=True, xalign=0)
        dialog.get_content_area().append(extra)
    ids: dict[int, str] = {}
    for index, (key, label) in enumerate(responses):
        code = 100 + index
        dialog.add_button(label, code)
        ids[code] = key

    def on_gtk(_d: Gtk.MessageDialog, response: int) -> None:
        dialog.destroy()
        if on_response is not None:
            on_response(ids.get(int(response), "close"))

    dialog.connect("response", on_gtk)
    dialog.present()


def present_text(parent: Gtk.Window, heading: str, body: str) -> None:
    alert_cls = getattr(Adw, "AlertDialog", None)
    if alert_cls is not None and len(body) < 3500:
        present_alert(parent, heading, body, [("ok", "OK")])
        return
    win = Gtk.Window(title=heading, transient_for=parent, modal=True)
    win.set_default_size(560, 520)
    header = Adw.HeaderBar()
    close_btn = Gtk.Button(label="OK")
    close_btn.connect("clicked", lambda *_: win.close())
    header.pack_end(close_btn)
    text = Gtk.TextView()
    text.set_editable(False)
    text.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    text.get_buffer().set_text(body)
    scroll = Gtk.ScrolledWindow()
    scroll.set_vexpand(True)
    set_bin_child(scroll, text)
    set_bin_child(win, toolbar_view(header, scroll))
    win.present()


def _keep(window: Gtk.Window, dialog: Any) -> None:
    window._kit_native_dialog = dialog  # type: ignore[attr-defined]


def _file_dialog_available() -> bool:
    return hasattr(Gtk, "FileDialog")


def open_files(
    window: Gtk.Window,
    on_paths: Callable[[list[Path]], None],
    *,
    multiple: bool = False,
) -> None:
    from ui.pages import common

    if _file_dialog_available():
        dialog = Gtk.FileDialog()
        if multiple:
            dialog.open_multiple(window, None, lambda d, res: _finish_open_many(d, res, on_paths))
        else:
            dialog.open(window, None, lambda d, res: _finish_open_one(d, res, on_paths))
        return
    native = Gtk.FileChooserNative.new("", window, Gtk.FileChooserAction.OPEN, None, None)
    native.set_select_multiple(multiple)

    def on_resp(dlg: Gtk.FileChooserNative, response: int) -> None:
        if int(response) == int(Gtk.ResponseType.ACCEPT):
            if multiple:
                on_paths(common.gio_paths(dlg.get_files()))
            else:
                handle = dlg.get_file()
                if handle is not None and handle.get_path():
                    on_paths([Path(handle.get_path())])
        dlg.destroy()

    native.connect("response", on_resp)
    _keep(window, native)
    native.show()


def _finish_open_one(dialog: Any, result: Gio.AsyncResult, on_paths: Callable[[list[Path]], None]) -> None:
    try:
        handle = dialog.open_finish(result)
    except GLib.Error:
        return
    if handle is None or not handle.get_path():
        return
    on_paths([Path(handle.get_path())])


def _finish_open_many(dialog: Any, result: Gio.AsyncResult, on_paths: Callable[[list[Path]], None]) -> None:
    from ui.pages import common

    try:
        files = dialog.open_multiple_finish(result)
    except GLib.Error:
        return
    on_paths(common.gio_paths(files))


def save_file(window: Gtk.Window, suggested: str, on_path: Callable[[Path], None]) -> None:
    if _file_dialog_available():
        dialog = Gtk.FileDialog()
        dialog.set_initial_name(suggested)
        dialog.save(window, None, lambda d, res: _finish_save(d, res, on_path))
        return
    native = Gtk.FileChooserNative.new("", window, Gtk.FileChooserAction.SAVE, None, None)
    if suggested:
        native.set_current_name(suggested)

    def on_resp(dlg: Gtk.FileChooserNative, response: int) -> None:
        if int(response) == int(Gtk.ResponseType.ACCEPT):
            handle = dlg.get_file()
            if handle is not None and handle.get_path():
                on_path(Path(handle.get_path()))
        dlg.destroy()

    native.connect("response", on_resp)
    _keep(window, native)
    native.show()


def _finish_save(dialog: Any, result: Gio.AsyncResult, on_path: Callable[[Path], None]) -> None:
    try:
        handle = dialog.save_finish(result)
    except GLib.Error:
        return
    if handle is None or not handle.get_path():
        return
    on_path(Path(handle.get_path()))


def select_folder(window: Gtk.Window, on_path: Callable[[Path], None]) -> None:
    if _file_dialog_available():
        dialog = Gtk.FileDialog()
        dialog.select_folder(window, None, lambda d, res: _finish_folder(d, res, on_path))
        return
    native = Gtk.FileChooserNative.new("", window, Gtk.FileChooserAction.SELECT_FOLDER, None, None)

    def on_resp(dlg: Gtk.FileChooserNative, response: int) -> None:
        if int(response) == int(Gtk.ResponseType.ACCEPT):
            handle = dlg.get_file()
            if handle is not None and handle.get_path():
                on_path(Path(handle.get_path()))
        dlg.destroy()

    native.connect("response", on_resp)
    _keep(window, native)
    native.show()


def _finish_folder(dialog: Any, result: Gio.AsyncResult, on_path: Callable[[Path], None]) -> None:
    try:
        folder = dialog.select_folder_finish(result)
    except GLib.Error:
        return
    if folder is None or not folder.get_path():
        return
    on_path(Path(folder.get_path()))


def choose_rgba(
    window: Gtk.Window,
    current: tuple[float, float, float],
    on_color: Callable[[float, float, float], None],
) -> None:
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = (*current, 1.0)
    color_dialog = getattr(Gtk, "ColorDialog", None)
    if color_dialog is not None:
        dialog = color_dialog()
        dialog.choose_rgba(window, rgba, None, lambda d, res: _finish_color_dialog(d, res, on_color))
        return
    native_cls = getattr(Gtk, "ColorChooserNative", None)
    if native_cls is not None:
        native = native_cls.new("", window)
        native.set_rgba(rgba)

        def on_resp(dlg: Any, response: int) -> None:
            if int(response) == int(Gtk.ResponseType.ACCEPT):
                picked = dlg.get_rgba()
                on_color(picked.red, picked.green, picked.blue)
            dlg.destroy()

        native.connect("response", on_resp)
        _keep(window, native)
        native.show()
        return
    dialog = Gtk.ColorChooserDialog(title="", transient_for=window)
    dialog.set_rgba(rgba)
    dialog.set_modal(True)

    def on_dlg(dlg: Gtk.ColorChooserDialog, response: int) -> None:
        if int(response) == int(Gtk.ResponseType.OK):
            picked = dlg.get_rgba()
            on_color(picked.red, picked.green, picked.blue)
        dlg.destroy()

    dialog.connect("response", on_dlg)
    _keep(window, dialog)
    dialog.present()


def enable_file_drop(widget: Gtk.Widget, on_paths: Callable[[list[Path]], None]) -> None:
    drop_cls = getattr(Gtk, "DropTarget", None)
    if drop_cls is None:
        return
    file_list = getattr(Gdk, "FileList", None)
    action = getattr(Gdk, "DragAction", None)
    copy_action = getattr(action, "COPY", 1) if action is not None else 1
    try:
        if file_list is not None:
            target = drop_cls.new(file_list, copy_action)
        else:
            target = drop_cls.new(Gio.File, copy_action)
    except (TypeError, GLib.Error, OverflowError):
        return

    def on_drop(_ctrl: object, value: object, *_xy: object) -> bool:
        paths: list[Path] = []
        getter = getattr(value, "get_files", None)
        if callable(getter):
            for item in getter() or []:
                handle = item if isinstance(item, Gio.File) else None
                if handle is not None and handle.get_path():
                    paths.append(Path(handle.get_path()))
        elif isinstance(value, Gio.File) and value.get_path():
            paths.append(Path(value.get_path()))
        if not paths:
            return False
        on_paths(paths)
        return True

    target.connect("drop", on_drop)
    widget.add_controller(target)


def _finish_color_dialog(dialog: Any, result: Gio.AsyncResult, on_color: Callable[[float, float, float], None]) -> None:
    try:
        picked = dialog.choose_rgba_finish(result)
    except GLib.Error:
        return
    on_color(picked.red, picked.green, picked.blue)
