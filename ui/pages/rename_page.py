# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import find as find_core
from core import i18n
from core import rename as rename_core
from core import settings as app_settings
from ui import compat
from ui.helpers import show_toast
from ui.pages import common
from ui.pages.folder_bar import FolderBar

_CASES = ("", "lower", "upper", "title", "snake", "kebab")
_COLLISIONS = ("suffix", "skip")


class RenamePage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget, settings: dict[str, Any]) -> None:
        self._window = window
        self._toast = toast
        self._settings = settings
        self._files: list[Path] = []
        self._copy_dir: Path | None = None
        self._bar = FolderBar(window, settings, on_folder=getattr(window, "notify_folder", None))
        self.widget = self._build()

    def on_folder(self, path: Path) -> None:
        self._bar.set_folder(path, notify=False)

    def receive_paths(self, paths: list[Path]) -> None:
        self._files = list(paths)
        self._preview()

    def _build(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        box.append(self._bar.widget)
        sources = Gtk.Box(spacing=8)
        add = common.t_button("add_files")
        add.connect("clicked", lambda *_: compat.open_files(self._window, self._set_files, multiple=True))
        from_folder = common.t_button("rename_from_folder")
        from_folder.connect("clicked", lambda *_: self._from_folder())
        sources.append(add)
        sources.append(from_folder)
        box.append(sources)
        hint = common.t_label("rename_tokens", wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        self._pat = common.t_entry("rename_pattern")
        self._pat.set_text("(.*)\\.(\\w+)$")
        self._repl = common.t_entry("rename_repl")
        self._repl.set_text(r"\1_{n:03d}.\2")
        box.append(self._pat)
        box.append(self._repl)
        affix = Gtk.Box(spacing=8)
        self._prefix = common.t_entry("rename_prefix")
        self._suffix = common.t_entry("rename_suffix")
        affix.append(self._prefix)
        affix.append(self._suffix)
        box.append(affix)
        box.append(common.t_label("rename_case", xalign=0))
        self._case = compat.string_choice(["—", "lower", "UPPER", "Title", "snake", "kebab"])
        box.append(self._case)
        box.append(common.t_label("rename_collision", xalign=0))
        self._collision = compat.string_choice([i18n.t("rename_suffix_n"), i18n.t("rename_skip")])
        box.append(self._collision)
        self._sanitize = common.t_check("rename_sanitize")
        box.append(self._sanitize)
        self._overwrite = common.t_check("rename_overwrite")
        box.append(self._overwrite)
        self._copies = common.t_check("rename_copies")
        box.append(self._copies)
        copy_btn = common.t_button("rename_out_folder")
        copy_btn.connect("clicked", lambda *_: compat.select_folder(self._window, self._set_copy_dir))
        box.append(copy_btn)
        self._copy_label = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._copy_label)
        self._preset_name = common.t_entry("rename_preset_name")
        box.append(self._preset_name)
        preset_row = Gtk.Box(spacing=8)
        load_preset = common.t_button("rename_preset_load")
        load_preset.connect("clicked", lambda *_: self._load_preset())
        save_preset = common.t_button("rename_preset_save")
        save_preset.connect("clicked", lambda *_: self._save_preset())
        import_csv = common.t_button("rename_csv_import")
        import_csv.connect("clicked", lambda *_: compat.open_files(self._window, self._import_csv))
        preset_row.append(load_preset)
        preset_row.append(save_preset)
        preset_row.append(import_csv)
        box.append(preset_row)
        actions = Gtk.Box(spacing=8)
        prev = common.t_button("rename_preview")
        prev.connect("clicked", lambda *_: self._preview())
        apply_btn = common.t_button("rename_apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", lambda *_: self._apply())
        undo = common.t_button("rename_undo")
        undo.connect("clicked", lambda *_: self._undo())
        actions.append(prev)
        actions.append(apply_btn)
        actions.append(undo)
        box.append(actions)
        self._list = Gtk.ListBox()
        self._list.add_css_class("boxed-list")
        box.append(self._list)
        compat.enable_file_drop(box, self._set_files)
        return common.scrolled(box)

    def _set_copy_dir(self, folder: Path) -> None:
        self._copy_dir = folder
        self._copy_label.set_text(str(folder))

    def _opts(self) -> dict[str, object]:
        case_idx = compat.choice_index(self._case)
        col_idx = compat.choice_index(self._collision)
        collision = _COLLISIONS[col_idx] if 0 <= col_idx < len(_COLLISIONS) else "suffix"
        if self._overwrite.get_active():
            collision = "overwrite"
        return {
            "case_mode": _CASES[case_idx] if 0 <= case_idx < len(_CASES) else "",
            "prefix": self._prefix.get_text(),
            "suffix": self._suffix.get_text(),
            "sanitize": self._sanitize.get_active(),
            "collision": collision,
        }

    def _set_files(self, paths: list[Path]) -> None:
        self._files = paths
        self._preview()

    def _from_folder(self) -> None:
        hits = find_core.list_files(self._bar.folder(), limit=app_settings.search_limit(self._settings))
        self._files = hits.paths
        self._preview()
        if hits.truncated:
            show_toast(self._toast, i18n.t("hits_truncated", count=len(hits.paths), limit=hits.limit), 5)

    def _save_preset(self) -> None:
        name = self._preset_name.get_text().strip()
        if not name:
            show_toast(self._toast, i18n.t("rename_preset_name"), 4)
            return
        rename_core.save_preset(
            name,
            {
                "pattern": self._pat.get_text(),
                "repl": self._repl.get_text(),
                "prefix": self._prefix.get_text(),
                "suffix": self._suffix.get_text(),
            },
        )
        show_toast(self._toast, i18n.t("prefs_saved"))

    def _load_preset(self) -> None:
        name = self._preset_name.get_text().strip()
        presets = rename_core.load_presets()
        data = presets.get(name)
        if not data:
            show_toast(self._toast, i18n.t("rename_preset_missing"), 4)
            return
        self._pat.set_text(data.get("pattern", ""))
        self._repl.set_text(data.get("repl", ""))
        self._prefix.set_text(data.get("prefix", ""))
        self._suffix.set_text(data.get("suffix", ""))
        self._preview()

    def _import_csv(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            mapping = rename_core.parse_rename_csv(paths[0].read_text(encoding="utf-8"))
        except OSError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        if not mapping:
            show_toast(self._toast, i18n.t("find_empty"), 4)
            return
        try:
            rows = rename_core.preview_from_csv(self._files, mapping, **self._opts())
        except rename_core.RenameError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        common.clear_list(self._list)
        for src, new in rows:
            row = Gtk.ListBoxRow()
            lab = Gtk.Label(label=f"{src.name} → {new}", xalign=0, wrap=True)
            lab.set_margin_start(10)
            lab.set_margin_end(10)
            lab.set_margin_top(6)
            lab.set_margin_bottom(6)
            row.set_child(lab)
            self._list.append(row)

    def _preview(self) -> None:
        common.clear_list(self._list)
        if not self._files:
            return
        try:
            rows = rename_core.preview(self._files, self._pat.get_text(), self._repl.get_text(), **self._opts())
        except rename_core.RenameError as exc:
            self._list.append(Gtk.Label(label=str(exc), wrap=True, xalign=0, margin_top=8, margin_bottom=8))
            return
        for src, new in rows:
            row = Gtk.ListBoxRow()
            lab = Gtk.Label(label=f"{src.name} → {new}", xalign=0, wrap=True)
            lab.set_margin_start(10)
            lab.set_margin_end(10)
            lab.set_margin_top(6)
            lab.set_margin_bottom(6)
            row.set_child(lab)
            self._list.append(row)

    def _apply(self) -> None:
        def on_resp(response: str) -> None:
            if response != "now":
                return
            self._apply_now()

        compat.present_alert(
            self._window,
            i18n.t("rename_apply_confirm"),
            i18n.t("rename_apply_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("confirm"))],
            suggested="now",
            on_response=on_resp,
        )

    def _apply_now(self) -> None:
        overwrite = self._overwrite.get_active()
        try:
            rows = rename_core.preview(self._files, self._pat.get_text(), self._repl.get_text(), **self._opts())
            if self._copies.get_active():
                if self._copy_dir is None:
                    show_toast(self._toast, i18n.t("rename_out_folder"), 5)
                    return
                done = rename_core.apply_copies(rows, self._copy_dir, overwrite=overwrite)
            else:
                done = rename_core.apply(rows, overwrite=overwrite)
        except rename_core.RenameError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        if not self._copies.get_active():
            self._files = done
        self._preview()
        show_toast(self._toast, f"{len(done)} OK")

    def _undo(self) -> None:
        try:
            done = rename_core.undo_last()
        except rename_core.RenameError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        self._files = done
        self._preview()
        show_toast(self._toast, f"{len(done)} OK")
