#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Hub Utilitaires — GTK4 / Libadwaita local toolkit."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from core.display_env import apply_safe_display_env

_applied = apply_safe_display_env()
for _key, _val in _applied.items():
    print(f"{_key}={_val}", flush=True)

import gi  # noqa: E402

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib  # noqa: E402

if os.environ.get("GDK_BACKEND") == "x11":
    try:
        Gdk.set_allowed_backends("x11")
    except Exception:  # noqa: BLE001
        pass

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ui_kit.bootstrap import ensure_ui_kit_on_path  # noqa: E402

ensure_ui_kit_on_path(_ROOT)

from core import i18n  # noqa: E402
from core import settings as app_settings  # noqa: E402
from core.migrate import run_first_launch_migration  # noqa: E402
from ui import compat  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


def _log(message: str) -> None:
    print(message, flush=True)
    log = Path.home() / ".local/share/hub-utilitaires/launch.log"
    try:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
    except OSError:
        pass


class HubUtilitairesApp(Adw.Application):
    def __init__(self) -> None:
        flags = getattr(Gio.ApplicationFlags, "NON_UNIQUE", None)
        if flags is None:
            flags = getattr(Gio.ApplicationFlags, "FLAGS_NONE", None)
        if flags is None:
            flags = getattr(Gio.ApplicationFlags, "DEFAULT_FLAGS", 0)
        super().__init__(
            application_id="org.mraurevox.HubUtilitaires",
            flags=flags,
        )
        self._window: MainWindow | None = None
        self._held = False
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _on_quit(self, *_args: object) -> None:
        self._release_hold()
        self.quit()

    def _hold_once(self) -> None:
        if self._held:
            return
        self.hold()
        self._held = True

    def _release_hold(self) -> None:
        if not self._held:
            return
        self._held = False
        self.release()

    def do_startup(self) -> None:  # noqa: N802
        Adw.Application.do_startup(self)
        _log("do_startup ok")

    def do_activate(self) -> None:  # noqa: N802
        self._hold_once()
        _log(
            "do_activate remote="
            f"{self.get_is_remote()} display={os.environ.get('DISPLAY', '')!r} "
            f"session={os.environ.get('XDG_SESSION_TYPE', '')!r}"
        )
        try:
            gdk_display = Gdk.Display.get_default()
            if gdk_display is None:
                raise RuntimeError("aucun display GDK (DISPLAY / X11)")
            style = Adw.StyleManager.get_default()
            style.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
            from ui_kit.theme import apply_theme

            apply_theme(config_app_id="hub-utilitaires")
            run_first_launch_migration()
            cfg = app_settings.load_settings()
            i18n.set_language(str(cfg.get("language") or "fr"))
            if self._window is None:
                self._window = MainWindow(application=self)
                self.add_window(self._window)
                self._window.connect("close-request", self._on_window_close)
            self._window.set_visible(True)
            present = getattr(self._window, "present", None)
            if callable(present):
                present()
            _log(
                f"window visible={self._window.get_visible()} "
                f"count={len(self.get_windows())}"
            )
            GLib.timeout_add(900, self._check_mapped)
        except Exception as exc:  # noqa: BLE001
            text = traceback.format_exc()
            _log(text)
            if not compat.present_startup_error(f"{type(exc).__name__}: {exc}", on_close=self._on_quit):
                self._on_quit()

    def _on_window_close(self, *_args: object) -> bool:
        self._release_hold()
        return False

    def _check_mapped(self) -> bool:
        win = self._window
        if win is None:
            _log("fenêtre absente après activate")
            return False
        mapped = bool(getattr(win, "get_mapped", lambda: False)())
        if mapped:
            _log("fenêtre mappée")
            return False
        _log("fenêtre non mappée après 900ms — GDK/GL ou WM")
        compat.present_startup_error(
            "La fenêtre GTK4 ne s’affiche pas (Mint/VM : DRI2/EGL). "
            "Réinstallez 0.2.5+ ou utilisez le Flatpak.",
            on_close=None,
        )
        return False


def main(argv: list[str] | None = None) -> int:
    _log(
        f"env DISPLAY={os.environ.get('DISPLAY')} "
        f"GDK_BACKEND={os.environ.get('GDK_BACKEND')} "
        f"GSK_RENDERER={os.environ.get('GSK_RENDERER')}"
    )
    return HubUtilitairesApp().run(argv or sys.argv)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
