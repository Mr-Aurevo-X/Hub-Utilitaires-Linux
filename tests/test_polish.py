# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import pytest

from core import batchutil, diskmap
from core import settings as app_settings


def test_preview_move_copies_does_not_move(tmp_path: Path) -> None:
    older = tmp_path / "keep.bin"
    newer = tmp_path / "copy.bin"
    older.write_bytes(b"same")
    newer.write_bytes(b"same")
    stamp = older.stat().st_mtime
    import os

    os.utime(older, (stamp - 10, stamp - 10))
    dest = tmp_path / "copies"
    planned = batchutil.preview_move_copies([[older, newer]], dest)
    assert planned == [(newer, dest / "copy.bin")]
    assert older.exists()
    assert newer.exists()
    assert not dest.exists()


def test_preview_move_copies_avoids_name_clash(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "dup" / "a.bin"
    b.parent.mkdir()
    a.write_bytes(b"xx")
    b.write_bytes(b"xx")
    dest = tmp_path / "out"
    dest.mkdir()
    taken = dest / "a.bin"
    taken.write_bytes(b"keep")
    planned = batchutil.preview_move_copies([[a, b]], dest)
    assert len(planned) == 1
    assert planned[0][1].name == "a_2.bin"


def test_treemap_rects_fill_area() -> None:
    entries = [
        diskmap.DiskEntry(Path("/tmp/big"), "big", False, 75, 75.0),
        diskmap.DiskEntry(Path("/tmp/mid"), "mid", False, 20, 20.0),
        diskmap.DiskEntry(Path("/tmp/small"), "small", False, 5, 5.0),
    ]
    rects = diskmap.treemap_rects(entries, 200.0, 100.0)
    assert [item.name for item in rects] == ["big", "mid", "small"]
    area = sum(item.w * item.h for item in rects)
    assert area == pytest.approx(20_000.0, rel=1e-6)
    assert all(item.w > 0 and item.h > 0 for item in rects)


def test_treemap_rects_empty_and_zero_size() -> None:
    assert diskmap.treemap_rects([], 100.0, 100.0) == []
    empty = diskmap.DiskEntry(Path("/tmp/z"), "z", False, 0, 0.0)
    assert diskmap.treemap_rects([empty], 100.0, 100.0) == []


def test_favorite_searches_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    settings = app_settings.load_settings()
    assert app_settings.favorite_searches(settings) == []
    app_settings.toggle_favorite_search(settings, folder=str(tmp_path), query="*.py", content="TODO")
    saved = app_settings.favorite_searches(settings)
    assert saved == [{"folder": str(tmp_path), "query": "*.py", "content": "TODO"}]
    app_settings.save_settings(settings)
    again = app_settings.load_settings()
    assert app_settings.favorite_searches(again) == saved
    app_settings.toggle_favorite_search(again, folder=str(tmp_path), query="*.py", content="TODO")
    assert app_settings.favorite_searches(again) == []


def test_polish_ui_hooks_present() -> None:
    root = Path(__file__).resolve().parents[1]
    find_src = (root / "ui" / "pages" / "find_page.py").read_text(encoding="utf-8")
    lots_src = (root / "ui" / "pages" / "lots_page.py").read_text(encoding="utf-8")
    disk_src = (root / "ui" / "pages" / "disk_page.py").read_text(encoding="utf-8")
    assert "toggle_favorite_search" in find_src
    assert "preview_move_copies" in lots_src
    assert "set_draw_func" in disk_src
    assert "treemap_rects" in disk_src
