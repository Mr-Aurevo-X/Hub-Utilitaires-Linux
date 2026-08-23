# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import hashutil
from core import i18n
from ui import compat
from ui.helpers import run_in_thread, show_toast
from ui.pages import common


class HashPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self._path_a: Path | None = None
        self._path_b: Path | None = None
        self._dir_a: Path | None = None
        self._dir_b: Path | None = None
        self.widget = self._build()

    def receive_paths(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._set_a(paths[:1])
        if len(paths) > 1:
            self._set_b(paths[1:2])

    def _build(self) -> Gtk.Widget:
        a_btn = Gtk.Button(label=i18n.t("hash_file"))
        a_btn.connect("clicked", lambda *_: compat.open_files(self._window, self._set_a))
        b_btn = Gtk.Button(label=i18n.t("hash_file_b"))
        b_btn.connect("clicked", lambda *_: compat.open_files(self._window, self._set_b))
        files = common.prefs_group("group_files",
            [common.action_row("hash_file", a_btn), common.action_row("hash_file_b", b_btn)],
        )
        self._label_a = Gtk.Label(label="A —", wrap=True, xalign=0)
        self._label_b = Gtk.Label(label="B —", wrap=True, xalign=0)
        self._sha256 = Gtk.Entry(placeholder_text="SHA-256")
        self._sha512 = Gtk.Entry(placeholder_text="SHA-512")
        self._blake = Gtk.Entry(placeholder_text="BLAKE2b")
        self._crc = Gtk.Entry(placeholder_text="CRC32")
        self._md5 = Gtk.Entry(placeholder_text=i18n.t("hash_md5"))
        self._sha1 = Gtk.Entry(placeholder_text=i18n.t("hash_sha1"))
        digest_rows: list[Gtk.Widget] = []
        for title, entry in (
            ("SHA-256", self._sha256),
            ("SHA-512", self._sha512),
            ("BLAKE2b", self._blake),
            ("CRC32", self._crc),
            (i18n.t("hash_md5"), self._md5),
            (i18n.t("hash_sha1"), self._sha1),
        ):
            copy = Gtk.Button(label=i18n.t("copy"))
            copy.connect("clicked", lambda *_a, src=entry: common.copy_text(src.get_text(), self._toast))
            row = common.action_row(title, copy)
            row.add_suffix(entry)
            digest_rows.append(row)
        digests = common.prefs_group("group_digests", digest_rows)
        self._hmac_key = Gtk.Entry(placeholder_text=i18n.t("hash_hmac_key"))
        self._hmac = Gtk.Entry(placeholder_text=i18n.t("hash_hmac"))
        self._expect = Gtk.Entry(placeholder_text=i18n.t("hash_compare"))
        go = Gtk.Button(label=i18n.t("hash_run"))
        go.add_css_class("suggested-action")
        go.connect("clicked", lambda *_: self._hash_a())
        cmp_btn = Gtk.Button(label=i18n.t("hash_compare_files"))
        cmp_btn.connect("clicked", lambda *_: self._compare())
        man = Gtk.Button(label=i18n.t("hash_manifest"))
        man.connect("clicked", lambda *_: self._manifest())
        verify = Gtk.Button(label=i18n.t("hash_verify"))
        verify.connect("clicked", lambda *_: self._verify())
        dir_a_btn = Gtk.Button(label=i18n.t("hash_dir_a"))
        dir_a_btn.connect("clicked", lambda *_: compat.select_folder(self._window, self._set_dir_a))
        dir_b_btn = Gtk.Button(label=i18n.t("hash_dir_b"))
        dir_b_btn.connect("clicked", lambda *_: compat.select_folder(self._window, self._set_dir_b))
        compare = common.prefs_group("group_compare",
            [
                common.action_row("hash_run", go),
                common.action_row("hash_compare_files", cmp_btn),
                common.action_row("hash_manifest", man),
                common.action_row("hash_verify", verify),
                common.action_row("hash_dir_a", dir_a_btn),
                common.action_row("hash_dir_b", dir_b_btn),
                common.button_row("hash_compare_dirs", self._compare_dirs),
                common.button_row("hash_sha256sums", self._sha256sums),
            ],
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        box.append(files)
        box.append(self._label_a)
        box.append(self._label_b)
        box.append(digests)
        box.append(self._hmac_key)
        box.append(self._hmac)
        box.append(self._expect)
        box.append(compare)
        self._status = Gtk.Label(xalign=0, wrap=True)
        box.append(self._status)
        self._verify_list = Gtk.ListBox()
        self._verify_list.add_css_class("boxed-list")
        box.append(self._verify_list)
        compat.enable_file_drop(box, self._set_a)
        return common.scrolled(box)

    def _set_a(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._path_a = paths[0]
        self._label_a.set_text(f"A — {self._path_a}")
        self._hash_a()

    def _set_b(self, paths: list[Path]) -> None:
        if not paths:
            return
        self._path_b = paths[0]
        self._label_b.set_text(f"B — {self._path_b}")

    def _set_dir_a(self, folder: Path) -> None:
        self._dir_a = folder
        self._label_a.set_text(f"A — {folder}")

    def _set_dir_b(self, folder: Path) -> None:
        self._dir_b = folder
        self._label_b.set_text(f"B — {folder}")

    def _hash_a(self) -> None:
        path = self._path_a
        if path is None:
            return
        key = self._hmac_key.get_text()

        def work() -> dict[str, str]:
            out = {
                "sha256": hashutil.file_hash(path, "sha256"),
                "sha512": hashutil.file_hash(path, "sha512"),
                "blake2b": hashutil.file_hash(path, "blake2b"),
                "crc32": hashutil.file_hash(path, "crc32"),
                "md5": hashutil.file_hash(path, "md5"),
                "sha1": hashutil.file_hash(path, "sha1"),
            }
            if key:
                out["hmac"] = hashutil.file_hmac(path, key, "sha256")
            return out

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            self._sha256.set_text(result["sha256"])
            self._sha512.set_text(result["sha512"])
            self._blake.set_text(result["blake2b"])
            self._crc.set_text(result["crc32"])
            self._md5.set_text(result["md5"])
            self._sha1.set_text(result["sha1"])
            self._hmac.set_text(result.get("hmac", ""))
            expect = "".join(self._expect.get_text().split()).lower()
            if not expect:
                line = self._expect.get_text()
                if line.strip() and " " in line.strip():
                    ok = hashutil.matches_manifest_line(path, line)
                    self._status.set_text(i18n.t("hash_ok") if ok else i18n.t("hash_bad"))
                    return
                self._status.set_text("")
                return
            values = {result["sha256"], result["sha512"], result["blake2b"], result["crc32"], result["md5"], result["sha1"]}
            if result.get("hmac"):
                values.add(result["hmac"])
            ok = expect in {item.lower() for item in values}
            self._status.set_text(i18n.t("hash_ok") if ok else i18n.t("hash_bad"))

        run_in_thread(work, done)

    def _compare(self) -> None:
        left, right = self._path_a, self._path_b
        if left is None or right is None:
            return

        def work() -> tuple[str, str, bool]:
            return hashutil.compare_files(left, right, "sha256")

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            ha, _hb, same = result
            self._sha256.set_text(ha)
            self._status.set_text(i18n.t("hash_same") if same else i18n.t("hash_diff"))

        run_in_thread(work, done)

    def _compare_dirs(self, *_args: object) -> None:
        left, right = self._dir_a, self._dir_b
        if left is None or right is None:
            show_toast(self._toast, i18n.t("pick_folder"), 4)
            return

        def work() -> list[tuple[str, str]]:
            return hashutil.compare_directories(left, right)

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            lines = [f"{state}  {name}" for name, state in result]
            self._status.set_text("\n".join(lines[:40]) + ("\n…" if len(lines) > 40 else ""))

        run_in_thread(work, done)

    def _sha256sums(self, *_args: object) -> None:
        compat.select_folder(self._window, self._write_sha256sums)

    def _write_sha256sums(self, root: Path) -> None:
        compat.save_file(
            self._window,
            "SHA256SUMS",
            lambda dest: self._bg_sha256sums(root, dest),
        )

    def _bg_sha256sums(self, root: Path, dest: Path) -> None:
        def work() -> str:
            return str(hashutil.sha256sums_file(root, dest))

        def done(result: Any, error: BaseException | None) -> None:
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            show_toast(self._toast, str(result))

        run_in_thread(work, done)

    def _manifest(self) -> None:
        compat.select_folder(self._window, self._write_manifest)

    def _write_manifest(self, root: Path) -> None:
        def work() -> str:
            return hashutil.checksums_manifest(root)

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

    def _verify(self) -> None:
        compat.open_files(self._window, self._verify_manifest)

    def _verify_manifest(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            text = paths[0].read_text(encoding="utf-8")
        except OSError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        compat.select_folder(self._window, lambda root: self._run_verify(root, text))

    def _run_verify(self, root: Path, text: str) -> None:
        def work() -> list[tuple[str, str]]:
            return hashutil.verify_manifest(root, text)

        def done(result: Any, error: BaseException | None) -> None:
            common.clear_list(self._verify_list)
            if error is not None:
                show_toast(self._toast, str(error), 6)
                return
            ok = sum(1 for _name, state in result if state == "OK")
            self._status.set_text(f"{ok} / {len(result)}")
            for name, state in result:
                row = Gtk.ListBoxRow()
                lab = Gtk.Label(label=f"{state}  {name}", xalign=0, wrap=True)
                lab.set_margin_start(10)
                lab.set_margin_end(10)
                lab.set_margin_top(6)
                lab.set_margin_bottom(6)
                row.set_child(lab)
                self._verify_list.append(row)

        run_in_thread(work, done)
