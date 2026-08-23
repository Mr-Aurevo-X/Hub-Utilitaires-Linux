# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from gi.repository import GLib, Gtk


def run_in_thread(fn: Callable[[], Any], on_done: Callable[[Any, BaseException | None], None]) -> None:
    def worker() -> None:
        result: Any = None
        error: BaseException | None = None
        try:
            result = fn()
        except BaseException as exc:  # noqa: BLE001
            error = exc
        GLib.idle_add(lambda: on_done(result, error) or False)

    threading.Thread(target=worker, daemon=True).start()


def show_toast(overlay: Gtk.Widget, text: str, timeout: int = 3) -> None:
    from gi.repository import Adw

    toast = Adw.Toast.new(text)
    toast.set_timeout(timeout)
    overlay.add_toast(toast)
