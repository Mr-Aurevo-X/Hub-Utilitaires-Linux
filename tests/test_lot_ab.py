# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event

import pytest

from core import batchutil, codec, fileutil, find as find_core, hashutil, pdfutil, rename, resize, snippets, textutil
from core import secretscan


def test_rename_mtime_and_copies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    src = tmp_path / "photo.jpg"
    src.write_text("orig", encoding="utf-8")
    stamp = datetime(2024, 6, 15, 12, 0, 0).timestamp()
    __import__("os").utime(src, (stamp, stamp))
    rows = rename.preview([src], "", "{stem}_{mtime}{ext}")
    assert rows[0][1] == "photo_2024-06-15.jpg"
    custom = rename.preview([src], "", "{stem}_{mtime:%Y%m%d}{ext}")
    assert custom[0][1] == "photo_20240615.jpg"
    dest_dir = tmp_path / "out"
    before = rename.last_undo_count()
    done = rename.apply_copies(rows, dest_dir)
    assert src.read_text(encoding="utf-8") == "orig"
    assert src.exists()
    assert done[0] == dest_dir / "photo_2024-06-15.jpg"
    assert done[0].read_text(encoding="utf-8") == "orig"
    assert rename.last_undo_count() == before


def test_rename_overwrite_preview(tmp_path: Path) -> None:
    a = tmp_path / "a.txt"
    b = tmp_path / "taken.txt"
    a.write_text("a", encoding="utf-8")
    b.write_text("keep", encoding="utf-8")
    skipped = rename.preview([a], "a.txt", "taken.txt", collision="skip")
    assert skipped == []
    rows = rename.preview([a], "a.txt", "taken.txt", collision="overwrite")
    assert rows[0][1] == "taken.txt"
    done = rename.apply(rows, overwrite=True)
    assert done[0].name == "taken.txt"
    assert not a.exists()
    assert (tmp_path / "taken.txt").read_text(encoding="utf-8") == "a"


def test_verify_manifest_ok_missing_diff(tmp_path: Path) -> None:
    ok = tmp_path / "ok.bin"
    missing = tmp_path / "gone.bin"
    changed = tmp_path / "changed.bin"
    ok.write_bytes(b"abc")
    changed.write_bytes(b"abc")
    digest_ok = hashutil.file_hash(ok, "sha256")
    digest_changed = hashutil.file_hash(changed, "sha256")
    changed.write_bytes(b"xyz")
    missing.write_bytes(b"tmp")
    digest_missing = hashutil.file_hash(missing, "sha256")
    missing.unlink()
    text = (
        f"{digest_ok}  ok.bin\n"
        f"{digest_missing}  gone.bin\n"
        f"{digest_changed}  changed.bin\n"
    )
    rows = hashutil.verify_manifest(tmp_path, text)
    status = {name: state for name, state in rows}
    assert status["ok.bin"] == "OK"
    assert status["gone.bin"] == "MANQUANT"
    assert status["changed.bin"] == "DIFF"


def test_jsonl_pretty_and_line_error() -> None:
    pretty = codec.pretty_jsonl('{"a":1}\n{"b":2}\n')
    assert '"a": 1' in pretty
    compact = codec.minify_jsonl(pretty)
    assert compact.splitlines()[0] == '{"a":1}'
    with pytest.raises(codec.CodecError, match=r"ligne 2"):
        codec.validate_jsonl('{"ok":true}\n{bad}\n')


def test_csv_merge_same_header_and_split(tmp_path: Path) -> None:
    a = tmp_path / "a.csv"
    b = tmp_path / "b.csv"
    a.write_text("n,v\n1,x\n", encoding="utf-8")
    b.write_text("n,v\n2,y\n", encoding="utf-8")
    dest = tmp_path / "merged.csv"
    codec.merge_csv_files([a, b], dest)
    assert dest.read_text(encoding="utf-8") == "n,v\n1,x\n2,y\n"
    bad = tmp_path / "bad.csv"
    bad.write_text("other,v\n3,z\n", encoding="utf-8")
    with pytest.raises(codec.CodecError):
        codec.merge_csv_files([a, bad], tmp_path / "nope.csv")
    parts = codec.split_csv_file(dest, tmp_path / "parts", 1)
    assert len(parts) == 2
    assert parts[0].name == "merged_part001.csv"
    assert parts[0].read_text(encoding="utf-8") == "n,v\n1,x\n"
    assert parts[1].read_text(encoding="utf-8") == "n,v\n2,y\n"


def test_secretscan_akia_and_private_key(tmp_path: Path) -> None:
    code = tmp_path / "leak.py"
    code.write_text(
        "key = 'AKIAIOSFODNN7EXAMPLE'\n"
        "token=secret\n"
        "-----BEGIN PRIVATE KEY-----\nMIIB\n",
        encoding="utf-8",
    )
    (tmp_path / "ok.txt").write_text("hello\n", encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"\x00AKIAIOSFODNN7EXAMPLE")
    hits = secretscan.scan_tree(tmp_path)
    rules = {hit.rule for hit in hits}
    assert "AKIA" in rules
    assert "TOKEN" in rules
    assert "PRIVATE_KEY" in rules
    assert all(hit.path != tmp_path / "bin.dat" for hit in hits)


def test_lined_diff_plus_minus() -> None:
    rows = textutil.lined_diff("keep\nold\n", "keep\nnew\n")
    marks = {line: mark for mark, line in rows}
    assert marks["keep"] == " "
    assert marks["old"] == "-"
    assert marks["new"] == "+"


def test_list_images_and_max_side(tmp_path: Path) -> None:
    from PIL import Image

    src = tmp_path / "wide.png"
    Image.new("RGB", (80, 20), (1, 2, 3)).save(src)
    (tmp_path / "skip.txt").write_text("nope", encoding="utf-8")
    found = resize.list_images(tmp_path)
    assert found == [src]
    dest = tmp_path / "small.png"
    resize.convert_image(src, dest, max_side=40)
    info = resize.image_info(dest)
    assert info["width"] == 40
    assert info["height"] == 10
    out_dir = tmp_path / "batch"
    done = resize.batch_convert([src], out_dir, suffix=".jpg")
    assert done[0].suffix == ".jpg"
    assert src.exists()
    assert done[0].parent == out_dir


def test_snippets_put_list_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    snippets.put("sig", "Cordialement")
    rows = snippets.list_all()
    assert rows[0]["name"] == "sig"
    assert snippets.get("sig") == "Cordialement"
    snippets.delete("sig")
    assert snippets.list_all() == []


def test_broken_doc_links_reports_missing_skips_http(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("# ok\n", encoding="utf-8")
    src = tmp_path / "readme.md"
    src.write_text(
        "[ok](ok.md)\n[gone](missing.md)\n[web](https://example.com/x)\n[mail](mailto:a@b.c)\n",
        encoding="utf-8",
    )
    html = tmp_path / "page.html"
    html.write_text('<a href="nope.html">x</a><img src="ok.md">', encoding="utf-8")
    hits = batchutil.broken_doc_links(tmp_path)
    assert src in hits.paths
    assert html in hits.paths
    assert (tmp_path / "ok.md") not in hits.paths
    text = batchutil.broken_doc_links_text(tmp_path)
    assert "missing.md" in text
    assert "nope.html" in text
    assert "example.com" not in text


def test_eol_audit_classifies_lf_and_mixed(tmp_path: Path) -> None:
    lf = tmp_path / "unix.txt"
    mixed = tmp_path / "mixed.txt"
    lf.write_bytes(b"a\nb\n")
    mixed.write_bytes(b"a\r\nb\nc\n")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01")
    rows = {row["path"]: row for row in batchutil.eol_audit(tmp_path)}
    assert rows[str(lf)]["endings"] == "lf"
    assert rows[str(mixed)]["endings"] == "mixed"
    assert str(tmp_path / "bin.dat") not in rows
    assert rows[str(lf)]["encoding"] == "utf-8"


def test_near_duplicate_images_groups_same_wxh_bytes(tmp_path: Path) -> None:
    from PIL import Image

    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    other = tmp_path / "other.png"
    Image.new("RGB", (16, 8), (9, 8, 7)).save(a)
    Image.new("RGB", (16, 8), (9, 8, 7)).save(b)
    Image.new("RGB", (8, 8), (1, 2, 3)).save(other)
    hits = batchutil.near_duplicate_images(tmp_path)
    groups = [sorted(group, key=lambda item: item.name) for group in hits.groups]
    assert [a, b] in groups
    assert all(other not in group for group in hits.groups)


def test_diff_archive_members_only_a_only_b(tmp_path: Path) -> None:
    shared = tmp_path / "shared.txt"
    extra_a = tmp_path / "only_a.txt"
    extra_b = tmp_path / "only_b.txt"
    shared.write_text("s", encoding="utf-8")
    extra_a.write_text("a", encoding="utf-8")
    extra_b.write_text("b", encoding="utf-8")
    zip_a = tmp_path / "a.zip"
    zip_b = tmp_path / "b.zip"
    fileutil.create_zip([shared, extra_a], zip_a)
    fileutil.create_zip([shared, extra_b], zip_b)
    diff = fileutil.diff_archive_members(zip_a, zip_b)
    assert diff["only_a"] == ["only_a.txt"]
    assert diff["only_b"] == ["only_b.txt"]
    assert diff["both"] == ["shared.txt"]


def test_pdf_inventory_ok_and_error_row(tmp_path: Path) -> None:
    from pypdf import PdfWriter

    ok = tmp_path / "ok.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": "Inv"})
    with ok.open("wb") as handle:
        writer.write(handle)
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf", encoding="utf-8")
    csv_text = pdfutil.inventory([ok, bad])
    lines = [line for line in csv_text.splitlines() if line]
    assert lines[0] == "path,pages,bytes,encrypted,title"
    assert any(line.startswith(str(ok)) and ",1," in line and "Inv" in line for line in lines[1:])
    assert any(line.startswith(str(bad)) and ",ERROR," in line for line in lines[1:])


def test_empty_files_skips_nonzero(tmp_path: Path) -> None:
    empty = tmp_path / "zero.txt"
    nonempty = tmp_path / "data.txt"
    empty.write_bytes(b"")
    nonempty.write_text("x", encoding="utf-8")
    hits = batchutil.empty_files(tmp_path)
    assert empty in hits.paths
    assert nonempty not in hits.paths


def test_scan_cancel_before_walk_is_truncated(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    cancel = Event()
    cancel.set()
    hits = batchutil.older_than(tmp_path, 0, cancel=cancel)
    assert hits.truncated
    assert hits.paths == []


def test_replace_regex_preview_and_apply(tmp_path: Path) -> None:
    src = tmp_path / "n.txt"
    src.write_text("foo1 foo2\n", encoding="utf-8")
    rows = find_core.replace_preview([src], r"foo\d", "x", regex=True)
    assert rows == [(src, 2)]
    done = find_core.replace_apply([src], r"foo\d", "x", regex=True, overwrite=True)
    assert done == [src]
    assert src.read_text(encoding="utf-8") == "x x\n"


def test_replace_invalid_regex_raises(tmp_path: Path) -> None:
    src = tmp_path / "n.txt"
    src.write_text("abc", encoding="utf-8")
    with pytest.raises(find_core.FindError):
        find_core.replace_preview([src], "(", "x", regex=True)


def test_create_symlink_and_refuse_existing(tmp_path: Path) -> None:
    target = tmp_path / "real.txt"
    dest = tmp_path / "alias.txt"
    target.write_text("ok", encoding="utf-8")
    link = fileutil.create_symlink(target, dest)
    assert link.is_symlink()
    assert link.read_text(encoding="utf-8") == "ok"
    with pytest.raises(fileutil.FileUtilError):
        fileutil.create_symlink(target, dest)


def test_relink_symlink_updates_target(tmp_path: Path) -> None:
    old = tmp_path / "old.txt"
    new = tmp_path / "new.txt"
    link = tmp_path / "link"
    old.write_text("old", encoding="utf-8")
    new.write_text("new", encoding="utf-8")
    link.symlink_to(old)
    fileutil.relink_symlink(link, new)
    assert link.is_symlink()
    assert link.resolve() == new.resolve()
    assert link.read_text(encoding="utf-8") == "new"


def test_password_excludes_ambiguous_and_ensures_classes() -> None:
    from core import generate

    for _ in range(20):
        pwd, entropy = generate.password(
            16,
            lower=True,
            upper=True,
            digits=True,
            symbols=True,
            exclude_ambiguous=True,
            ensure_classes=True,
        )
        assert len(pwd) == 16
        assert entropy > 0
        assert not any(ch in "0OIl1" for ch in pwd)
        assert any(ch.islower() for ch in pwd)
        assert any(ch.isupper() for ch in pwd)
        assert any(ch.isdigit() for ch in pwd)
        assert any(ch in "!@#$%^&*()-_=+[]{}" for ch in pwd)


def test_password_batch_and_passphrase_count() -> None:
    from core import generate

    rows = generate.password_batch(3, length=10, symbols=False)
    assert len(rows) == 3
    assert all(len(pwd) == 10 and bits > 0 for pwd, bits in rows)
    phrase = generate.passphrase(5)
    assert len(phrase.split("-")) == 5
