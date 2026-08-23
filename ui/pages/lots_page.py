# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import GLib, Gtk

from core import batchutil
from core import find as find_core
from core import i18n
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common
from ui.pages.folder_bar import FolderBar


class LotsPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget, settings: dict[str, Any]) -> None:
        self._window = window
        self._toast = toast
        self._settings = settings
        self._paths: list[Path] = []
        self._groups: list[list[Path]] = []
        self._group_checks: list[Gtk.CheckButton] = []
        self._selection: list[Path] | None = None
        self._bar = FolderBar(window, settings, on_folder=getattr(window, "notify_folder", None))
        self.widget = self._build()

    def on_folder(self, path: Path) -> None:
        self._bar.set_folder(path, notify=False)

    def receive_paths(self, paths: list[Path]) -> None:
        self._selection = list(paths)
        self._bg(lambda: batchutil.sha256_duplicates_paths(list(paths)), groups=True)

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        box.append(self._bar.widget)
        nums = Gtk.Box(spacing=8)
        self._days = Gtk.SpinButton.new_with_range(1, 3650, 1)
        self._days.set_value(30)
        self._mb = Gtk.SpinButton.new_with_range(1, 10240, 1)
        self._mb.set_value(50)
        nums.append(Gtk.Label(label=i18n.t("lots_days")))
        nums.append(self._days)
        nums.append(Gtk.Label(label=i18n.t("lots_mb")))
        nums.append(self._mb)
        box.append(nums)
        self._progress = Gtk.ProgressBar()
        self._progress.set_show_text(True)
        box.append(self._progress)
        scan = common.prefs_group(
            i18n.t("group_actions"),
            [
                common.button_row(i18n.t("lots_dupes"), self._dupes, suggested=True),
                common.button_row(i18n.t("lots_names"), self._names),
                common.button_row(i18n.t("lots_empty"), self._empty),
                common.button_row(i18n.t("lots_old"), self._old),
                common.button_row(i18n.t("lots_large"), self._large),
                common.button_row(i18n.t("lots_stats"), self._stats),
                common.button_row(i18n.t("lots_broken"), self._broken),
                common.button_row(i18n.t("lots_trash"), self._trash),
            ],
        )
        act = common.prefs_group(
            i18n.t("group_export"),
            [
                common.button_row(i18n.t("hash_manifest"), self._manifest),
                common.button_row(i18n.t("lots_move"), self._move),
                common.button_row(i18n.t("lots_export"), self._export),
            ],
        )
        box.append(scan)
        box.append(act)
        self._count = Gtk.Label(xalign=0)
        box.append(self._count)
        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        box.append(self._list)
        self._out = Gtk.TextView()
        self._out.set_editable(False)
        self._out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._out.set_visible(False)
        box.append(common.scrolled(self._out))
        return common.scrolled(box)

    def _root_path(self) -> Path:
        return self._bar.folder()

    def _set_progress(self, done: int, total: int) -> None:
        frac = 0.0 if total <= 0 else min(1.0, done / total)
        self._progress.set_fraction(frac)
        self._progress.set_text(f"{done} / {total}")

    def _set_hits(self, truncated: bool, count: int, limit: int) -> None:
        key = "hits_truncated" if truncated else "hits_count"
        self._count.set_text(i18n.t(key, count=count, limit=limit) if limit else "")

    def _show_paths(self, paths: list[Path], *, truncated: bool = False, limit: int = 0) -> None:
        self._paths = paths
        self._groups = []
        self._group_checks = []
        common.clear_list(self._list)
        self._set_hits(truncated, len(paths), limit)
        self._out.set_visible(False)
        for path in paths:
            row = Gtk.ListBoxRow()
            lab = Gtk.Label(label=str(path), xalign=0, wrap=True)
            lab.set_margin_start(10)
            lab.set_margin_end(10)
            lab.set_margin_top(6)
            lab.set_margin_bottom(6)
            row.set_child(lab)
            self._list.append(row)
        self._out.get_buffer().set_text("")

    def _show_groups(self, groups: list[list[Path]], *, truncated: bool = False, limit: int = 0) -> None:
        self._groups = groups
        self._group_checks = []
        self._paths = [path for group in groups for path in group]
        common.clear_list(self._list)
        self._set_hits(truncated, len(self._paths), limit)
        self._out.set_visible(False)
        for group in groups:
            header = Gtk.ListBoxRow()
            header.set_selectable(False)
            inner = Gtk.Box(spacing=8)
            check = Gtk.CheckButton()
            check.set_active(True)
            title = Gtk.Label(
                label=i18n.t("lots_group", count=len(group)),
                xalign=0,
                margin_start=4,
                margin_end=10,
                margin_top=8,
                margin_bottom=4,
            )
            title.add_css_class("heading")
            inner.append(check)
            inner.append(title)
            header.set_child(inner)
            self._list.append(header)
            self._group_checks.append(check)
            for path in group:
                row = Gtk.ListBoxRow()
                lab = Gtk.Label(label=str(path), xalign=0, wrap=True)
                lab.set_margin_start(18)
                lab.set_margin_end(10)
                lab.set_margin_top(4)
                lab.set_margin_bottom(4)
                row.set_child(lab)
                self._list.append(row)
        self._out.get_buffer().set_text("")

    def _dupes(self, *_args: object) -> None:
        if self._selection:
            paths = list(self._selection)
            self._bg(lambda: batchutil.sha256_duplicates_paths(paths, on_progress=self._progress_cb), groups=True)
            return
        root = self._root_path()
        self._bg(lambda: batchutil.sha256_duplicates(root, on_progress=self._progress_cb), groups=True)

    def _progress_cb(self, done: int, total: int) -> None:
        GLib.idle_add(lambda: self._set_progress(done, total) or False)

    def _names(self, *_args: object) -> None:
        root = self._root_path()
        self._bg(lambda: batchutil.same_names(root), groups=True)

    def _empty(self, *_args: object) -> None:
        root = self._root_path()
        self._bg(lambda: list(batchutil.empty_folders(root).paths))

    def _old(self, *_args: object) -> None:
        root = self._root_path()
        days = float(self._days.get_value())
        self._bg(lambda: batchutil.older_than(root, days))

    def _large(self, *_args: object) -> None:
        root = self._root_path()
        mb = float(self._mb.get_value())
        self._bg(lambda: batchutil.larger_than(root, mb))

    def _broken(self, *_args: object) -> None:
        root = self._root_path()
        self._bg(lambda: batchutil.broken_symlinks(root))

    def _trash(self, *_args: object) -> None:
        def work() -> str:
            return batchutil.trash_peek_text()

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            self._out.set_visible(True)
            self._out.get_buffer().set_text(str(result))
            show_toast(self._toast, "OK")

        run_in_thread(work, done)

    def _stats(self, *_args: object) -> None:
        root = self._root_path()

        def work() -> str:
            return batchutil.stats_text(root)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            self._out.set_visible(True)
            self._out.get_buffer().set_text(str(result))

        run_in_thread(work, done)

    def _manifest(self, *_args: object) -> None:
        root = self._root_path()

        def work() -> str:
            return batchutil.write_manifest(root, on_progress=self._progress_cb)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            compat.save_file(
                self._window,
                "checksums.sha256",
                lambda dest: dest.write_text(str(result), encoding="utf-8"),
            )

        run_in_thread(work, done)

    def _move(self, *_args: object) -> None:
        groups = [
            group
            for group, check in zip(self._groups, self._group_checks)
            if check.get_active()
        ]
        if not groups:
            show_toast(self._toast, i18n.t("lots_dupes"), 4)
            return

        def on_resp(response: str) -> None:
            if response != "now":
                return
            compat.select_folder(
                self._window,
                lambda folder: self._bg(lambda: batchutil.move_copies(groups, folder)),
            )

        compat.present_alert(
            self._window,
            i18n.t("lots_move_confirm"),
            i18n.t("lots_move_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("lots_move"))],
            suggested="now",
            on_response=on_resp,
        )

    def _export(self, *_args: object) -> None:
        text = batchutil.export_paths(self._paths, csv_mode=True)
        compat.save_file(self._window, "lots.csv", lambda dest: dest.write_text(text, encoding="utf-8"))

    def _bg(self, fn: Any, *, groups: bool = False) -> None:
        def work() -> Any:
            return fn()

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            if isinstance(result, batchutil.GroupHits):
                self._show_groups(result.groups, truncated=result.truncated, limit=result.limit)
            elif groups and isinstance(result, list):
                self._show_groups(result)
            elif isinstance(result, find_core.PathHits):
                self._show_paths(result.paths, truncated=result.truncated, limit=result.limit)
            elif isinstance(result, list) and result and isinstance(result[0], Path):
                self._show_paths(result)
            else:
                self._out.set_visible(True)
                self._out.get_buffer().set_text(str(result))
            show_toast(self._toast, "OK")

        run_in_thread(work, done)
