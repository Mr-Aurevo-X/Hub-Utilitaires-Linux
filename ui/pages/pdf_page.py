# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import i18n
from core import pdfutil
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common


class PdfPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self._files: list[Path] = []
        self._inventory_csv = ""
        self.widget = self._build()

    def receive_paths(self, paths: list[Path]) -> None:
        self._set_files(paths)

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        hint = Gtk.Label(label=i18n.t("pdf_hint"), wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        add = Gtk.Button(label=i18n.t("add_files"))
        add.connect("clicked", lambda *_: compat.open_files(self._window, self._set_files, multiple=True))
        box.append(common.prefs_group("group_files", [common.action_row("add_files", add)]))
        self._sel = Gtk.SpinButton.new_with_range(1, 1, 1)
        up = Gtk.Button(label=i18n.t("pdf_up"))
        down = Gtk.Button(label=i18n.t("pdf_down"))
        up.connect("clicked", lambda *_: self._move(-1))
        down.connect("clicked", lambda *_: self._move(1))
        order = Gtk.Box(spacing=8)
        order.append(self._sel)
        order.append(up)
        order.append(down)
        box.append(order)
        self._list = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._list)
        self._info = Gtk.Label(label="", wrap=True, xalign=0)
        box.append(self._info)
        self._ranges = Gtk.Entry(placeholder_text=i18n.t("pdf_ranges"))
        box.append(self._ranges)
        self._password = Gtk.Entry(placeholder_text=i18n.t("pdf_password"))
        self._password.set_visibility(False)
        box.append(self._password)
        self._blank = Gtk.SpinButton.new_with_range(0, 999, 1)
        box.append(Gtk.Label(label=i18n.t("pdf_blank"), xalign=0))
        box.append(self._blank)
        box.append(Gtk.Label(label=i18n.t("pdf_rotate"), xalign=0))
        self._rot = compat.string_choice(["90", "180", "270"])
        box.append(self._rot)
        pages = common.prefs_group("group_pages",
            [
                common.button_row("pdf_info", self._show_info),
                common.button_row("pdf_merge", self._merge, suggested=True),
                common.button_row("pdf_extract", self._extract),
                common.button_row("pdf_split", self._split),
                common.button_row("pdf_rotate", self._rotate),
                common.button_row("pdf_blank_go", self._insert_blank),
                common.button_row("pdf_reorder", self._reorder_pages),
                common.button_row("pdf_extract_images", self._extract_images),
                common.button_row("pdf_inventory", self._inventory),
                common.button_row("pdf_inventory_save", self._inventory_save),
            ],
        )
        security = common.prefs_group("group_security",
            [
                common.button_row("pdf_strip", self._strip),
                common.button_row("pdf_encrypt", self._encrypt),
                common.button_row("pdf_decrypt", self._decrypt),
            ],
        )
        box.append(pages)
        box.append(security)
        return common.scrolled(box)

    def _set_files(self, paths: list[Path]) -> None:
        self._files = paths
        self._refresh_list()
        if paths:
            self._show_info()

    def _refresh_list(self) -> None:
        self._list.set_text("\n".join(f"{i + 1}. {p}" for i, p in enumerate(self._files)) or "—")
        self._sel.set_range(1, max(1, len(self._files)))

    def _move(self, delta: int) -> None:
        if len(self._files) < 2:
            return
        idx = max(0, min(len(self._files) - 1, int(self._sel.get_value()) - 1))
        nxt = idx + delta
        if nxt < 0 or nxt >= len(self._files):
            return
        self._files[idx], self._files[nxt] = self._files[nxt], self._files[idx]
        self._sel.set_value(nxt + 1)
        self._refresh_list()

    def _degrees(self) -> int:
        return (90, 180, 270)[compat.choice_index(self._rot)]

    def _merge(self, *_args: object) -> None:
        files = list(self._files)
        if not files:
            return
        compat.save_file(self._window, "merged.pdf", lambda dest: self._run(lambda: pdfutil.merge(files, dest)))

    def _extract(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        ranges = self._ranges.get_text()
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-pages.pdf",
            lambda dest: self._run(lambda: pdfutil.extract(src, dest, ranges, password=password)),
        )

    def _split(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()
        compat.select_folder(
            self._window,
            lambda folder: self._run(lambda: pdfutil.split_pages(src, folder, password=password)),
        )

    def _rotate(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        deg = self._degrees()
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-rot.pdf",
            lambda dest: self._run(lambda: pdfutil.rotate(src, dest, deg, password=password)),
        )

    def _insert_blank(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        index = int(self._blank.get_value())
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-blank.pdf",
            lambda dest: self._run(lambda: pdfutil.insert_blank(src, dest, index, password=password)),
        )

    def _strip(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-meta.pdf",
            lambda dest: self._run(lambda: pdfutil.strip_metadata(src, dest, password=password)),
        )

    def _encrypt(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-enc.pdf",
            lambda dest: self._run(lambda: pdfutil.encrypt(src, dest, password)),
        )

    def _decrypt(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()
        compat.save_file(
            self._window,
            f"{src.stem}-dec.pdf",
            lambda dest: self._run(lambda: pdfutil.decrypt(src, dest, password)),
        )

    def _reorder_pages(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        spec = self._ranges.get_text().strip()
        password = self._password.get_text()

        def work(dest: Path) -> Path:
            if spec:
                order = [int(part.strip()) for part in spec.split(",") if part.strip()]
            else:
                reader_count = int(pdfutil.info(src, password)["pages"])
                order = list(reversed(range(reader_count)))
            return pdfutil.reorder_pages(src, dest, order, password=password)

        compat.save_file(self._window, f"{src.stem}-reordered.pdf", lambda dest: self._run(lambda: work(dest)))

    def _extract_images(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()
        compat.select_folder(
            self._window,
            lambda folder: self._run(lambda: pdfutil.extract_images(src, folder, password=password)),
        )

    def _inventory(self, *_args: object) -> None:
        files = list(self._files)

        def run(paths: list[Path]) -> None:
            def work() -> str:
                return pdfutil.inventory(paths)

            def done(result: Any, error: BaseException | None) -> None:
                if error is not None:
                    show_toast(self._toast, str(error), 6)
                    return
                text = str(result)
                self._inventory_csv = text
                preview = text if len(text) <= 400 else text[:400] + "…"
                self._info.set_text(preview)
                show_toast(self._toast, "OK")

            run_in_thread(work, done)

        if files:
            run(files)
            return
        compat.select_folder(self._window, lambda folder: run(pdfutil.list_pdfs(folder)))

    def _inventory_save(self, *_args: object) -> None:
        text = self._inventory_csv
        if not text.strip():
            show_toast(self._toast, i18n.t("pdf_inventory"), 4)
            return
        compat.save_file(
            self._window,
            "pdf-inventory.csv",
            lambda dest: dest.write_text(text, encoding="utf-8"),
        )

    def _show_info(self, *_args: object) -> None:
        if not self._files:
            return
        src = self._files[0]
        password = self._password.get_text()

        def work() -> str:
            data = pdfutil.info(src, password)
            return "\n".join(f"{key}: {data[key]}" for key in data)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            self._info.set_text(str(result))

        run_in_thread(work, done)

    def _run(self, fn: Any) -> None:
        def work() -> str:
            result = fn()
            if isinstance(result, list):
                return f"{len(result)} OK"
            return str(result)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            show_toast(self._toast, str(result))

        run_in_thread(work, done)
