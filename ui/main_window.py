# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from core import i18n
from core import settings as app_settings
from core import updater
from core.workset import SendTarget, Workset, coerce_send_target, existing_only, from_paths
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui_kit.dialogs.update import present as present_update_dialog
from ui_kit.shell import ShellLayout, build_main_layout
from ui.nav import NavSidebar, nav_pages, page_titles
from ui.pages import (
    AtelierPage,
    ColorPage,
    DiskPage,
    FilePage,
    FindPage,
    HashPage,
    ImagesPage,
    LotsPage,
    PdfPage,
    PrefsPage,
    RenamePage,
)

def _nav_pages() -> tuple[tuple[str, str], ...]:
    return nav_pages()


def _default_window_size() -> tuple[int, int]:
    width, height = 1100, 720
    display = Gdk.Display.get_default()
    if display is None:
        return width, height
    get_n = getattr(display, "get_n_monitors", None)
    get_mon = getattr(display, "get_monitor", None)
    if callable(get_n) and callable(get_mon) and get_n() > 0:
        try:
            geo = get_mon(0).get_geometry()
            width = min(width, max(640, int(geo.width) - 64))
            height = min(height, max(480, int(geo.height) - 64))
        except (TypeError, AttributeError):
            pass
    return width, height


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application) -> None:
        display = updater.app_display_name()
        super().__init__(application=application, title=display)
        self.add_css_class("uni-window")
        self.set_default_size(*_default_window_size())
        self._display_name = display
        self._settings = app_settings.load_settings()
        i18n.set_language(str(self._settings.get("language") or "fr"))
        self._toast = Adw.ToastOverlay()
        self._pages: dict[str, Any] = {}
        self._stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self._nav_sidebar: NavSidebar | None = None
        self._layout: ShellLayout | None = None
        self._logged_mapped = False
        folder = Path(str(self._settings.get("last_folder") or "")).expanduser()
        self._workset = Workset(folder if folder.is_dir() else Path.home(), [])
        self._build()
        self._bind_shortcuts()
        self._setup_drop_target()
        self.connect("map", self._on_window_mapped)
        if not app_settings.needs_language_prompt(self._settings):
            GLib.timeout_add(1800, self._maybe_check_updates)

    def _on_window_mapped(self, *_args: object) -> None:
        if self._logged_mapped:
            return
        self._logged_mapped = True
        print("fenêtre ouverte", flush=True)
        if app_settings.needs_language_prompt(self._settings):
            GLib.idle_add(self._prompt_language)

    def _build(self) -> None:
        start = app_settings.coerce_page(self._settings.get("last_page"))
        titles = page_titles()
        layout = build_main_layout(
            self._make_nav(),
            self._stack,
            page_title=titles.get(start, start),
            lang=i18n.language(),
        )
        layout.attach_chrome_buttons(
            self,
            on_check_updates=self._manual_check_updates,
            on_language_toggle=self._apply_language,
            current_language=i18n.language(),
            settings_snapshot=self._settings,
            current_version=updater.local_version(),
            on_settings_save=self._save_prefs_from_kit,
            on_open_preferences=self._open_preferences,
        )
        self._layout = layout
        compat.set_bin_child(self._toast, layout.widget)
        compat.set_bin_child(self, self._toast)
        self._show_page(start)

    def _make_nav(self) -> Gtk.Widget:
        self._nav_sidebar = NavSidebar(
            settings=self._settings,
            on_page_selected=self._on_nav_page_selected,
            on_groups_changed=self._on_nav_groups_changed,
        )
        start = app_settings.coerce_page(self._settings.get("last_page"))
        self._nav_sidebar.select_page(start, notify=False)
        return self._nav_sidebar.widget

    def _on_nav_page_selected(self, key: str) -> None:
        self._show_page(key)

    def _on_nav_groups_changed(self, expanded: dict[str, bool]) -> None:
        self._settings["nav_groups_expanded"] = expanded
        app_settings.save_settings(self._settings)

    def _bind_shortcuts(self) -> None:
        app = self.get_application()
        prefs = Gio.SimpleAction.new("preferences", None)
        prefs.connect("activate", lambda *_: self._open_preferences())
        self.add_action(prefs)
        about = Gio.SimpleAction.new("about", None)
        about.connect("activate", lambda *_: self._open_legal())
        self.add_action(about)
        donate = Gio.SimpleAction.new("donate", None)
        donate.connect("activate", lambda *_: self._open_donate())
        self.add_action(donate)
        if app is None:
            return
        mapping = (
            ("show-find", ["<Control>f"], "find"),
            ("nav-1", ["<Control>1"], "find"),
            ("nav-2", ["<Control>2"], "rename"),
            ("nav-3", ["<Control>3"], "lots"),
            ("nav-4", ["<Control>4"], "disk"),
        )
        for name, accels, page in mapping:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda *_args, key=page: self._show_page(key))
            self.add_action(action)
            app.set_accels_for_action(f"win.{name}", accels)
        app.set_accels_for_action("win.preferences", ["<Control>comma"])
        palette = Gio.SimpleAction.new("command-palette", None)
        palette.connect("activate", lambda *_: self._open_command_palette())
        self.add_action(palette)
        app.set_accels_for_action("win.command-palette", ["<Control>k"])

    def _setup_drop_target(self) -> None:
        target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        target.connect("drop", self._on_drop)
        self.add_controller(target)

    def _on_drop(self, _target: Gtk.DropTarget, value: object, _x: float, _y: float) -> bool:
        files: list[Path] = []
        if isinstance(value, Gio.File):
            files = [Path(value.get_path() or "")]
        elif isinstance(value, Gdk.FileList):
            for item in value.get_files():
                files.append(Path(item.get_path() or ""))
        files = [p for p in files if p and (p.is_dir() or p.is_file())]
        if not files:
            return False
        if len(files) == 1 and files[0].is_dir():
            self.notify_folder(files[0])
            return True
        self.send_paths(self._stack.get_visible_child_name() or "find", files)
        return True

    def _open_command_palette(self) -> None:
        dialog = Adw.Window(transient_for=self, modal=True, title=i18n.t("cmd_palette"))
        dialog.set_default_size(420, 360)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
        entry = Gtk.SearchEntry(placeholder_text=i18n.t("cmd_palette_hint"))
        listbox = Gtk.ListBox()
        listbox.add_css_class("boxed-list")
        pages = _nav_pages()

        def rebuild(_entry: Gtk.SearchEntry | None = None) -> None:
            child = listbox.get_first_child()
            while child is not None:
                nxt = child.get_next_sibling()
                listbox.remove(child)
                child = nxt
            needle = entry.get_text().strip().lower()
            for key, label_key in pages:
                label = i18n.t(label_key)
                if needle and needle not in label.lower() and needle not in key:
                    continue
                row = Gtk.ListBoxRow()
                row.set_name(key)
                row.set_child(Gtk.Label(label=label, xalign=0))
                listbox.append(row)

        entry.connect("search-changed", rebuild)
        rebuild()

        def on_activate(_lb: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
            key = row.get_name() or "find"
            self._show_page(key)
            dialog.close()

        listbox.connect("row-activated", on_activate)
        box.append(entry)
        box.append(Gtk.ScrolledWindow(vexpand=True, child=listbox))
        dialog.set_content(box)
        dialog.present()
        entry.grab_focus()

    def _factory(self, key: str) -> Any:
        if key == "find":
            return FindPage(self, self._toast, self._settings, on_send=self.send_paths)
        if key == "color":
            return ColorPage(self, self._toast)
        if key == "atelier":
            return AtelierPage(self, self._toast)
        if key == "rename":
            return RenamePage(self, self._toast, self._settings)
        if key == "hash":
            return HashPage(self, self._toast)
        if key == "resize":
            return ImagesPage(self, self._toast)
        if key == "pdf":
            return PdfPage(self, self._toast)
        if key == "file":
            return FilePage(self, self._toast)
        if key == "lots":
            return LotsPage(self, self._toast, self._settings)
        if key == "disk":
            return DiskPage(self, self._toast, self._settings)
        raise KeyError(key)

    def _ensure_page(self, key: str) -> Any:
        page = self._pages.get(key)
        if page is not None:
            return page
        page = self._factory(key)
        self._pages[key] = page
        self._stack.add_named(page.widget, key)
        return page

    def _show_page(self, key: str) -> None:
        self._ensure_page(key)
        self._stack.set_visible_child_name(key)
        titles = page_titles()
        if self._layout is not None:
            self._layout.set_page_title(titles.get(key, key))
        self._settings["last_page"] = key
        app_settings.save_settings(self._settings)
        if self._nav_sidebar is not None:
            self._nav_sidebar.select_page(key, notify=False)

    def notify_folder(self, path: Path) -> None:
        app_settings.remember_folder(self._settings, str(path))
        self._workset = Workset(path, self._workset.paths)
        for page in self._pages.values():
            on_folder = getattr(page, "on_folder", None)
            if callable(on_folder):
                on_folder(path)

    def send_paths(self, target: SendTarget | str, paths: list[Path]) -> None:
        key = coerce_send_target(target)
        if key == "textdiff":
            from core import cross_hub

            cross_hub.write_pending_textdiff(paths)
            show_toast(self._toast, i18n.t("send_textdiff_hub_dev"), 6)
            return
        folder = self._workset.folder
        raw = str(self._settings.get("last_folder") or "").strip()
        if raw:
            folder = Path(raw)
        self._workset = existing_only(from_paths(folder, paths))
        page = self._ensure_page(key)
        receive = getattr(page, "receive_paths", None)
        if callable(receive):
            receive(self._workset.paths)
        self._show_page(key)

    def _prompt_language(self) -> bool:
        if not app_settings.needs_language_prompt(self._settings):
            return False

        def on_resp(response: str) -> None:
            if response not in {"fr", "en"}:
                return
            self._apply_language(response)
            GLib.timeout_add(400, self._maybe_check_updates)

        compat.present_alert(
            self,
            i18n.t("welcome_lang"),
            i18n.t("welcome_lang_body"),
            [("fr", "Français"), ("en", "English")],
            suggested="fr",
            on_response=on_resp,
        )
        return False

    def _apply_language(self, lang: str) -> None:
        code = i18n.normalize_language(lang)
        same_ui = i18n.language() == code and str(self._settings.get("language") or "") == code
        self._settings["language"] = code
        self._settings["language_chosen"] = True
        app_settings.save_settings(self._settings)
        if same_ui:
            return
        i18n.set_language(code)
        current = self._stack.get_visible_child_name() or "find"
        self._rebuild_pages(current)
        if self._layout is not None:
            self._layout.update_language_button(code)

    def _save_prefs_from_kit(self, _settings: dict[str, Any]) -> None:
        show_toast(self._toast, i18n.t("prefs_saved"))

    def _save_prefs(
        self,
        combo: Gtk.ComboBoxText,
        toggle: Any,
        limit_spin: Gtk.SpinButton,
        theme_preset: str,
        theme_overrides: dict[str, str],
    ) -> None:
        self._settings["auto_update_on_startup"] = toggle.get_active()
        self._settings["find_max_results"] = int(limit_spin.get_value())
        self._settings["language"] = i18n.normalize_language(combo.get_active_id())
        app_settings.save_settings(self._settings)
        self._apply_language(str(self._settings["language"]))
        from ui_kit.theme import apply_theme, save_user_theme, user_theme_path

        save_user_theme(
            user_theme_path("hub-utilitaires"),
            preset_id=theme_preset,
            overrides=theme_overrides,
        )
        apply_theme(config_app_id="hub-utilitaires", preset_id=theme_preset)
        show_toast(self._toast, i18n.t("prefs_saved"))

    def _open_preferences(self) -> None:
        win = Adw.PreferencesWindow()
        win.set_transient_for(self)
        win.set_modal(True)
        win.set_title(i18n.t("preferences"))

        def on_save(
            combo: Gtk.ComboBoxText,
            toggle: Any,
            limit_spin: Gtk.SpinButton,
            theme_preset: str,
            theme_overrides: dict[str, str],
        ) -> None:
            self._save_prefs(combo, toggle, limit_spin, theme_preset, theme_overrides)
            win.close()

        prefs = PrefsPage(
            self._settings,
            on_language=self._apply_language,
            on_save=on_save,
        )
        win.add(prefs.widget)
        win.present()

    def _open_legal(self) -> None:
        from ui_kit.dialogs import legal as legal_dialog

        legal_dialog.present(self, i18n.language())

    def _open_donate(self) -> None:
        from ui_kit.dialogs import donate as donate_dialog

        donate_dialog.present(self, i18n.language())

    def _rebuild_pages(self, current: str) -> None:
        for name in list(self._pages):
            child = self._stack.get_child_by_name(name)
            if child is not None:
                self._stack.remove(child)
        self._pages.clear()
        if self._nav_sidebar is not None:
            self._nav_sidebar.update_settings(self._settings)
            self._nav_sidebar.relabel()
        self._show_page(current)

    def _set_auto_update_enabled(self, enabled: bool) -> None:
        self._settings["auto_update_on_startup"] = bool(enabled)
        app_settings.save_settings(self._settings)

    def _manual_check_updates(self) -> None:
        show_toast(self._toast, i18n.t("update_checking"), 4)

        def work() -> dict[str, Any] | None:
            return updater.check_for_update(raise_on_error=True)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, i18n.t("update_check_failed", detail=str(error)), 8)
                return
            if not isinstance(result, dict):
                show_toast(
                    self._toast,
                    i18n.t("update_up_to_date", version=updater.local_version()),
                    5,
                )
                return
            self._show_update_dialog(result)

        run_in_thread(work, done)

    def _maybe_check_updates(self) -> bool:
        if not bool(self._settings.get("auto_update_on_startup", True)):
            return False

        def work() -> dict[str, Any] | None:
            return updater.check_for_update()

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None or not isinstance(result, dict):
                return
            self._show_update_dialog(result)

        run_in_thread(work, done)
        return False

    def _show_update_dialog(self, info: dict[str, Any]) -> None:
        from core.update_fetch import format_update_dialog_body, format_update_dialog_commands

        latest = str(info.get("version") or "?")
        present_update_dialog(
            self,
            i18n.t("update_available"),
            format_update_dialog_body(info),
            format_update_dialog_commands(info),
            new_version=latest,
            lang=i18n.language(),
        )
