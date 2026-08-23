# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import fileutil
from core import i18n
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common


class FilePage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self._path: Path | None = None
        self._path_b: Path | None = None
        self._archive_files: list[Path] = []
        self.widget = self._build()

    def receive_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_a(paths[:1])
        if len(paths) > 1:
            self._set_b(paths[1:2])
        self._set_archive(paths)

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        switcher, stack = compat.view_switcher_stack()
        outer.append(switcher)
        stack.add_titled(self._tab_inspect(), "inspect", i18n.t("file_inspect"))
        stack.add_titled(self._tab_archive(), "archive", i18n.t("file_archive"))
        stack.set_vexpand(True)
        outer.append(stack)
        return outer

    def _tab_inspect(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        pick = Gtk.Button(label=i18n.t("add_files"))
        pick.connect("clicked", lambda *_: compat.open_files(self._window, self._set_a))
        pick_b = Gtk.Button(label=i18n.t("hash_file_b"))
        pick_b.connect("clicked", lambda *_: compat.open_files(self._window, self._set_b))
        row = Gtk.Box(spacing=8)
        row.append(pick)
        row.append(pick_b)
        box.append(row)
        self._label = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._label)
        self._mode = Gtk.Entry(placeholder_text="644")
        box.append(self._mode)
        self._chunk = Gtk.SpinButton.new_with_range(1, 512, 1)
        self._chunk.set_value(8)
        box.append(Gtk.Label(label=i18n.t("file_split"), xalign=0))
        box.append(self._chunk)
        inspect = common.prefs_group(
            i18n.t("group_inspect"),
            [
                common.button_row(i18n.t("file_inspect"), self._inspect, suggested=True),
                common.button_row(i18n.t("file_chmod"), self._chmod),
                common.button_row(i18n.t("file_hex"), self._hex),
                common.button_row(i18n.t("file_diff"), self._diff),
                common.button_row(i18n.t("file_encoding"), self._encoding),
                common.button_row(i18n.t("file_touch"), self._touch),
                common.button_row(i18n.t("file_tree_size"), self._tree_size),
                common.button_row(i18n.t("file_flatpak"), self._flatpak),
            ],
        )
        rewrite = common.prefs_group(
            i18n.t("group_rewrite"),
            [
                common.button_row(i18n.t("file_lf"), lambda *_: self._rewrite("lf")),
                common.button_row(i18n.t("file_utf8"), lambda *_: self._rewrite("utf8")),
                common.button_row(i18n.t("file_rstrip"), lambda *_: self._rewrite("rstrip")),
                common.button_row(i18n.t("file_split"), self._split),
                common.button_row(i18n.t("file_join"), self._join),
                common.button_row(i18n.t("file_copy"), self._copy),
            ],
        )
        box.append(inspect)
        box.append(rewrite)
        self._out = Gtk.TextView()
        self._out.set_editable(False)
        self._out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._out))
        return common.scrolled(box)

    def _tab_archive(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        add = Gtk.Button(label=i18n.t("add_files"))
        add.connect("clicked", lambda *_: compat.open_files(self._window, self._set_archive, multiple=True))
        box.append(add)
        self._arc_list = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._arc_list)
        self._filter = Gtk.Entry(placeholder_text=i18n.t("file_filter"))
        box.append(self._filter)
        grid = common.prefs_group(
            i18n.t("group_archive"),
            [
                common.button_row(i18n.t("file_list_arc"), self._list_arc, suggested=True),
                common.button_row(i18n.t("file_make_zip"), self._make_zip),
                common.button_row(i18n.t("file_make_tar"), self._make_tar),
                common.button_row(i18n.t("file_extract"), self._extract),
            ],
        )
        box.append(grid)
        self._arc_out = Gtk.TextView()
        self._arc_out.set_editable(False)
        self._arc_out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._arc_out))
        return common.scrolled(box)

    def _set_a(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._path = paths[0]
        self._label.set_text(str(self._path))
        self._inspect()

    def _set_b(self, paths: list[Path]) -> None:
        if paths:
            self._path_b = paths[0]

    def _set_archive(self, paths: list[Path]) -> None:
        self._archive_files = paths
        self._arc_list.set_text("\n".join(str(p) for p in paths) or "—")

    def _need(self) -> Path | None:
        if self._path is None:
            show_toast(self._toast, i18n.t("add_files"), 4)
        return self._path

    def _inspect(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return

        def work() -> str:
            extra = fileutil.inspect_text(path)
            mime = fileutil.detect_mime_magic(path)
            lines, shebang = fileutil.line_count(path)
            return (
                f"{extra}\nmime: {mime['mime']} hint={mime['hint']} match={mime['match']}\n"
                f"lines: {lines}\nshebang: {shebang or '—'}"
            )

        self._bg(work, self._out)

    def _chmod(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        try:
            fileutil.chmod_path(path, self._mode.get_text())
        except fileutil.FileUtilError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, "OK")
        self._inspect()

    def _hex(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        self._bg(lambda: fileutil.hexdump_file(path), self._out)

    def _diff(self, *_args: object) -> None:
        if self._path is None or self._path_b is None:
            return

        def work() -> str:
            offset = fileutil.first_diff(self._path, self._path_b)
            return i18n.t("hash_same") if offset is None else f"offset {offset}"

        self._bg(work, self._out)

    def _encoding(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        self._bg(lambda: fileutil.guess_encoding(path), self._out)

    def _tree_size(self, *_args: object) -> None:
        targets: list[Path] = []
        if self._path is not None:
            targets.append(self._path)
        elif self._archive_files:
            targets = list(self._archive_files)
        if not targets:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return
        self._bg(lambda: str(fileutil.tree_size(targets)), self._out)

    def _flatpak(self, *_args: object) -> None:
        self._bg(fileutil.flatpak_info, self._out)

    def _touch(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        try:
            fileutil.touch_mtime(path)
        except fileutil.FileUtilError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, "OK")

    def _rewrite(self, mode: str) -> None:
        path = self._need()
        if path is None:
            return
        compat.save_file(
            self._window,
            f"{path.stem}_kit{path.suffix}",
            lambda dest: self._bg(lambda: str(fileutil.rewrite_text(path, dest, mode=mode)), self._out),
        )

    def _split(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        mb = float(self._chunk.get_value())
        compat.select_folder(
            self._window,
            lambda folder: self._bg(lambda: "\n".join(str(p) for p in fileutil.split_file(path, folder, mb)), self._out),
        )

    def _join(self, *_args: object) -> None:
        if not self._archive_files:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return
        parts = list(self._archive_files)
        compat.save_file(
            self._window,
            "joined.bin",
            lambda dest: self._bg(lambda: str(fileutil.join_files(parts, dest)), self._out),
        )

    def _copy(self, *_args: object) -> None:
        path = self._need()
        if path is None:
            return
        compat.select_folder(
            self._window,
            lambda folder: self._bg(lambda: str(fileutil.copy_to(path, folder)), self._out),
        )

    def _list_arc(self, *_args: object) -> None:
        if not self._archive_files:
            return
        src = self._archive_files[0]
        self._bg(lambda: "\n".join(fileutil.list_archive(src)), self._arc_out)

    def _make_zip(self, *_args: object) -> None:
        files = list(self._archive_files)
        if not files:
            return
        compat.save_file(
            self._window,
            "archive.zip",
            lambda dest: self._bg(lambda: str(fileutil.create_zip(files, dest)), self._arc_out),
        )

    def _make_tar(self, *_args: object) -> None:
        files = list(self._archive_files)
        if not files:
            return
        compat.save_file(
            self._window,
            "archive.tar.gz",
            lambda dest: self._bg(lambda: str(fileutil.create_tar_gz(files, dest)), self._arc_out),
        )

    def _extract(self, *_args: object) -> None:
        if not self._archive_files:
            return
        src = self._archive_files[0]
        needle = self._filter.get_text()
        compat.select_folder(
            self._window,
            lambda folder: self._bg(
                lambda: "\n".join(str(p) for p in fileutil.extract_archive(src, folder, name_filter=needle)),
                self._arc_out,
            ),
        )

    def _bg(self, fn: Any, view: Gtk.TextView) -> None:
        def work() -> str:
            return str(fn())

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            view.get_buffer().set_text(str(result))
            show_toast(self._toast, "OK")

        run_in_thread(work, done)
