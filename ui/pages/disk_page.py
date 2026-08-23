# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from threading import Event
from typing import Any

from gi.repository import GLib, Gtk

from core import diskmap
from core import i18n
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common
from ui.pages.folder_bar import FolderBar


class DiskPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget, settings: dict[str, Any]) -> None:
        self._window = window
        self._toast = toast
        self._settings = settings
        self._entries: list[diskmap.DiskEntry] = []
        self._cancel: Event | None = None
        self._bar = FolderBar(window, settings, on_folder=getattr(window, "notify_folder", None))
        self.widget = self._build()

    def on_folder(self, path: Path) -> None:
        self._bar.set_folder(path, notify=False)

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        hint = common.t_label("disk_hint", wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        map_hint = common.t_label("disk_map_hint", wrap=True, xalign=0)
        map_hint.add_css_class("dim-label")
        box.append(map_hint)
        box.append(self._bar.widget)
        self._skip = common.t_check("disk_skip")
        self._skip.set_active(True)
        box.append(self._skip)
        self._progress = Gtk.ProgressBar()
        box.append(self._progress)
        actions = Gtk.Box(spacing=8)
        scan = common.t_button("disk_scan")
        scan.add_css_class("suggested-action")
        scan.connect("clicked", lambda *_: self._scan())
        cancel = common.t_button("disk_cancel")
        cancel.connect("clicked", lambda *_: self._do_cancel())
        parent = common.t_button("disk_parent")
        parent.connect("clicked", lambda *_: self._parent())
        export = common.t_button("disk_export")
        export.connect("clicked", lambda *_: self._export())
        actions.append(scan)
        actions.append(cancel)
        actions.append(parent)
        actions.append(export)
        box.append(actions)
        self._total = Gtk.Label(xalign=0)
        box.append(self._total)
        self._map = Gtk.DrawingArea()
        self._map.set_content_height(280)
        self._map.set_hexpand(True)
        self._map.set_vexpand(True)
        self._map.add_css_class("card")
        self._map.set_draw_func(self._draw_treemap)
        click = Gtk.GestureClick()
        click.connect("released", self._on_map_click)
        self._map.add_controller(click)
        box.append(self._map)
        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        self._list.connect("row-activated", self._open_row)
        box.append(self._list)
        return common.scrolled(box)

    def _root_path(self) -> Path:
        return self._bar.folder()

    def _do_cancel(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    def _parent(self) -> None:
        current = self._root_path()
        parent = current.parent
        if parent == current or current == Path("/"):
            return
        self._bar.set_folder(parent)
        self._scan()

    def _progress_cb(self, done: int, total: int) -> None:
        def tick() -> bool:
            self._progress.set_fraction(0.0 if total <= 0 else min(1.0, done / total))
            self._progress.set_text(f"{done} / {total}")
            return False

        GLib.idle_add(tick)

    def _scan(self) -> None:
        root = self._root_path()
        if root == Path("/"):
            show_toast(self._toast, i18n.t("disk_no_root"), 6)
            return
        self._bar.set_folder(root)
        skip = self._skip.get_active()
        cancel = Event()
        self._cancel = cancel

        def work() -> tuple[int, list[diskmap.DiskEntry], int]:
            return diskmap.scan_children(root, skip_known=skip, cancel=cancel, on_progress=self._progress_cb)

        def done(result: Any, error: BaseException | None) -> None:
            common.clear_list(self._list)
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            total, entries, hidden = result
            self._entries = entries
            self._total.set_text(
                f"{i18n.t('disk_total')}: {diskmap.human_size(total)} — {len(entries)} ({hidden})"
            )
            self._map.queue_draw()
            for entry in entries:
                row = Gtk.ListBoxRow()
                inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                inner.set_margin_start(10)
                inner.set_margin_end(10)
                inner.set_margin_top(6)
                inner.set_margin_bottom(6)
                kind = "▸ " if entry.is_dir else ""
                lab = Gtk.Label(
                    label=f"{kind}{entry.name}  {diskmap.human_size(entry.size)}  {entry.percent:.1f}%",
                    xalign=0,
                    wrap=True,
                )
                bar = Gtk.LevelBar()
                bar.set_min_value(0)
                bar.set_max_value(100)
                bar.set_value(min(100.0, entry.percent))
                inner.append(lab)
                inner.append(bar)
                row.set_child(inner)
                self._list.append(row)

        run_in_thread(work, done)

    def _draw_treemap(self, _area: Gtk.DrawingArea, cr: object, width: int, height: int) -> None:
        palette = (
            (0.18, 0.42, 0.72),
            (0.16, 0.62, 0.45),
            (0.72, 0.45, 0.16),
            (0.55, 0.28, 0.62),
            (0.22, 0.55, 0.62),
            (0.62, 0.22, 0.32),
        )
        cr.set_source_rgb(0.12, 0.14, 0.16)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        rects = diskmap.treemap_rects(self._entries, float(width), float(height))
        for index, rect in enumerate(rects):
            color = palette[index % len(palette)]
            cr.set_source_rgb(*color)
            cr.rectangle(rect.x + 1, rect.y + 1, max(0.0, rect.w - 2), max(0.0, rect.h - 2))
            cr.fill()
            if rect.w >= 48 and rect.h >= 18:
                cr.set_source_rgb(0.95, 0.96, 0.97)
                cr.move_to(rect.x + 6, rect.y + 14)
                cr.show_text(rect.name[:28])

    def _on_map_click(self, _gesture: Gtk.GestureClick, _n_press: int, x: float, y: float) -> None:
        width = max(1, self._map.get_width())
        height = max(1, self._map.get_height())
        hit = diskmap.hit_treemap(diskmap.treemap_rects(self._entries, float(width), float(height)), x, y)
        if hit is None or not hit.is_dir or hit.path is None:
            return
        if hit.name.startswith("(reste"):
            return
        self._bar.set_folder(hit.path)
        self._scan()

    def _open_row(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        idx = row.get_index()
        if idx < 0 or idx >= len(self._entries):
            return
        entry = self._entries[idx]
        if entry.is_dir and entry.path.name != "(reste)" and not entry.name.startswith("(reste"):
            self._bar.set_folder(entry.path)
            self._scan()

    def _export(self) -> None:
        text = diskmap.export_csv(self._entries)
        compat.save_file(self._window, "diskmap.csv", lambda dest: dest.write_text(text, encoding="utf-8"))
