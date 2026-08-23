# SPDX-License-Identifier: GPL-3.0-or-later
"""Color helpers + XDG portal screen picker (local, no network)."""

from __future__ import annotations

import colorsys
import random
from pathlib import Path
from typing import Callable


def hex_from_rgb(r: float, g: float, b: float) -> str:
    return "#{:02X}{:02X}{:02X}".format(
        max(0, min(255, round(r * 255))),
        max(0, min(255, round(g * 255))),
        max(0, min(255, round(b * 255))),
    )


def rgb_text(r: float, g: float, b: float) -> str:
    return f"rgb({round(r * 255)}, {round(g * 255)}, {round(b * 255)})"


def hsl_text(r: float, g: float, b: float) -> str:
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return f"hsl({round(h * 360)}, {round(s * 100)}%, {round(l * 100)}%)"


def hsv_text(r: float, g: float, b: float) -> str:
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return f"hsv({round(h * 360)}, {round(s * 100)}%, {round(v * 100)}%)"


def parse_hex(text: str) -> tuple[float, float, float]:
    raw = (text or "").strip().lstrip("#")
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    if len(raw) != 6:
        raise ValueError("HEX invalide")
    r = int(raw[0:2], 16) / 255.0
    g = int(raw[2:4], 16) / 255.0
    b = int(raw[4:6], 16) / 255.0
    return r, g, b


def _shift_hue(r: float, g: float, b: float, delta: float) -> tuple[float, float, float]:
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    return colorsys.hsv_to_rgb((h + delta) % 1.0, s, v)


def complementary(r: float, g: float, b: float) -> tuple[float, float, float]:
    return _shift_hue(r, g, b, 0.5)


def triad(r: float, g: float, b: float) -> list[tuple[float, float, float]]:
    return [(r, g, b), _shift_hue(r, g, b, 1.0 / 3.0), _shift_hue(r, g, b, 2.0 / 3.0)]


def analogous(r: float, g: float, b: float) -> list[tuple[float, float, float]]:
    return [_shift_hue(r, g, b, -30 / 360.0), (r, g, b), _shift_hue(r, g, b, 30 / 360.0)]


def random_color() -> tuple[float, float, float]:
    return random.random(), random.random(), random.random()


def _linear(channel: float) -> float:
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(r: float, g: float, b: float) -> float:
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(fg: tuple[float, float, float], bg: tuple[float, float, float]) -> float:
    l1 = relative_luminance(*fg)
    l2 = relative_luminance(*bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def contrast_ok(fg: tuple[float, float, float], bg: tuple[float, float, float], *, threshold: float = 4.5) -> bool:
    return contrast_ratio(fg, bg) >= threshold


def palette_from_image(path: Path, count: int = 6) -> list[tuple[float, float, float]]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow n’est pas installé") from exc
    n = max(2, min(16, int(count)))
    with Image.open(path) as img:
        work = img.convert("RGB")
        work.thumbnail((80, 80))
        counted = work.getcolors(80 * 80) or []
        counted.sort(key=lambda item: item[0], reverse=True)
        colors: list[tuple[float, float, float]] = []
        for _freq, rgb in counted[:n]:
            if not isinstance(rgb, tuple):
                continue
            colors.append((rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0))
        return colors


def gradient_png(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    dest: Path,
    *,
    width: int = 256,
    height: int = 64,
) -> Path:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow n’est pas installé") from exc
    w = max(8, min(2048, int(width)))
    h = max(8, min(512, int(height)))
    img = Image.new("RGB", (w, h))
    pixels = img.load()
    for x in range(w):
        t = x / max(1, w - 1)
        r = start[0] + (end[0] - start[0]) * t
        g = start[1] + (end[1] - start[1]) * t
        b = start[2] + (end[2] - start[2]) * t
        color = (round(r * 255), round(g * 255), round(b * 255))
        for y in range(h):
            pixels[x, y] = color
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "PNG")
    return dest


def pick_screen_color(callback: Callable[[float, float, float], None], on_error: Callable[[str], None]) -> None:
    """org.freedesktop.portal.Screenshot.PickColor — stays on-device."""
    from gi.repository import Gio, GLib

    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            None,
        )
        parent = ""
        options = GLib.Variant("a{sv}", {})
        handle = proxy.call_sync("PickColor", GLib.Variant("(sa{sv})", (parent, options)), Gio.DBusCallFlags.NONE, 15000, None)
        request_path = handle.unpack()[0]
    except GLib.Error as exc:
        on_error(str(exc.message or exc))
        return

    def on_signal(_conn: Gio.DBusConnection, _sender: str, _path: str, _iface: str, _sig: str, params: GLib.Variant) -> None:
        try:
            _response, results = params.unpack()
        except (TypeError, ValueError):
            on_error("réponse pipette invalide")
            return
        if int(_response) != 0:
            on_error("pipette annulée")
            return
        color = results.get("color")
        if not color or len(color) < 3:
            on_error("couleur absente")
            return
        callback(float(color[0]), float(color[1]), float(color[2]))

    try:
        bus.signal_subscribe(
            None,
            "org.freedesktop.portal.Request",
            "Response",
            request_path,
            None,
            Gio.DBusSignalFlags.NONE,
            on_signal,
        )
    except GLib.Error as exc:
        on_error(str(exc.message or exc))
