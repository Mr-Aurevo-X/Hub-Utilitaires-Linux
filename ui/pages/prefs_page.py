# SPDX-License-Identifier: GPL-3.0-or-later
from collections.abc import Callable
from typing import Any

from gi.repository import Adw, Gdk, Gtk

from core import i18n
from core import updater
from ui import compat
from ui_kit.theme import (
    default_preset_id,
    list_presets,
    load_merged_colors,
    load_preset,
    load_user_theme,
)

_THEME_APP_ID = "hub-utilitaires"
_COLOR_KEYS = ("text", "muted", "accent", "ok", "warn", "danger")


def _normalize_hex(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if not text.startswith("#"):
        text = f"#{text}"
    return text


class PrefsPage:
    def __init__(
        self,
        settings: dict[str, Any],
        *,
        on_language: Callable[[str], None],
        on_save: Callable[
            [Gtk.ComboBoxText, Any, Gtk.SpinButton, str, dict[str, str]],
            None,
        ],
    ) -> None:
        self._settings = settings
        self._on_language = on_language
        self._on_save = on_save
        self._preset_ids: list[str] = []
        self._color_entries: dict[str, Gtk.Entry] = {}
        self.widget = self._build()

    def _theme_state(self) -> tuple[str, dict[str, str]]:
        preset = str(self._preset_combo.get_active_id() or default_preset_id())
        overrides: dict[str, str] = {}
        base = load_preset(preset).get("colors") or {}
        for key, entry in self._color_entries.items():
            value = _normalize_hex(entry.get_text())
            if value and value != str(base.get(key) or ""):
                overrides[key] = value
        return preset, overrides

    def _reset_theme_colors(self) -> None:
        preset = str(self._preset_combo.get_active_id() or default_preset_id())
        colors = load_preset(preset).get("colors") or {}
        for key, entry in self._color_entries.items():
            entry.set_text(str(colors.get(key) or ""))

    def _pick_color(self, key: str, entry: Gtk.Entry) -> None:
        merged = load_merged_colors(config_app_id=_THEME_APP_ID)
        current = _normalize_hex(entry.get_text()) or str((merged.get("colors") or {}).get(key) or "#ffffff")
        rgba = Gdk.RGBA()
        if not rgba.parse(current):
            rgba.parse("#ffffff")
        compat.choose_rgba(
            self.widget,
            rgba,
            lambda color: entry.set_text(color.to_string()),
        )

    def _build(self) -> Gtk.Widget:
        page = Adw.PreferencesPage()
        lang_g = Adw.PreferencesGroup(title=i18n.t("language"))
        combo = Gtk.ComboBoxText()
        combo.append("fr", "Français")
        combo.append("en", "English")
        combo.set_active_id(i18n.normalize_language(i18n.language()))
        combo.set_valign(Gtk.Align.CENTER)
        combo.connect("changed", self._combo_changed)
        lang_row = Adw.ActionRow(title=i18n.t("language"))
        lang_row.add_suffix(combo)
        lang_g.add(lang_row)
        page.add(lang_g)

        appearance = Adw.PreferencesGroup(
            title=i18n.t("appearance"),
            description=i18n.t("appearance_subtitle"),
        )
        presets = list_presets()
        self._preset_ids = [pid for pid, _ in presets]
        preset_combo = Gtk.ComboBoxText()
        for pid, label in presets:
            preset_combo.append(pid, label)
        current_preset = str(load_user_theme(config_app_id=_THEME_APP_ID).get("preset") or default_preset_id())
        if current_preset in self._preset_ids:
            preset_combo.set_active_id(current_preset)
        preset_combo.set_valign(Gtk.Align.CENTER)
        merged = load_merged_colors(config_app_id=_THEME_APP_ID, preset_id=current_preset)
        merged_colors = merged.get("colors") or {}
        preset_row = Adw.ActionRow(title=i18n.t("theme_preset"))
        preset_row.add_suffix(preset_combo)
        appearance.add(preset_row)
        self._preset_combo = preset_combo

        for key in _COLOR_KEYS:
            entry = Gtk.Entry()
            entry.set_width_chars(10)
            entry.set_text(str(merged_colors.get(key) or ""))
            self._color_entries[key] = entry
            pick_btn = Gtk.Button(label=i18n.t("theme_pick"))
            pick_btn.connect("clicked", lambda *_a, k=key, e=entry: self._pick_color(k, e))
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.append(entry)
            box.append(pick_btn)
            row = Adw.ActionRow(title=i18n.t(f"theme_{key}"))
            row.add_suffix(box)
            appearance.add(row)

        reset_row = Adw.ActionRow(title=i18n.t("theme_reset"))
        reset_btn = Gtk.Button(label=i18n.t("theme_reset"))
        reset_btn.connect("clicked", lambda *_: self._reset_theme_colors())
        reset_row.add_suffix(reset_btn)
        appearance.add(reset_row)
        page.add(appearance)

        limits = Adw.PreferencesGroup(title=i18n.t("find_max_results"))
        limit_row = Adw.ActionRow(title=i18n.t("find_max_results"))
        limit_spin = Gtk.SpinButton.new_with_range(1, 20_000, 50)
        limit_spin.set_value(int(self._settings.get("find_max_results") or 400))
        limit_spin.set_valign(Gtk.Align.CENTER)
        limit_row.add_suffix(limit_spin)
        limits.add(limit_row)
        page.add(limits)

        upd = Adw.PreferencesGroup(title=i18n.t("updates"), description=i18n.t("privacy_local"))
        ver = Adw.ActionRow(title=i18n.t("current_version"), subtitle=updater.local_version())
        upd.add(ver)
        toggle_row, toggle = compat.switch_row(
            i18n.t("auto_update"),
            i18n.t("auto_update_subtitle"),
            bool(self._settings.get("auto_update_on_startup", True)),
        )
        upd.add(toggle_row)
        page.add(upd)

        log_g = Adw.PreferencesGroup(title=i18n.t("ops_log"))
        log_row = Adw.ActionRow(title=i18n.t("ops_log_view"))
        log_btn = Gtk.Button(label=i18n.t("ops_log_view"))
        log_btn.connect("clicked", lambda *_: self._show_ops_log())
        log_row.add_suffix(log_btn)
        log_g.add(log_row)
        page.add(log_g)

        save = Adw.PreferencesGroup()
        save_row = Adw.ActionRow(title=i18n.t("save"))
        save_btn = Gtk.Button(label=i18n.t("save"))
        save_btn.add_css_class("suggested-action")
        save_btn.connect(
            "clicked",
            lambda *_: self._on_save(combo, toggle, limit_spin, *self._theme_state()),
        )
        save_row.add_suffix(save_btn)
        save.add(save_row)
        page.add(save)
        return page

    def _combo_changed(self, combo: Gtk.ComboBoxText) -> None:
        self._on_language(i18n.normalize_language(combo.get_active_id()))

    def _show_ops_log(self) -> None:
        from core import opslog

        win = Gtk.Window(transient_for=self.widget.get_root(), modal=True, title=i18n.t("ops_log"))
        win.set_default_size(640, 420)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.get_buffer().set_text(opslog.read_tail())
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(view)
        win.set_child(scroll)
        win.present()
