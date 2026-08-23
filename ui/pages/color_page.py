# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path

from gi.repository import GLib, Gtk

from core import color as color_core
from core import i18n
from ui import compat
from ui.helpers import show_toast
from ui.pages import common


class ColorPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self._color = (0.2, 0.75, 0.55)
        self._fg = (0.05, 0.05, 0.05)
        self._history: list[str] = []
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(24)
        box.set_margin_start(24)
        box.set_margin_end(24)
        self._swatch = Gtk.Box()
        self._swatch.set_size_request(-1, 80)
        self._swatch.add_css_class("card")
        box.append(self._swatch)
        self._hex = Gtk.Entry()
        self._rgb = Gtk.Entry()
        self._hsl = Gtk.Entry()
        self._hsv = Gtk.Entry()
        for entry in (self._hex, self._rgb, self._hsl, self._hsv):
            entry.set_editable(False)
            box.append(entry)
        pick = Gtk.Button(label=i18n.t("color_pick"))
        pick.connect("clicked", self._choose)
        screen = Gtk.Button(label=i18n.t("color_screen"))
        screen.add_css_class("suggested-action")
        screen.connect("clicked", self._screen)
        copy = Gtk.Button(label="HEX")
        copy.connect("clicked", lambda *_: self._copy())
        rnd = Gtk.Button(label=i18n.t("color_random"))
        rnd.connect("clicked", lambda *_: self._apply(*color_core.random_color()))
        box.append(
            common.prefs_group("group_actions",
                [
                    common.action_row("color_pick", pick),
                    common.action_row("color_screen", screen),
                    common.action_row("HEX", copy),
                    common.action_row("color_random", rnd),
                ],
            )
        )
        self._harmony = Gtk.Label(wrap=True, xalign=0)
        box.append(self._harmony)
        self._contrast = Gtk.Label(wrap=True, xalign=0)
        box.append(self._contrast)
        fg = Gtk.Button(label=i18n.t("color_fg"))
        fg.connect("clicked", self._choose_fg)
        pal = Gtk.Button(label=i18n.t("color_palette"))
        pal.connect("clicked", self._palette)
        grad = Gtk.Button(label=i18n.t("color_gradient"))
        grad.connect("clicked", self._gradient)
        box.append(
            common.prefs_group("group_transform",
                [
                    common.action_row("color_fg", fg),
                    common.action_row("color_palette", pal),
                    common.action_row("color_gradient", grad),
                ],
            )
        )
        self._palette_label = Gtk.Label(wrap=True, xalign=0)
        box.append(self._palette_label)
        self._history_list = Gtk.ListBox()
        self._history_list.add_css_class("boxed-list")
        self._history_list.connect("row-activated", self._history_pick)
        box.append(Gtk.Label(label=i18n.t("color_history"), xalign=0))
        box.append(self._history_list)
        gpl_btn = Gtk.Button(label=i18n.t("color_gpl"))
        gpl_btn.connect("clicked", lambda *_: self._export_palette("gpl"))
        css_btn = Gtk.Button(label=i18n.t("color_css"))
        css_btn.connect("clicked", lambda *_: self._export_palette("css"))
        box.append(
            common.prefs_group("group_export",
                [
                    common.action_row("color_gpl", gpl_btn),
                    common.action_row("color_css", css_btn),
                ],
            )
        )
        self._apply(*self._color)
        return common.scrolled(box)

    def _history_pick(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        idx = row.get_index()
        if idx < 0 or idx >= len(self._history):
            return
        try:
            self._apply(*color_core.parse_hex(self._history[idx]))
        except ValueError as exc:
            show_toast(self._toast, str(exc), 5)

    def _push_history(self, hex_value: str) -> None:
        if hex_value in self._history:
            return
        self._history.insert(0, hex_value)
        self._history = self._history[:12]
        common.clear_list(self._history_list)
        for item in self._history:
            row = Gtk.ListBoxRow()
            lab = Gtk.Label(label=item, xalign=0, margin_start=10, margin_end=10, margin_top=6, margin_bottom=6)
            row.set_child(lab)
            self._history_list.append(row)

    def _palette_colors(self) -> list[str]:
        if self._history:
            return list(self._history)
        return [self._hex.get_text()]

    def _gpl_text(self) -> str:
        colors = self._palette_colors()
        lines = ["GIMP Palette", "Name: Hub Utilitaires", f"Columns: {len(colors)}", "#"]
        for index, hex_value in enumerate(colors, 1):
            red, green, blue = color_core.parse_hex(hex_value)
            lines.append(
                f"{round(red * 255):3} {round(green * 255):3} {round(blue * 255):3}\tColor-{index}"
            )
        return "\n".join(lines) + "\n"

    def _css_text(self) -> str:
        colors = self._palette_colors()
        lines = [":root {"]
        for index, hex_value in enumerate(colors, 1):
            lines.append(f"  --color-{index}: {hex_value};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def _export_palette(self, mode: str) -> None:
        text = self._gpl_text() if mode == "gpl" else self._css_text()
        ext = "gpl" if mode == "gpl" else "css"
        compat.save_file(self._window, f"palette.{ext}", lambda dest: dest.write_text(text, encoding="utf-8"))

    def _apply(self, r: float, g: float, b: float) -> None:
        self._color = (r, g, b)
        css = Gtk.CssProvider()
        compat.load_css_data(css, f".kit-swatch {{ background: {color_core.hex_from_rgb(r, g, b)}; }}")
        self._swatch.add_css_class("kit-swatch")
        self._swatch.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._hex.set_text(color_core.hex_from_rgb(r, g, b))
        self._push_history(self._hex.get_text())
        self._rgb.set_text(color_core.rgb_text(r, g, b))
        self._hsl.set_text(color_core.hsl_text(r, g, b))
        self._hsv.set_text(color_core.hsv_text(r, g, b))
        comp = color_core.complementary(r, g, b)
        tri = color_core.triad(r, g, b)
        ana = color_core.analogous(r, g, b)
        self._harmony.set_text(
            f"{i18n.t('color_harmony')}: "
            f"{color_core.hex_from_rgb(*comp)} | "
            + " ".join(color_core.hex_from_rgb(*c) for c in tri)
            + " | "
            + " ".join(color_core.hex_from_rgb(*c) for c in ana)
        )
        ratio = color_core.contrast_ratio(self._fg, self._color)
        ok = color_core.contrast_ok(self._fg, self._color)
        self._contrast.set_text(f"{i18n.t('color_contrast')}: {ratio:.2f} ({'OK' if ok else '<'} 4.5)")

    def _choose(self, *_args: object) -> None:
        compat.choose_rgba(self._window, self._color, self._apply)

    def _choose_fg(self, *_args: object) -> None:
        compat.choose_rgba(self._window, self._fg, self._set_fg)

    def _set_fg(self, r: float, g: float, b: float) -> None:
        self._fg = (r, g, b)
        self._apply(*self._color)

    def _screen(self, *_args: object) -> None:
        color_core.pick_screen_color(
            lambda r, g, b: GLib.idle_add(lambda: self._apply(r, g, b) or False),
            lambda err: GLib.idle_add(lambda: show_toast(self._toast, err, 5) or False),
        )

    def _copy(self) -> None:
        common.copy_text(self._hex.get_text(), self._toast)
        show_toast(self._toast, i18n.t("color_copied"))

    def _palette(self, *_args: object) -> None:
        compat.open_files(self._window, self._load_palette)

    def _load_palette(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            colors = color_core.palette_from_image(paths[0])
        except Exception as exc:  # noqa: BLE001
            show_toast(self._toast, str(exc), 6)
            return
        self._palette_label.set_text(" ".join(color_core.hex_from_rgb(*c) for c in colors))

    def _gradient(self, *_args: object) -> None:
        start = self._color
        end = color_core.complementary(*self._color)
        compat.save_file(self._window, "gradient.png", lambda dest: self._write_grad(start, end, dest))

    def _write_grad(self, start: tuple[float, float, float], end: tuple[float, float, float], dest: Path) -> None:
        try:
            color_core.gradient_png(start, end, dest)
        except Exception as exc:  # noqa: BLE001
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, str(dest))
