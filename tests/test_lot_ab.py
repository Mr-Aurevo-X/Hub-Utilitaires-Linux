# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from core import codec, hashutil, rename, resize, snippets, textutil
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
