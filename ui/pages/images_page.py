# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import GLib, Gtk

from core import i18n
from core import resize as resize_core
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common

_FMT_KEEP = "keep"
_FMT_CHOICES = (_FMT_KEEP, "jpg", "png", "webp", "bmp")
_CORNERS = ("se", "sw", "ne", "nw")


class ImagesPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self._files: list[Path] = []
        self._out_dir: Path | None = None
        self.widget = self._build()

    def receive_paths(self, paths: list[Path]) -> None:
        self._set_files(paths)

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        add = Gtk.Button(label=i18n.t("add_files"))
        add.connect("clicked", lambda *_: compat.open_files(self._window, self._set_files, multiple=True))
        folder = Gtk.Button(label=i18n.t("resize_folder"))
        folder.connect("clicked", lambda *_: compat.select_folder(self._window, self._from_folder))
        out = Gtk.Button(label=i18n.t("resize_out"))
        out.connect("clicked", lambda *_: compat.select_folder(self._window, self._set_out))
        box.append(
            common.prefs_group("group_source",
                [
                    common.action_row("add_files", add),
                    common.action_row("resize_folder", folder),
                    common.action_row("resize_out", out),
                ],
            )
        )
        self._list = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._list)
        self._out_label = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._out_label)
        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(True)
        box.append(self._progress)
        box.append(Gtk.Label(label=i18n.t("resize_side"), xalign=0))
        self._max_side = Gtk.SpinButton.new_with_range(0, 8000, 16)
        self._max_side.set_value(0)
        box.append(self._max_side)
        box.append(Gtk.Label(label=i18n.t("resize_width"), xalign=0))
        self._max_w = Gtk.SpinButton.new_with_range(0, 8000, 16)
        self._max_w.set_value(1280)
        box.append(self._max_w)
        box.append(Gtk.Label(label=i18n.t("resize_height"), xalign=0))
        self._max_h = Gtk.SpinButton.new_with_range(0, 8000, 16)
        self._max_h.set_value(0)
        box.append(self._max_h)
        box.append(Gtk.Label(label=i18n.t("resize_percent"), xalign=0))
        self._percent = Gtk.SpinButton.new_with_range(0, 400, 5)
        self._percent.set_value(0)
        box.append(self._percent)
        box.append(Gtk.Label(label=i18n.t("resize_quality"), xalign=0))
        self._quality = Gtk.SpinButton.new_with_range(40, 95, 1)
        self._quality.set_value(85)
        box.append(self._quality)
        box.append(Gtk.Label(label=i18n.t("resize_format"), xalign=0))
        self._fmt = compat.string_choice([i18n.t("resize_keep"), "JPEG", "PNG", "WebP", "BMP"])
        box.append(self._fmt)
        box.append(Gtk.Label(label=i18n.t("resize_rotate"), xalign=0))
        self._rotate = compat.string_choice(["0", "90", "180", "270"])
        box.append(self._rotate)
        self._flip_h = Gtk.CheckButton(label=i18n.t("resize_flip_h"))
        self._flip_v = Gtk.CheckButton(label=i18n.t("resize_flip_v"))
        self._gray = Gtk.CheckButton(label=i18n.t("resize_gray"))
        self._invert = Gtk.CheckButton(label=i18n.t("resize_invert"))
        for item in (self._flip_h, self._flip_v, self._gray, self._invert):
            box.append(item)
        box.append(Gtk.Label(label=i18n.t("resize_pixelate"), xalign=0))
        self._pixel = Gtk.SpinButton.new_with_range(0, 32, 1)
        box.append(self._pixel)
        box.append(Gtk.Label(label=i18n.t("resize_brightness"), xalign=0))
        self._bright = Gtk.SpinButton.new_with_range(-80, 80, 5)
        box.append(self._bright)
        self._mark = Gtk.Entry(placeholder_text=i18n.t("resize_watermark"))
        box.append(self._mark)
        box.append(Gtk.Label(label=i18n.t("resize_corner"), xalign=0))
        self._corner = compat.string_choice(["SE", "SW", "NE", "NW"])
        box.append(self._corner)
        self._strip = Gtk.CheckButton(label=i18n.t("resize_strip_exif"))
        box.append(self._strip)
        go = Gtk.Button(label=i18n.t("resize_go"))
        go.add_css_class("suggested-action")
        go.connect("clicked", lambda *_: self._run())
        box.append(
            common.prefs_group("group_export",
                [
                    common.action_row("resize_go", go),
                    common.button_row("img_icons", self._export_icons),
                    common.button_row("img_exif_rotate", self._exif_rotate),
                    common.button_row("img_compare", self._compare_images),
                ],
            )
        )
        box.append(Gtk.Label(label=i18n.t("resize_info"), xalign=0))
        self._exif = Gtk.TextView()
        self._exif.set_editable(False)
        self._exif.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._exif))
        compat.enable_file_drop(box, self._set_files)
        return common.scrolled(box)

    def _from_folder(self, root: Path) -> None:
        try:
            self._set_files(resize_core.list_images(root))
        except resize_core.ResizeError as exc:
            show_toast(self._toast, str(exc), 6)

    def _set_out(self, folder: Path) -> None:
        self._out_dir = folder
        self._out_label.set_text(str(folder))

    def _set_files(self, paths: list[Path]) -> None:
        self._files = paths
        self._list.set_text("\n".join(str(p) for p in paths) or "—")
        if not paths:
            self._exif.get_buffer().set_text("")
            return
        try:
            info = resize_core.image_info(paths[0])
            exif = resize_core.exif_text(paths[0]) or "—"
            header = (
                f"{info['width']}×{info['height']} {info['mode']} {info['format']} "
                f"{info['bytes']} o DPI={info['dpi']}"
            )
            self._exif.get_buffer().set_text(f"{header}\n{exif}")
        except resize_core.ResizeError as exc:
            self._exif.get_buffer().set_text(str(exc))

    def _opts(self) -> dict[str, object]:
        width = int(self._max_w.get_value())
        height = int(self._max_h.get_value())
        side = int(self._max_side.get_value())
        percent = float(self._percent.get_value())
        idx = compat.choice_index(self._fmt)
        choice = _FMT_CHOICES[idx] if 0 <= idx < len(_FMT_CHOICES) else _FMT_KEEP
        rot = (0, 90, 180, 270)[compat.choice_index(self._rotate)]
        corner = _CORNERS[compat.choice_index(self._corner)]
        return {
            "max_width": width if width >= 16 else None,
            "max_height": height if height >= 16 else None,
            "max_side": side if side >= 16 else None,
            "scale_percent": percent if percent > 0 else None,
            "quality": int(self._quality.get_value()),
            "strip_exif": bool(self._strip.get_active()),
            "rotate": rot,
            "flip_h": self._flip_h.get_active(),
            "flip_v": self._flip_v.get_active(),
            "grayscale": self._gray.get_active(),
            "invert": self._invert.get_active(),
            "pixelate": int(self._pixel.get_value()),
            "brightness": int(self._bright.get_value()),
            "watermark": self._mark.get_text(),
            "watermark_corner": corner,
            "choice": choice,
        }

    def _set_progress(self, done: int, total: int) -> None:
        frac = (done / total) if total else 0.0
        self._progress.set_fraction(min(1.0, max(0.0, frac)))
        self._progress.set_text(f"{done} / {total}")

    def _progress_cb(self, done: int, total: int) -> None:
        GLib.idle_add(lambda: self._set_progress(done, total) or False)

    def _run(self) -> None:
        files = list(self._files)
        if not files:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return

        def on_resp(response: str) -> None:
            if response != "now":
                return
            self._convert(files)

        compat.present_alert(
            self._window,
            i18n.t("resize_write_confirm"),
            i18n.t("resize_write_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("confirm"))],
            suggested="now",
            on_response=on_resp,
        )

    def _convert(self, files: list[Path]) -> None:
        opts = self._opts()
        choice = str(opts.pop("choice"))
        dest_dir = self._out_dir

        def suffix_for(src: Path) -> str:
            if choice == _FMT_KEEP:
                return src.suffix.lower() or ".jpg"
            return f".{choice}"

        def work() -> list[str]:
            if dest_dir is not None:
                first = suffix_for(files[0])
                done = resize_core.batch_convert(
                    files,
                    dest_dir,
                    suffix=first if choice != _FMT_KEEP else "",
                    on_progress=self._progress_cb,
                    **opts,
                )
                if choice == _FMT_KEEP:
                    return [str(path) for path in done]
                return [str(path) for path in done]
            out: list[str] = []
            total = len(files)
            for index, src in enumerate(files, 1):
                dest = src.with_name(f"{src.stem}_kit{suffix_for(src)}")
                resize_core.convert_image(src, dest, **opts)  # type: ignore[arg-type]
                out.append(str(dest))
                self._progress_cb(index, total)
            return out

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            show_toast(self._toast, f"{len(result)} OK")

        run_in_thread(work, done)

    def _need_file(self) -> Path | None:
        if not self._files:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return None
        return self._files[0]

    def _export_icons(self, *_args: object) -> None:
        src = self._need_file()
        if src is None:
            return
        compat.select_folder(
            self._window,
            lambda folder: self._bg_icons(src, folder),
        )

    def _bg_icons(self, src: Path, folder: Path) -> None:
        def work() -> str:
            paths = resize_core.export_icons(src, folder)
            return "\n".join(str(path) for path in paths)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            show_toast(self._toast, "OK")

        run_in_thread(work, done)

    def _exif_rotate(self, *_args: object) -> None:
        src = self._need_file()
        if src is None:
            return
        compat.save_file(
            self._window,
            f"{src.stem}_rotated{src.suffix or '.jpg'}",
            lambda dest: self._bg_rotate(src, dest),
        )

    def _bg_rotate(self, src: Path, dest: Path) -> None:
        def work() -> str:
            return str(resize_core.auto_rotate_exif(src, dest))

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            show_toast(self._toast, str(result))

        run_in_thread(work, done)

    def _compare_images(self, *_args: object) -> None:
        if len(self._files) < 2:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return
        left, right = self._files[0], self._files[1]

        def work() -> str:
            return resize_core.compare_images(left, right)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            self._exif.get_buffer().set_text(str(result))

        run_in_thread(work, done)
