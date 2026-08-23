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
    assert "broken_doc_links" in lots_src
    assert "eol_audit_text" in lots_src
    assert "near_duplicate_images" in lots_src
    assert "empty_files" in lots_src
    assert "_do_cancel" in lots_src
    assert "on_send" in lots_src
    assert "set_draw_func" in disk_src
    assert "treemap_rects" in disk_src
    file_src = (root / "ui" / "pages" / "file_page.py").read_text(encoding="utf-8")
    pdf_src = (root / "ui" / "pages" / "pdf_page.py").read_text(encoding="utf-8")
    assert "diff_archive_members" in file_src
    assert "create_symlink" in file_src
    assert "pdfutil.inventory" in pdf_src
    assert "save_file" not in pdf_src.split("def _inventory")[1].split("def _")[0]
    assert "present_alert" in find_src
    assert "regex=regex" in find_src
    atelier_src = (root / "ui" / "pages" / "atelier_page.py").read_text(encoding="utf-8")
    assert '_tab_password()' in atelier_src
    assert "atelier_password" in atelier_src
    gen_tab = atelier_src.split("def _tab_generate")[1].split("def _")[0]
    assert "gen_password" not in gen_tab


def test_product_truth_hub_not_kit_identity() -> None:
    root = Path(__file__).resolve().parents[1]
    modules = (root / "MODULES.md").read_text(encoding="utf-8")
    assert "devises" not in modules.lower()
    assert "Unités" in modules
    meta = (root / "packaging" / "flatpak" / "org.mraurevox.HubUtilitaires.metainfo.xml").read_text(
        encoding="utf-8"
    )
    assert "github.com/Mr-Aurevo-X/Hub Utilitaires" not in meta
    assert '<url type="homepage">https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux</url>' in meta
    update_url = (root / "core" / "update_url.py").read_text(encoding="utf-8")
    assert "Kit updates" not in update_url
    assert "SOURCE_REPO" in update_url
    assert "MrAurevoX_Kit-{version}.tar.gz" in update_url
    compat = (root / "packaging" / "COMPAT.md").read_text(encoding="utf-8")
    assert "Hub Utilitaires" in compat
    assert "historique" in compat.lower()


def test_language_toggle_relabels_without_rebuild() -> None:
    root = Path(__file__).resolve().parents[1]
    window = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    apply = window.split("def _apply_language")[1].split("\n    def ")[0]
    assert "_rebuild_pages" not in apply
    assert "_relabel_ui" in apply
    assert "def _relabel_ui" in window
    common_src = (root / "ui" / "pages" / "common.py").read_text(encoding="utf-8")
    assert "def bind_i18n" in common_src
    assert "def relabel_tree" in common_src


def test_relabel_tree_updates_bound_label() -> None:
    from gi.repository import Gtk

    from core import i18n
    from ui.pages.atelier_page import AtelierPage
    from ui.pages import common

    previous = i18n.language()
    try:
        i18n.set_language("fr")
        btn = Gtk.Button()
        common.bind_i18n(btn, "copy", "label")
        assert btn.get_label() == "Copier"
        i18n.set_language("en")
        common.relabel_tree(btn)
        assert btn.get_label() == "Copy"
        win = Gtk.Window()
        page = AtelierPage(win, Gtk.Label())
        buf = page._text_in.get_buffer()
        buf.set_text("KEEP-STATE")
        page.relabel()
        start, end = buf.get_start_iter(), buf.get_end_iter()
        assert buf.get_text(start, end, True) == "KEEP-STATE"
    finally:
        i18n.set_language(previous)
