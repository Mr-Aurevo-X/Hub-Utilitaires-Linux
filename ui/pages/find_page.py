# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any, Callable

from gi.repository import Gio, Gtk

from core import find as find_core
from core import i18n
from core import settings as app_settings
from core.workset import SendTarget
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common
from ui.pages.folder_bar import FolderBar

SendFn = Callable[[SendTarget, list[Path]], None]


class FindPage:
    def __init__(
        self,
        window: Gtk.Window,
        toast: Gtk.Widget,
        settings: dict[str, Any],
        *,
        on_send: SendFn | None = None,
    ) -> None:
        self._window = window
        self._toast = toast
        self._settings = settings
        self._on_send = on_send
        self._files: list[Path] = []
        self._checks: list[Gtk.CheckButton] = []
        self._bar = FolderBar(window, settings, on_folder=getattr(window, "notify_folder", None))
        self.widget = self._build()

    def on_folder(self, path: Path) -> None:
        self._bar.set_folder(path, notify=False)

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        hint = common.t_label("find_hint", wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        box.append(self._bar.widget)
        self._query = common.t_entry("find_query")
        self._query.connect("activate", lambda *_: self._run())
        self._content = common.t_entry("find_content")
        self._content.connect("activate", lambda *_: self._run())
        box.append(self._query)
        box.append(self._content)
        filt = Gtk.Box(spacing=8)
        self._ext = common.t_entry("find_ext")
        self._min_size = common.t_entry("find_min_size")
        self._max_size = common.t_entry("find_max_size")
        filt.append(self._ext)
        filt.append(self._min_size)
        filt.append(self._max_size)
        box.append(filt)
        dates = Gtk.Box(spacing=8)
        self._min_date = common.t_entry("find_min_date")
        self._max_date = common.t_entry("find_max_date")
        dates.append(self._min_date)
        dates.append(self._max_date)
        box.append(dates)
        self._hidden = common.t_check("find_hidden")
        self._empty = common.t_check("find_empty_dirs")
        box.append(self._hidden)
        box.append(self._empty)
        go = common.t_button("find_go")
        go.add_css_class("suggested-action")
        go.connect("clicked", lambda *_: self._run())
        pin = Gtk.Button(icon_name="starred-symbolic")
        pin.set_tooltip_text(i18n.t("find_search_favorite"))
        pin.connect("clicked", self._toggle_search_favorite)
        self._search_fav_btn = Gtk.MenuButton()
        self._search_fav_btn.set_icon_name("starred-symbolic")
        self._search_fav_btn.set_tooltip_text(i18n.t("find_search_favorites"))
        self._search_fav_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        popover = Gtk.Popover()
        popover.set_child(self._search_fav_box)
        self._search_fav_btn.set_popover(popover)
        actions = Gtk.Box(spacing=8)
        actions.append(go)
        actions.append(pin)
        actions.append(self._search_fav_btn)
        box.append(actions)
        self._rebuild_search_favorites()
        self._count = Gtk.Label(xalign=0)
        box.append(self._count)
        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        self._list.connect("row-activated", self._open_row)
        box.append(self._list)
        send = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        row_a = Gtk.Box(spacing=8)
        export_btn = Gtk.Button(label=i18n.t("export"))
        export_btn.connect("clicked", lambda *_: self._export())
        export_json_btn = Gtk.Button(label=i18n.t("find_export_json"))
        export_json_btn.connect("clicked", lambda *_: self._export_json())
        row_a.append(export_btn)
        row_a.append(export_json_btn)
        row_b = Gtk.Box(spacing=8)
        for index, (target, key) in enumerate(
            (
                ("rename", "send_rename"),
                ("lots", "send_lots"),
                ("hash", "send_hash"),
                ("resize", "send_images"),
                ("pdf", "send_pdf"),
                ("file", "send_file"),
                ("textdiff", "send_textdiff"),
            )
        ):
            btn = Gtk.Button(label=i18n.t(key))
            btn.connect("clicked", lambda *_a, dest=target: self._send(dest))
            (row_a if index < 3 else row_b).append(btn)
        send.append(row_a)
        send.append(row_b)
        box.append(send)
        self._needle = Gtk.Entry(placeholder_text=i18n.t("find_replace"))
        self._repl = Gtk.Entry(placeholder_text=i18n.t("find_replace_with"))
        self._overwrite = Gtk.CheckButton(label=i18n.t("overwrite"))
        self._regex = Gtk.CheckButton(label=i18n.t("find_replace_regex"))
        preview = Gtk.Button(label=i18n.t("rename_preview"))
        preview.connect("clicked", lambda *_: self._replace(preview_only=True))
        apply_btn = Gtk.Button(label=i18n.t("find_replace_go"))
        apply_btn.connect("clicked", lambda *_: self._replace(preview_only=False))
        repl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        repl_box.append(self._needle)
        repl_box.append(self._repl)
        repl_box.append(self._overwrite)
        repl_box.append(self._regex)
        repl_actions = Gtk.Box(spacing=8)
        repl_actions.append(preview)
        repl_actions.append(apply_btn)
        repl_box.append(repl_actions)
        expand = common.t_expander("group_replace")
        expand.set_child(repl_box)
        box.append(expand)
        return common.scrolled(box)

    def _filters(self) -> dict[str, Any]:
        def as_int(raw: str) -> int | None:
            text = raw.strip()
            if not text:
                return None
            return int(float(text))

        return {
            "extensions": self._ext.get_text(),
            "min_bytes": as_int(self._min_size.get_text()),
            "max_bytes": as_int(self._max_size.get_text()),
            "min_mtime": self._min_date.get_text().strip() or None,
            "max_mtime": self._max_date.get_text().strip() or None,
            "include_hidden": self._hidden.get_active(),
            "limit": app_settings.search_limit(self._settings),
        }

    def _run(self) -> None:
        root = self._bar.folder()
        query = self._query.get_text()
        content = self._content.get_text()
        empty = self._empty.get_active()
        try:
            filters = self._filters()
        except ValueError as exc:
            show_toast(self._toast, str(exc), 5)
            return
        show_toast(self._toast, i18n.t("find_go"))

        def work() -> find_core.PathHits:
            if empty:
                return find_core.empty_dirs(root, include_hidden=bool(filters["include_hidden"]), limit=int(filters["limit"]))
            if content.strip():
                return find_core.search_content(root, content, **filters)
            return find_core.search_names(root, query, **filters)

        def done(result: Any, error: BaseException | None) -> None:
            common.clear_list(self._list)
            self._checks = []
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            hits = result if isinstance(result, find_core.PathHits) else find_core.PathHits([], False, 0)
            self._files = hits.paths
            key = "hits_truncated" if hits.truncated else "hits_count"
            self._count.set_text(i18n.t(key, count=len(hits.paths), limit=hits.limit))
            if not hits.paths:
                self._list.append(Gtk.Label(label=i18n.t("find_empty"), margin_top=8, margin_bottom=8))
                return
            for path in hits.paths:
                row = Gtk.ListBoxRow()
                inner = Gtk.Box(spacing=8)
                check = Gtk.CheckButton()
                check.set_active(True)
                lab = Gtk.Label(label=str(path), xalign=0, wrap=True)
                lab.set_hexpand(True)
                inner.append(check)
                inner.append(lab)
                row.set_child(inner)
                self._list.append(row)
                self._checks.append(check)

        run_in_thread(work, done)

    def _checked(self) -> list[Path]:
        return [path for path, check in zip(self._files, self._checks) if check.get_active()]

    def _send(self, target: SendTarget) -> None:
        paths = self._checked()
        if not paths or self._on_send is None:
            show_toast(self._toast, i18n.t("find_empty"), 4)
            return
        self._on_send(target, paths)

    def _replace(self, *, preview_only: bool) -> None:
        paths = self._checked()
        needle = self._needle.get_text()
        repl = self._repl.get_text()
        overwrite = self._overwrite.get_active()
        regex = self._regex.get_active()

        def work() -> str:
            rows = find_core.replace_preview(paths, needle, repl, regex=regex)
            if preview_only:
                return "\n".join(f"{path} ×{count}" for path, count in rows) or i18n.t("find_empty")
            done = find_core.replace_apply(paths, needle, repl, overwrite=overwrite, regex=regex)
            return f"{len(done)} OK"

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            if preview_only:
                compat.present_text(self._window, i18n.t("rename_preview"), str(result))
                return
            show_toast(self._toast, str(result))

        if preview_only:
            run_in_thread(work, done)
            return

        def on_resp(response: str) -> None:
            if response != "now":
                return
            run_in_thread(work, done)

        compat.present_alert(
            self._window,
            i18n.t("find_replace_confirm"),
            i18n.t("find_replace_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("confirm"))],
            suggested="now",
            on_response=on_resp,
        )

    def _export(self) -> None:
        text = find_core.export_paths(self._files, csv_mode=True)
        compat.save_file(self._window, "find.csv", lambda dest: dest.write_text(text, encoding="utf-8"))

    def _export_json(self) -> None:
        text = find_core.export_paths(self._files, json_mode=True)
        compat.save_file(self._window, "find.json", lambda dest: dest.write_text(text, encoding="utf-8"))

    def _toggle_search_favorite(self, *_args: object) -> None:
        app_settings.toggle_favorite_search(
            self._settings,
            folder=str(self._bar.folder()),
            query=self._query.get_text(),
            content=self._content.get_text(),
        )
        app_settings.save_settings(self._settings)
        self._rebuild_search_favorites()
        show_toast(self._toast, i18n.t("find_search_favorites"))

    def _rebuild_search_favorites(self) -> None:
        child = self._search_fav_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self._search_fav_box.remove(child)
            child = nxt
        favs = app_settings.favorite_searches(self._settings)
        if not favs:
            self._search_fav_box.append(
                Gtk.Label(label=i18n.t("find_search_empty"), margin_top=8, margin_bottom=8, margin_start=8, margin_end=8)
            )
            return
        self._search_fav_box.append(Gtk.Label(label=i18n.t("find_search_favorites"), xalign=0, margin_start=8))
        for item in favs:
            label = item["query"] or item["content"] or item["folder"]
            btn = Gtk.Button(label=label)
            btn.add_css_class("flat")
            btn.connect("clicked", lambda *_a, row=item: self._apply_search_favorite(row))
            self._search_fav_box.append(btn)

    def _apply_search_favorite(self, item: dict[str, str]) -> None:
        if item["folder"]:
            self._bar.set_folder(Path(item["folder"]))
        self._query.set_text(item["query"])
        self._content.set_text(item["content"])
        self._run()

    def _open_row(self, _box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        idx = row.get_index()
        if idx < 0 or idx >= len(self._files):
            return
        Gio.AppInfo.launch_default_for_uri(self._files[idx].as_uri(), None)
