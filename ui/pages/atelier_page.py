# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Gtk

from core import codec
from core import generate
from core import i18n
from core import textutil
from ui import compat
from ui.helpers import show_toast
from ui.pages import common


def _buffer_text(view: Gtk.TextView) -> str:
    buf = view.get_buffer()
    start, end = buf.get_start_iter(), buf.get_end_iter()
    return buf.get_text(start, end, True)


def _set_buffer(view: Gtk.TextView, text: str) -> None:
    view.get_buffer().set_text(text)


class AtelierPage:
    def __init__(self, window: Gtk.Window, toast: Gtk.Widget) -> None:
        self._window = window
        self._toast = toast
        self.widget = self._build()

    def _build(self) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        switcher, stack = compat.view_switcher_stack()
        outer.append(switcher)
        stack.add_titled(self._tab_text(), "text", i18n.t("atelier_text"))
        stack.add_titled(self._tab_encode(), "encode", i18n.t("atelier_encode"))
        stack.add_titled(self._tab_generate(), "gen", i18n.t("atelier_generate"))
        stack.add_titled(self._tab_password(), "password", i18n.t("atelier_password"))
        stack.add_titled(self._tab_preview(), "preview", i18n.t("atelier_preview"))
        stack.add_titled(self._tab_data(), "data", i18n.t("atelier_data"))
        stack.set_vexpand(True)
        outer.append(stack)
        return outer

    def _tab_text(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        self._pattern = Gtk.Entry(placeholder_text=i18n.t("text_pattern"))
        self._text_repl = Gtk.Entry(placeholder_text=i18n.t("text_replace_with"))
        self._ignore = Gtk.CheckButton(label=i18n.t("text_ignore_case"))
        box.append(self._pattern)
        box.append(self._text_repl)
        box.append(self._ignore)
        self._text_in = Gtk.TextView()
        self._text_in.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._text_in))
        box.append(
            common.prefs_group(
                i18n.t("group_actions"),
                [
                    common.button_row(i18n.t("text_run"), lambda *_: self._on_text("run"), suggested=True),
                    common.button_row(i18n.t("text_regex"), lambda *_: self._on_text("regex")),
                    common.button_row(i18n.t("text_normalize"), lambda *_: self._on_text("normalize")),
                ],
            )
        )
        more = common.prefs_group(
            i18n.t("group_more"),
            [
                common.button_row(i18n.t("text_upper"), lambda *_: self._on_text("upper")),
                common.button_row(i18n.t("text_lower"), lambda *_: self._on_text("lower")),
                common.button_row(i18n.t("text_trim"), lambda *_: self._on_text("trim")),
                common.button_row(i18n.t("text_slug"), lambda *_: self._on_text("slug")),
                common.button_row(i18n.t("text_accents"), lambda *_: self._on_text("accents")),
                common.button_row(i18n.t("text_html_e"), lambda *_: self._on_text("html_escape")),
                common.button_row(i18n.t("text_html_u"), lambda *_: self._on_text("html_unescape")),
                common.button_row(i18n.t("text_lf"), lambda *_: self._on_text("lf")),
                common.button_row(i18n.t("text_crlf"), lambda *_: self._on_text("crlf")),
                common.button_row(i18n.t("text_sort"), lambda *_: self._on_text("sort")),
                common.button_row(i18n.t("text_unique"), lambda *_: self._on_text("unique")),
                common.button_row(i18n.t("text_reverse"), lambda *_: self._on_text("reverse")),
                common.button_row(i18n.t("text_wrap"), lambda *_: self._on_text("wrap")),
                common.button_row(i18n.t("text_counts"), lambda *_: self._on_text("counts")),
                common.button_row(i18n.t("text_sha"), lambda *_: self._on_text("sha")),
            ],
        )
        extra = Gtk.Expander(label=i18n.t("group_more"))
        extra.set_child(more)
        box.append(extra)
        self._text_out = Gtk.TextView()
        self._text_out.set_editable(False)
        self._text_out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._text_out))
        self._text_b = Gtk.TextView()
        self._text_b.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(Gtk.Label(label="B", xalign=0))
        box.append(common.scrolled(self._text_b))
        diff = Gtk.Button(label=i18n.t("text_diff"))
        diff.add_css_class("suggested-action")
        diff.connect("clicked", lambda *_: self._on_text("diff"))
        box.append(diff)
        return common.scrolled(box)

    def _on_text(self, key: str) -> None:
        src = _buffer_text(self._text_in)
        try:
            if key == "run":
                rows, count = textutil.regex_matches(
                    self._pattern.get_text(), src, ignore_case=self._ignore.get_active()
                )
                _set_buffer(self._text_out, f"{count}\n" + "\n".join(rows))
            elif key == "regex":
                out = textutil.regex_replace_preview(
                    self._pattern.get_text(),
                    self._text_repl.get_text(),
                    src,
                    ignore_case=self._ignore.get_active(),
                )
                _set_buffer(self._text_out, out)
            elif key == "normalize":
                _set_buffer(self._text_out, textutil.normalize_clipboard(src))
            elif key == "diff":
                _set_buffer(self._text_out, textutil.unified_diff(src, _buffer_text(self._text_b)))
            elif key == "counts":
                data = textutil.counts(src)
                _set_buffer(self._text_out, "\n".join(f"{k}: {v}" for k, v in data.items()))
            elif key == "sha":
                _set_buffer(self._text_out, textutil.sha256_text(src))
            else:
                _set_buffer(self._text_in, textutil.transform(src, key))
        except textutil.TextError as exc:
            show_toast(self._toast, str(exc), 6)

    def _tab_encode(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        hint = Gtk.Label(label=i18n.t("encode_hint"), wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)
        self._enc_in = Gtk.TextView()
        self._enc_in.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._enc_in))
        actions: list[tuple[str, Callable[[str], str]]] = [
            (i18n.t("encode_json"), codec.pretty_json),
            (i18n.t("encode_json_min"), codec.minify_json),
            (i18n.t("encode_jsonl"), codec.pretty_jsonl),
            (i18n.t("encode_jsonl_min"), codec.minify_jsonl),
            (i18n.t("encode_jsonl_check"), lambda t: (codec.validate_jsonl(t) or "OK")),
            (i18n.t("encode_yaml"), codec.pretty_yaml),
            (i18n.t("encode_xml"), codec.pretty_xml),
            (i18n.t("encode_ini"), codec.pretty_ini),
            (i18n.t("encode_jwt"), codec.decode_jwt),
            (i18n.t("encode_b64e"), codec.b64_encode),
            (i18n.t("encode_b64d"), codec.b64_decode),
            (i18n.t("encode_urle"), codec.url_encode),
            (i18n.t("encode_urld"), codec.url_decode),
            (i18n.t("encode_rot13"), codec.rot13),
            (i18n.t("encode_hash"), lambda t: codec.hash_text(t, "sha256")),
            (i18n.t("encode_hex"), codec.hexdump_text),
        ]
        primary = common.prefs_group(
            i18n.t("group_actions"),
            [
                common.button_row(actions[0][0], lambda *_a, func=actions[0][1]: self._run_codec(func), suggested=True),
                common.button_row(i18n.t("encode_env"), self._env_inspect),
            ],
        )
        box.append(primary)
        more_rows = [
            common.button_row(label, lambda *_a, func=fn: self._run_codec(func))
            for label, fn in actions[1:]
        ]
        extra = Gtk.Expander(label=i18n.t("group_more"))
        extra.set_child(common.prefs_group(i18n.t("group_more"), more_rows))
        box.append(extra)
        self._enc_out = Gtk.TextView()
        self._enc_out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._enc_out))
        copy = Gtk.Button(label=i18n.t("copy"))
        copy.connect("clicked", lambda *_: common.copy_text(_buffer_text(self._enc_out), self._toast))
        box.append(copy)
        return common.scrolled(box)

    def _run_codec(self, fn: Callable[[str], str]) -> None:
        try:
            _set_buffer(self._enc_out, fn(_buffer_text(self._enc_in)))
        except codec.CodecError as exc:
            show_toast(self._toast, str(exc), 6)

    def _env_inspect(self, *_args: object) -> None:
        compat.open_files(self._window, self._env_from_file)

    def _env_from_file(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            _set_buffer(self._enc_out, generate.env_inspect(paths[0]))
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)

    def _tab_generate(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        self._uuid = Gtk.Entry()
        uuid_row = Gtk.Box(spacing=8)
        uuid_btn = Gtk.Button(label=i18n.t("gen_uuid"))
        uuid_btn.add_css_class("suggested-action")
        uuid_btn.connect("clicked", self._make_uuid)
        uuid5 = Gtk.Button(label=i18n.t("gen_uuid5"))
        uuid5.connect("clicked", self._make_uuid5)
        uuid_row.append(self._uuid)
        self._uuid.set_hexpand(True)
        uuid_row.append(uuid_btn)
        uuid_row.append(uuid5)
        box.append(uuid_row)
        self._uuid5_name = Gtk.Entry(placeholder_text=i18n.t("gen_uuid5_name"))
        box.append(self._uuid5_name)
        extra = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        self._unix = Gtk.Entry(placeholder_text="Unix")
        self._iso = Gtk.Entry(placeholder_text="ISO-8601")
        ts_row = Gtk.Box(spacing=8)
        now = Gtk.Button(label=i18n.t("gen_now"))
        now.connect("clicked", self._now)
        to_iso = Gtk.Button(label=i18n.t("gen_unix"))
        to_iso.connect("clicked", self._unix_to_iso)
        to_unix = Gtk.Button(label=i18n.t("gen_iso"))
        to_unix.connect("clicked", self._iso_to_unix)
        plus = Gtk.Button(label=i18n.t("gen_plus_days"))
        plus.connect("clicked", self._plus_days)
        week = Gtk.Button(label=i18n.t("gen_week"))
        week.connect("clicked", self._week)
        ts_row.append(now)
        ts_row.append(to_iso)
        ts_row.append(to_unix)
        ts_row.append(plus)
        ts_row.append(week)
        extra.append(self._unix)
        extra.append(self._iso)
        self._days = Gtk.SpinButton.new_with_range(-3650, 3650, 1)
        self._days.set_value(1)
        extra.append(self._days)
        extra.append(ts_row)

        kind_row = Gtk.Box(spacing=8)
        self._kind = compat.string_choice(
            [
                i18n.t("gen_kind_length"),
                i18n.t("gen_kind_mass"),
                i18n.t("gen_kind_temp"),
                i18n.t("gen_kind_size"),
                i18n.t("gen_kind_angle"),
                i18n.t("gen_kind_duration"),
            ]
        )
        self._unit_from = Gtk.Entry()
        self._unit_from.set_text("km")
        self._unit_to = Gtk.Entry()
        self._unit_to.set_text("mi")
        self._unit_val = Gtk.Entry()
        self._unit_val.set_text("1")
        self._unit_out = Gtk.Entry()
        self._unit_out.set_editable(False)
        conv = Gtk.Button(label=i18n.t("gen_units"))
        conv.connect("clicked", self._convert)
        kind_row.append(self._kind)
        kind_row.append(self._unit_from)
        kind_row.append(self._unit_to)
        extra.append(kind_row)
        extra.append(self._unit_val)
        extra.append(self._unit_out)
        extra.append(conv)

        base_row = Gtk.Box(spacing=8)
        self._base_val = Gtk.Entry(placeholder_text=i18n.t("gen_base"))
        self._base_from = Gtk.SpinButton.new_with_range(2, 16, 1)
        self._base_from.set_value(10)
        self._base_to = Gtk.SpinButton.new_with_range(2, 16, 1)
        self._base_to.set_value(16)
        base_btn = Gtk.Button(label=i18n.t("gen_base_go"))
        base_btn.connect("clicked", self._base)
        base_row.append(self._base_val)
        base_row.append(self._base_from)
        base_row.append(self._base_to)
        base_row.append(base_btn)
        extra.append(base_row)

        lorem_btn = Gtk.Button(label=i18n.t("gen_lorem"))
        lorem_btn.connect("clicked", self._lorem)
        extra.append(lorem_btn)

        self._qr = Gtk.Entry(placeholder_text=i18n.t("gen_qr_text"))
        qr_btn = Gtk.Button(label=i18n.t("gen_qr"))
        qr_btn.connect("clicked", self._qr_save)
        extra.append(self._qr)
        extra.append(qr_btn)

        self._dummy_mb = Gtk.SpinButton.new_with_range(1, 1024, 1)
        self._dummy_mb.set_value(1)
        dummy_btn = Gtk.Button(label=i18n.t("gen_dummy"))
        dummy_btn.connect("clicked", self._dummy_file)
        dummy_row = Gtk.Box(spacing=8)
        dummy_row.append(self._dummy_mb)
        dummy_row.append(dummy_btn)
        extra.append(dummy_row)

        self._desktop_name = Gtk.Entry(placeholder_text=i18n.t("gen_desktop_name"))
        self._desktop_exec = Gtk.Entry(placeholder_text=i18n.t("gen_desktop_exec"))
        desktop_btn = Gtk.Button(label=i18n.t("gen_desktop"))
        desktop_btn.connect("clicked", self._desktop_entry)
        extra.append(self._desktop_name)
        extra.append(self._desktop_exec)
        extra.append(desktop_btn)

        qr_read_btn = Gtk.Button(label=i18n.t("gen_qr_read"))
        qr_read_btn.connect("clicked", lambda *_: compat.open_files(self._window, self._qr_read))
        extra.append(qr_read_btn)

        self._cron_expr = Gtk.Entry(placeholder_text=i18n.t("gen_cron_expr"))
        cron_btn = Gtk.Button(label=i18n.t("gen_cron"))
        cron_btn.connect("clicked", self._cron_next)
        cron_row = Gtk.Box(spacing=8)
        cron_row.append(self._cron_expr)
        cron_row.append(cron_btn)
        extra.append(cron_row)

        gitignore_btn = Gtk.Button(label=i18n.t("gen_gitignore"))
        gitignore_btn.connect("clicked", lambda *_: compat.select_folder(self._window, self._gitignore))
        extra.append(gitignore_btn)

        self._gen_out = Gtk.TextView()
        self._gen_out.set_editable(False)
        self._gen_out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        extra.append(common.scrolled(self._gen_out))

        more = Gtk.Expander(label=i18n.t("group_more"))
        more.set_child(extra)
        box.append(more)
        return common.scrolled(box)

    def _tab_password(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        hint = Gtk.Label(label=i18n.t("atelier_password_hint"), wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        box.append(hint)

        opts = Gtk.Box(spacing=8)
        self._pwd_len = Gtk.SpinButton.new_with_range(4, 128, 1)
        self._pwd_len.set_value(16)
        self._pwd_len.set_tooltip_text(i18n.t("gen_length"))
        self._pwd_batch = Gtk.SpinButton.new_with_range(1, 50, 1)
        self._pwd_batch.set_value(1)
        self._pwd_batch.set_tooltip_text(i18n.t("gen_batch"))
        self._pwd_words = Gtk.SpinButton.new_with_range(3, 12, 1)
        self._pwd_words.set_value(4)
        self._pwd_words.set_tooltip_text(i18n.t("gen_words"))
        opts.append(Gtk.Label(label=i18n.t("gen_length")))
        opts.append(self._pwd_len)
        opts.append(Gtk.Label(label=i18n.t("gen_batch")))
        opts.append(self._pwd_batch)
        opts.append(Gtk.Label(label=i18n.t("gen_words")))
        opts.append(self._pwd_words)
        box.append(opts)

        classes = Gtk.Box(spacing=8)
        self._pwd_lower = Gtk.CheckButton(label=i18n.t("gen_lower"))
        self._pwd_lower.set_active(True)
        self._pwd_upper = Gtk.CheckButton(label=i18n.t("gen_upper"))
        self._pwd_upper.set_active(True)
        self._pwd_digits = Gtk.CheckButton(label=i18n.t("gen_digits"))
        self._pwd_digits.set_active(True)
        self._pwd_sym = Gtk.CheckButton(label=i18n.t("gen_symbols"))
        classes.append(self._pwd_lower)
        classes.append(self._pwd_upper)
        classes.append(self._pwd_digits)
        classes.append(self._pwd_sym)
        box.append(classes)

        extra_opts = Gtk.Box(spacing=8)
        self._pwd_ambiguous = Gtk.CheckButton(label=i18n.t("gen_exclude_ambiguous"))
        self._pwd_ambiguous.set_active(True)
        self._pwd_ensure = Gtk.CheckButton(label=i18n.t("gen_ensure"))
        self._pwd_ensure.set_active(True)
        extra_opts.append(self._pwd_ambiguous)
        extra_opts.append(self._pwd_ensure)
        box.append(extra_opts)

        actions = Gtk.Box(spacing=8)
        pwd_btn = Gtk.Button(label=i18n.t("gen_password"))
        pwd_btn.add_css_class("suggested-action")
        pwd_btn.connect("clicked", self._make_password)
        pin_btn = Gtk.Button(label=i18n.t("gen_pin"))
        pin_btn.connect("clicked", self._make_pin)
        phrase_btn = Gtk.Button(label=i18n.t("gen_passphrase"))
        phrase_btn.connect("clicked", self._make_phrase)
        copy = Gtk.Button(label=i18n.t("copy"))
        copy.connect("clicked", self._copy_password)
        actions.append(pwd_btn)
        actions.append(pin_btn)
        actions.append(phrase_btn)
        actions.append(copy)
        box.append(actions)

        self._entropy = Gtk.Label(xalign=0)
        self._entropy.add_css_class("dim-label")
        box.append(self._entropy)

        self._pwd = Gtk.TextView()
        self._pwd.set_wrap_mode(Gtk.WrapMode.CHAR)
        self._pwd.set_monospace(True)
        box.append(common.scrolled(self._pwd))
        return common.scrolled(box)

    def _make_uuid(self, *_args: object) -> None:
        value = generate.new_uuid()
        self._uuid.set_text(value)
        common.copy_text(value, self._toast)

    def _make_uuid5(self, *_args: object) -> None:
        try:
            value = generate.new_uuid5(self._uuid5_name.get_text())
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)
            return
        self._uuid.set_text(value)

    def _now(self, *_args: object) -> None:
        unix, iso = generate.now_unix_iso()
        self._unix.set_text(unix)
        self._iso.set_text(iso)

    def _unix_to_iso(self, *_args: object) -> None:
        try:
            self._iso.set_text(generate.unix_to_iso(self._unix.get_text()))
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)

    def _iso_to_unix(self, *_args: object) -> None:
        try:
            self._unix.set_text(generate.iso_to_unix(self._iso.get_text()))
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)

    def _plus_days(self, *_args: object) -> None:
        self._iso.set_text(generate.date_plus_days(int(self._days.get_value())))

    def _week(self, *_args: object) -> None:
        try:
            week = generate.week_number(self._iso.get_text())
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)
            return
        self._unit_out.set_text(str(week))

    def _convert(self, *_args: object) -> None:
        kinds = ("length", "mass", "temp", "size", "angle", "duration")
        kind = kinds[compat.choice_index(self._kind)]
        try:
            value = float(self._unit_val.get_text().replace(",", "."))
            out = generate.convert_unit(value, self._unit_from.get_text().strip(), self._unit_to.get_text().strip(), kind)
        except (ValueError, generate.GenerateError) as exc:
            show_toast(self._toast, str(exc), 5)
            return
        self._unit_out.set_text(f"{out:.6g}")

    def _base(self, *_args: object) -> None:
        try:
            out = generate.convert_base(
                self._base_val.get_text(),
                int(self._base_from.get_value()),
                int(self._base_to.get_value()),
            )
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)
            return
        self._unit_out.set_text(out)

    def _pwd_options(self) -> dict[str, bool]:
        return {
            "lower": self._pwd_lower.get_active(),
            "upper": self._pwd_upper.get_active(),
            "digits": self._pwd_digits.get_active(),
            "symbols": self._pwd_sym.get_active(),
            "exclude_ambiguous": self._pwd_ambiguous.get_active(),
            "ensure_classes": self._pwd_ensure.get_active(),
        }

    def _show_passwords(self, rows: list[tuple[str, float]]) -> None:
        _set_buffer(self._pwd, "\n".join(pwd for pwd, _bits in rows))
        if not rows:
            self._entropy.set_text("")
            return
        bits = rows[0][1]
        if len(rows) == 1:
            self._entropy.set_text(f"{bits:.1f} bits")
            return
        self._entropy.set_text(f"{len(rows)} × {bits:.1f} bits")

    def _make_password(self, *_args: object) -> None:
        try:
            rows = generate.password_batch(
                int(self._pwd_batch.get_value()),
                length=int(self._pwd_len.get_value()),
                **self._pwd_options(),
            )
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 5)
            return
        self._show_passwords(rows)

    def _make_pin(self, *_args: object) -> None:
        count = int(self._pwd_batch.get_value())
        pins = [generate.pin(int(self._pwd_len.get_value())) for _ in range(count)]
        _set_buffer(self._pwd, "\n".join(pins))
        self._entropy.set_text("")

    def _make_phrase(self, *_args: object) -> None:
        count = int(self._pwd_batch.get_value())
        words = int(self._pwd_words.get_value())
        phrases = [generate.passphrase(words) for _ in range(count)]
        _set_buffer(self._pwd, "\n".join(phrases))
        self._entropy.set_text("")

    def _copy_password(self, *_args: object) -> None:
        common.copy_text(_buffer_text(self._pwd), self._toast)

    def _lorem(self, *_args: object) -> None:
        self._set_gen_out(generate.lorem(paragraphs=2, sentences=3))

    def _qr_save(self, *_args: object) -> None:
        text = self._qr.get_text()
        compat.save_file(self._window, "qr.png", lambda dest: self._write_qr(text, dest))

    def _write_qr(self, text: str, dest: Any) -> None:
        try:
            generate.qr_png(text, dest)
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, str(dest))

    def _set_gen_out(self, text: str) -> None:
        self._gen_out.get_buffer().set_text(text)

    def _dummy_file(self, *_args: object) -> None:
        mb = float(self._dummy_mb.get_value())
        compat.save_file(
            self._window,
            "dummy.bin",
            lambda dest: self._write_dummy(mb, dest),
        )

    def _write_dummy(self, mb: float, dest: Path) -> None:
        try:
            generate.dummy_file(dest, mb)
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, str(dest))

    def _desktop_entry(self, *_args: object) -> None:
        try:
            path = generate.desktop_entry(
                name=self._desktop_name.get_text(),
                exec_cmd=self._desktop_exec.get_text(),
            )
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        self._set_gen_out(str(path))
        show_toast(self._toast, str(path))

    def _qr_read(self, paths: list[Path]) -> None:
        if not paths:
            return
        try:
            self._set_gen_out(generate.qr_read_image(paths[0]))
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)

    def _cron_next(self, *_args: object) -> None:
        try:
            hits = generate.cron_next(self._cron_expr.get_text())
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        self._set_gen_out("\n".join(hits))

    def _gitignore(self, folder: Path) -> None:
        try:
            self._set_gen_out(generate.gitignore_suggest(folder))
        except generate.GenerateError as exc:
            show_toast(self._toast, str(exc), 6)

    def _tab_preview(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        self._md_in = Gtk.TextView()
        self._md_in.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._md_in))
        box.append(
            common.prefs_group(
                i18n.t("group_actions"),
                [common.button_row(i18n.t("md_preview"), self._md_preview, suggested=True)],
            )
        )
        self._md_out = Gtk.Label(wrap=True, xalign=0, use_markup=True)
        box.append(self._md_out)
        return common.scrolled(box)

    def _md_preview(self, *_args: object) -> None:
        markup = generate.markdown_to_pango(_buffer_text(self._md_in))
        self._md_out.set_markup(markup)

    def _tab_data(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        common.padded(box)
        self._data_in = Gtk.TextView()
        self._data_in.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._data_in))
        data_actions = (
            (i18n.t("data_csv_json"), codec.csv_to_json),
            (i18n.t("data_json_csv"), codec.json_to_csv),
            (i18n.t("data_json_yaml"), codec.json_to_yaml),
            (i18n.t("data_yaml_json"), codec.yaml_to_json),
            (i18n.t("data_flatten"), codec.flatten_json),
        )
        box.append(
            common.prefs_group(
                i18n.t("group_actions"),
                [
                    common.button_row(
                        data_actions[0][0],
                        lambda *_a, func=data_actions[0][1]: self._run_data(func),
                        suggested=True,
                    )
                ],
            )
        )
        extra = Gtk.Expander(label=i18n.t("group_more"))
        extra.set_child(
            common.prefs_group(
                i18n.t("group_more"),
                [common.button_row(label, lambda *_a, func=fn: self._run_data(func)) for label, fn in data_actions[1:]],
            )
        )
        box.append(extra)
        self._csv_files: list[Path] = []
        pick_csv = Gtk.Button(label=i18n.t("add_files"))
        pick_csv.connect("clicked", lambda *_: compat.open_files(self._window, self._set_csv, multiple=True))
        merge_btn = Gtk.Button(label=i18n.t("data_csv_merge"))
        merge_btn.connect("clicked", self._csv_merge)
        box.append(Gtk.Label(label=i18n.t("data_csv_rows"), xalign=0))
        self._csv_rows = Gtk.SpinButton.new_with_range(1, 100000, 1)
        self._csv_rows.set_value(100)
        split_btn = Gtk.Button(label=i18n.t("data_csv_split"))
        split_btn.connect("clicked", self._csv_split)
        box.append(
            common.prefs_group(
                i18n.t("group_export"),
                [
                    common.action_row(i18n.t("add_files"), pick_csv),
                    common.action_row(i18n.t("data_csv_merge"), merge_btn),
                    common.action_row(i18n.t("data_csv_split"), split_btn),
                ],
            )
        )
        box.append(self._csv_rows)
        self._csv_label = Gtk.Label(label="—", wrap=True, xalign=0)
        box.append(self._csv_label)
        self._data_out = Gtk.TextView()
        self._data_out.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        box.append(common.scrolled(self._data_out))
        export = Gtk.Button(label=i18n.t("data_export"))
        export.connect("clicked", self._export_data)
        box.append(export)
        return common.scrolled(box)

    def _set_csv(self, paths: list[Path]) -> None:
        self._csv_files = paths
        self._csv_label.set_text("\n".join(str(p) for p in paths) or "—")

    def _csv_merge(self, *_args: object) -> None:
        files = list(self._csv_files)
        if not files:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return

        def on_resp(response: str) -> None:
            if response != "now":
                return
            compat.save_file(self._window, "merged.csv", lambda dest: self._write_merge(files, dest))

        compat.present_alert(
            self._window,
            i18n.t("data_write_confirm"),
            i18n.t("data_write_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("confirm"))],
            suggested="now",
            on_response=on_resp,
        )

    def _write_merge(self, files: list[Path], dest: Path) -> None:
        try:
            codec.merge_csv_files(files, dest)
        except codec.CodecError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, str(dest))

    def _csv_split(self, *_args: object) -> None:
        files = list(self._csv_files)
        if not files:
            show_toast(self._toast, i18n.t("add_files"), 4)
            return
        src = files[0]
        n = int(self._csv_rows.get_value())

        def on_resp(response: str) -> None:
            if response != "now":
                return
            compat.select_folder(self._window, lambda folder: self._write_split(src, folder, n))

        compat.present_alert(
            self._window,
            i18n.t("data_write_confirm"),
            i18n.t("data_write_body"),
            [("cancel", i18n.t("cancel")), ("now", i18n.t("confirm"))],
            suggested="now",
            on_response=on_resp,
        )

    def _write_split(self, src: Path, folder: Path, n: int) -> None:
        try:
            parts = codec.split_csv_file(src, folder, n)
        except codec.CodecError as exc:
            show_toast(self._toast, str(exc), 6)
            return
        show_toast(self._toast, f"{len(parts)} OK")

    def _run_data(self, fn: Callable[[str], str]) -> None:
        try:
            _set_buffer(self._data_out, fn(_buffer_text(self._data_in)))
        except codec.CodecError as exc:
            show_toast(self._toast, str(exc), 6)

    def _export_data(self, *_args: object) -> None:
        text = _buffer_text(self._data_out)
        compat.save_file(self._window, "atelier.txt", lambda dest: dest.write_text(text, encoding="utf-8"))
