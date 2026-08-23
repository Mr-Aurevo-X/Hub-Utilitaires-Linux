# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

import pytest

from core import (
    batchutil,
    codec,
    color,
    diskmap,
    display_env,
    fileutil,
    find as find_core,
    generate,
    gskenv,
    hashutil,
    i18n,
    pdfutil,
    rename,
    resize,
    settings as app_settings,
    textutil,
    updater,
    workset,
)


def test_update_urls_allow_our_github_only() -> None:
    ok_native = (
        "https://github.com/Mr-Aurevo-X/linux-releases/releases/download/"
        "Hub-Utilitaires-v0.1.0/MrAurevoX_Kit-0.1.0.tar.gz"
    )
    ok_flatpak = (
        "https://github.com/Mr-Aurevo-X/Hub Utilitaires/releases/download/"
        "Hub-Utilitaires-v0.1.0/org.mraurevox.HubUtilitaires.flatpak"
    )
    ok_cdn = "https://release-assets.githubusercontent.com/github-production-release-asset/abc"
    assert updater._require_allowed_url(ok_native, kind="download") == ok_native
    assert updater._require_allowed_url(ok_flatpak, kind="download") == ok_flatpak
    assert updater._require_allowed_url(ok_cdn, kind="any") == ok_cdn
    with pytest.raises(updater.UpdateError):
        updater._require_allowed_url(ok_cdn, kind="download")
    assert updater._require_allowed_url(updater.NATIVE_RELEASES_API, kind="api") == updater.NATIVE_RELEASES_API
    assert updater._require_allowed_url(updater.FLATPAK_RELEASES_API, kind="api") == updater.FLATPAK_RELEASES_API


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/Mr-Aurevo-X/linux-releases/releases",
        "https://evil.example/malware.tar.gz",
        "https://github.com/evil/malware/releases/download/x/x.tar.gz",
        "https://api.github.com/repos/evil/malware/releases",
        "file:///etc/passwd",
        "https://user:pass@github.com/Mr-Aurevo-X/linux-releases/x",
        "https://github.com:8443/Mr-Aurevo-X/linux-releases/x",
        "javascript:alert(1)",
    ],
)
def test_update_urls_reject_backdoors(url: str) -> None:
    with pytest.raises(updater.UpdateError):
        updater._require_allowed_url(url, kind="any")


def test_asset_url_ignores_foreign_download() -> None:
    item = {
        "assets": [
            {
                "name": "MrAurevoX_Kit-0.1.0.tar.gz",
                "browser_download_url": "https://evil.example/backdoor.tar.gz",
            }
        ]
    }
    url = updater._asset_url(item, "0.1.0", "native")
    assert url == updater.public_download_url("0.1.0", "native")
    updater._require_allowed_url(url, kind="download")


def test_rename_preview_and_apply(tmp_path: Path) -> None:
    a = tmp_path / "photo.jpg"
    b = tmp_path / "scan.png"
    a.write_text("a", encoding="utf-8")
    b.write_text("b", encoding="utf-8")
    rows = rename.preview([a, b], r"(.*)\.(\w+)$", r"\1_{n:03d}.\2")
    assert rows[0][1] == "photo_001.jpg"
    assert rows[1][1] == "scan_002.png"
    done = rename.apply(rows)
    assert (tmp_path / "photo_001.jpg").is_file()
    assert (tmp_path / "scan_002.png").is_file()
    assert len(done) == 2


def test_find_names(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("hello", encoding="utf-8")
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "beta.log").write_text("needle here", encoding="utf-8")
    names = find_core.search_names(tmp_path, "alpha")
    assert any(p.name == "alpha.txt" for p in names)
    content = find_core.search_content(tmp_path, "needle")
    assert any(p.name == "beta.log" for p in content)


def test_hash_sha256(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    f.write_bytes(b"abc")
    digest = hashutil.file_hash(f, "sha256")
    assert digest == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert hashutil.matches(f, digest, "sha256")
    assert not hashutil.matches(f, "00" * 32, "sha256")


def test_hash_blake2b_and_compare(tmp_path: Path) -> None:
    import hashlib

    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"abc")
    b.write_bytes(b"abc")
    digest = hashutil.file_hash(a, "blake2b")
    assert digest == hashlib.blake2b(b"abc").hexdigest()
    ha, hb, same = hashutil.compare_files(a, b, "sha256")
    assert same and ha == hb
    b.write_bytes(b"xyz")
    _ha, _hb, same = hashutil.compare_files(a, b, "sha256")
    assert not same


def test_pdf_merge_extract_rotate(tmp_path: Path) -> None:
    pytest.importorskip("pypdf")
    from pypdf import PdfReader, PdfWriter

    src_a = tmp_path / "a.pdf"
    src_b = tmp_path / "b.pdf"
    for path, count in ((src_a, 2), (src_b, 1)):
        writer = PdfWriter()
        for _ in range(count):
            writer.add_blank_page(width=72, height=72)
        with path.open("wb") as handle:
            writer.write(handle)
    merged = tmp_path / "m.pdf"
    pdfutil.merge([src_a, src_b], merged)
    assert len(PdfReader(str(merged)).pages) == 3
    extracted = tmp_path / "e.pdf"
    pdfutil.extract(merged, extracted, "1-2")
    assert len(PdfReader(str(extracted)).pages) == 2
    rotated = tmp_path / "r.pdf"
    pdfutil.rotate(merged, rotated, 90)
    assert len(PdfReader(str(rotated)).pages) == 3


def test_codec_json_jwt_base64() -> None:
    import base64
    import json

    pretty = codec.pretty_json('{"a":1}')
    assert '"a": 1' in pretty
    assert codec.minify_json(pretty) == '{"a":1}'
    assert codec.b64_decode(codec.b64_encode("café")) == "café"
    yaml_out = codec.pretty_yaml("a: 1\nb: 2\n")
    assert "a:" in yaml_out

    def b64url(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    token = f"{b64url({'alg': 'none', 'typ': 'JWT'})}.{b64url({'sub': '1'})}."
    decoded = codec.decode_jwt(token)
    assert '"sub": "1"' in decoded
    assert "non vérifiée" in decoded or "pas de signature" in decoded


def test_regex_and_diff() -> None:
    rows, count = textutil.regex_matches(r"a+", "baa a")
    assert count == 2
    diff = textutil.unified_diff("a\n", "b\n")
    assert "-a" in diff and "+b" in diff
    assert textutil.transform("  x  ", "trim") == "x"


def test_timestamps_and_units() -> None:
    assert generate.unix_to_iso("0") == "1970-01-01T00:00:00Z"
    assert float(generate.iso_to_unix("1970-01-01T00:00:00Z")) == 0.0
    assert generate.convert_unit(1.0, "km", "mi", "length") == pytest.approx(1000 / 1609.344)
    assert generate.convert_unit(100.0, "c", "f", "temp") == pytest.approx(212.0)
    uid = generate.new_uuid()
    assert len(uid) == 36


def test_i18n_fr_en_keys() -> None:
    assert set(i18n._FR) == set(i18n._EN)


def test_i18n_en_is_english() -> None:
    previous = i18n.language()
    try:
        i18n.set_language("EN")
        assert i18n.language() == "en"
        assert i18n.t("find") == "Search"
        assert i18n.t("save") == "Save"
        assert i18n.t("preferences") == "Preferences"
        assert i18n.t("nav_daily") == "Daily"
        i18n.set_language("de")
        assert i18n.language() == "fr"
        assert i18n.t("find") == "Recherche"
    finally:
        i18n.set_language(previous)


def test_normalize_and_coerce_language() -> None:
    assert i18n.normalize_language("en-US") == "en"
    assert i18n.normalize_language("FR") == "fr"
    assert app_settings.coerce_language("EN") == "en"
    assert app_settings.coerce_language("nope") == "fr"


def test_python_310_min() -> None:
    import sys

    assert sys.version_info >= (3, 10)


def test_mint_gtk46_adw11_apis_go_through_compat() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "Adw.ViewStack(",
        "Adw.ToolbarView(",
        "Adw.NavigationSplitView(",
        "Adw.NavigationPage(",
        "Adw.SwitchRow(",
        "Adw.SpinRow(",
        "Adw.AlertDialog(",
        "Gtk.ColorDialog(",
        "Gtk.DropDown",
    )
    file_dialog_ok = {"compat.py"}
    for path in sorted((root / "ui").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name != "compat.py":
            for needle in forbidden:
                assert needle not in text, f"{path.relative_to(root)} : {needle} (Mint 21.3) — ui.compat"
        if path.name not in file_dialog_ok:
            assert "Gtk.FileDialog(" not in text, f"{path.relative_to(root)} : Gtk.FileDialog (GTK 4.10)"
    prefs = (root / "ui" / "pages" / "prefs_page.py").read_text(encoding="utf-8")
    assert "Adw.ComboRow" not in prefs
    assert "ComboBoxText" in prefs
    assert "on_language" in prefs


def test_ui_pages_import_common_when_used() -> None:
    import ast

    root = Path(__file__).resolve().parents[1] / "ui" / "pages"
    for path in sorted(root.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        uses = False
        imported = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "common":
                uses = True
            if isinstance(node, ast.ImportFrom):
                if any(alias.name == "common" for alias in node.names):
                    imported = True
        if uses:
            assert imported, f"{path.name} utilise common sans l’importer"


def test_gsk_cairo_on_mint_jammy_vm(monkeypatch) -> None:
    monkeypatch.delenv("GSK_RENDERER", raising=False)
    mint = 'NAME="Linux Mint"\nID=linuxmint\nID_LIKE=ubuntu\nVERSION_ID="21.3"\n'
    assert gskenv.choose_renderer(os_release=mint, virt="none") == "cairo"
    jammy = 'ID=ubuntu\nUBUNTU_CODENAME=jammy\nVERSION_ID="22.04"\n'
    assert gskenv.choose_renderer(os_release=jammy, virt="none") == "cairo"
    assert gskenv.choose_renderer(os_release="ID=cachyos\n", virt="oracle") == "cairo"
    assert gskenv.choose_renderer(os_release="ID=cachyos\n", virt="none") is None
    monkeypatch.setenv("GSK_RENDERER", "ngl")
    assert gskenv.choose_renderer(os_release=mint, virt="oracle") is None


def test_needs_safe_display_mint_and_vm() -> None:
    assert display_env.needs_safe_display({"ID": "linuxmint", "VERSION_ID": "21.3"})
    assert display_env.needs_safe_display({"ID": "ubuntu", "VERSION_ID": "22.04", "VERSION_CODENAME": "jammy"})
    assert display_env.needs_safe_display({"ID": "cachyos"}, virt="oracle")
    assert display_env.needs_safe_display({"ID": "cachyos"}, product_name="VirtualBox")
    assert not display_env.needs_safe_display({"ID": "cachyos"}, virt="none")


def test_lancer_applies_display_env_before_gtk() -> None:
    root = Path(__file__).resolve().parents[1]
    lancer = (root / "LANCER.sh").read_text(encoding="utf-8")
    assert "apply_safe_display_env" in lancer
    assert lancer.find("apply_safe_display_env") < lancer.find("gi.require_version")
    main = (root / "main.py").read_text(encoding="utf-8")
    assert "NON_UNIQUE" in main
    window = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert 'connect("map"' in window
    assert "fenêtre ouverte" in window


def test_qr_png(tmp_path: Path) -> None:
    dest = tmp_path / "qr.png"
    generate.qr_png("hello", dest)
    assert dest.is_file() and dest.stat().st_size > 32


def test_find_filters_empty_replace_export(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("hello world", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("hello world", encoding="utf-8")
    empty = tmp_path / "empty"
    empty.mkdir()
    names = find_core.search_names(tmp_path, "keep", extensions="py")
    assert [p.name for p in names] == ["keep.py"]
    assert find_core.empty_dirs(tmp_path)
    preview = find_core.replace_preview([tmp_path / "keep.py"], "world", "kit")
    assert preview[0][1] == 1
    dests = find_core.replace_apply([tmp_path / "keep.py"], "world", "kit", overwrite=False)
    assert dests[0].name == "keep_kit.py"
    assert "hello kit" in dests[0].read_text(encoding="utf-8")
    assert "keep.py" in find_core.export_paths(names, csv_mode=True)


def test_rename_tokens_case_undo(tmp_path: Path) -> None:
    src = tmp_path / "Photo.JPG"
    src.write_text("x", encoding="utf-8")
    rows = rename.preview([src], "", "{stem}_{n:04d}{ext}", case_mode="lower")
    assert rows[0][1] == "photo_0001.jpg"
    done = rename.apply(rows)
    assert (tmp_path / "photo_0001.jpg").is_file()
    undone = rename.undo_last()
    assert undone[0].name == "Photo.JPG"
    assert src.is_file()


def test_hash_crc32_hmac_manifest(tmp_path: Path) -> None:
    import binascii
    import hmac as hmaclib

    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    assert hashutil.file_hash(f, "crc32") == f"{binascii.crc32(b'abc') & 0xFFFFFFFF:08x}"
    digest = hashutil.file_hmac(f, "secret", "sha256")
    assert digest == hmaclib.new(b"secret", b"abc", "sha256").hexdigest()
    (tmp_path / "b.bin").write_bytes(b"abc")
    manifest = hashutil.checksums_manifest(tmp_path)
    line = manifest.splitlines()[0]
    assert hashutil.matches_manifest_line(tmp_path / line.split()[-1], line)


def test_image_ops_and_info(tmp_path: Path) -> None:
    from PIL import Image

    src = tmp_path / "in.png"
    Image.new("RGB", (40, 20), (10, 20, 30)).save(src)
    dest = tmp_path / "out.png"
    resize.convert_image(src, dest, max_width=20, grayscale=True, rotate=90, watermark="K")
    info = resize.image_info(dest)
    assert info["width"] == 20
    assert info["height"] == 40


def test_pdf_split_meta_password(tmp_path: Path) -> None:
    pypdf = pytest.importorskip("pypdf")
    PdfReader = pypdf.PdfReader
    PdfWriter = pypdf.PdfWriter

    src = tmp_path / "src.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({"/Title": "Secret"})
    with src.open("wb") as handle:
        writer.write(handle)
    data = pdfutil.info(src)
    assert data["pages"] == 2
    pages = pdfutil.split_pages(src, tmp_path / "pages")
    assert len(pages) == 2
    stripped = tmp_path / "meta.pdf"
    pdfutil.strip_metadata(src, stripped)
    enc = tmp_path / "enc.pdf"
    pdfutil.encrypt(src, enc, "pw")
    assert PdfReader(str(enc)).is_encrypted
    dec = tmp_path / "dec.pdf"
    pdfutil.decrypt(enc, dec, "pw")
    assert len(PdfReader(str(dec)).pages) == 2
    blank = tmp_path / "blank.pdf"
    pdfutil.insert_blank(src, blank, 1)
    assert len(PdfReader(str(blank)).pages) == 3


def test_color_harmony_contrast_gradient(tmp_path: Path) -> None:
    from PIL import Image

    src = tmp_path / "c.png"
    Image.new("RGB", (16, 16), (255, 0, 0)).save(src)
    r, g, b = 1.0, 0.0, 0.0
    comp = color.complementary(r, g, b)
    assert color.hex_from_rgb(*comp).startswith("#")
    assert color.contrast_ratio((0, 0, 0), (1, 1, 1)) == pytest.approx(21.0)
    assert color.palette_from_image(src, 3)
    dest = tmp_path / "g.png"
    color.gradient_png((1, 0, 0), (0, 0, 1), dest)
    assert dest.is_file()


def test_text_line_endings_and_slug() -> None:
    assert textutil.transform("Café Noir!", "slug") == "cafe-noir"
    assert textutil.transform("a\r\nb", "lf") == "a\nb"
    assert textutil.counts("un deux")["words"] == 2
    assert len(textutil.sha256_text("x")) == 64


def test_codec_xml_csv_json_rot13() -> None:
    xml = codec.pretty_xml("<a><b>1</b></a>")
    assert "<b>" in xml
    assert codec.rot13("ab") == "no"
    csv_text = "n,v\na,1\n"
    js = codec.csv_to_json(csv_text)
    assert '"n": "a"' in js
    back = codec.json_to_csv(js)
    assert "n,v" in back
    flat = codec.flatten_json('{"a":{"b":1}}')
    assert "a.b" in flat


def test_generate_password_bases_dates() -> None:
    pwd, entropy = generate.password(12, symbols=True)
    assert len(pwd) == 12 and entropy > 0
    assert generate.pin(4).isdigit()
    assert "-" in generate.passphrase(3)
    assert generate.convert_base("ff", 16, 10) == "255"
    assert generate.convert_unit(1.0, "kib", "b", "size") == 1024.0
    assert generate.week_number("2026-01-05T00:00:00Z") == 2
    assert generate.new_uuid5("example.com").count("-") == 4
    assert "Lorem" in generate.lorem()


def test_fileutil_hex_zip_split(tmp_path: Path) -> None:
    src = tmp_path / "a.txt"
    src.write_text("hello\n", encoding="utf-8")
    dump = fileutil.hexdump_file(src)
    assert "68 65 6c 6c 6f" in dump
    assert fileutil.guess_encoding(src) == "utf-8"
    assert fileutil.first_diff(src, src) is None
    zdest = tmp_path / "a.zip"
    fileutil.create_zip([src], zdest)
    names = fileutil.list_archive(zdest)
    assert "a.txt" in names
    out = tmp_path / "out"
    extracted = fileutil.extract_archive(zdest, out)
    assert extracted[0].read_text(encoding="utf-8") == "hello\n"
    parts = fileutil.split_file(src, tmp_path / "parts", 0.000001)
    joined = fileutil.join_files(parts, tmp_path / "joined.txt")
    assert joined.read_bytes() == src.read_bytes()


def test_batch_duplicates_and_stats(tmp_path: Path) -> None:
    (tmp_path / "a.bin").write_bytes(b"same")
    (tmp_path / "b.bin").write_bytes(b"same")
    (tmp_path / "c.bin").write_bytes(b"other")
    groups = batchutil.sha256_duplicates(tmp_path)
    assert len(groups) == 1 and len(groups[0]) == 2
    dest = tmp_path / "copies"
    moved = batchutil.move_copies(groups, dest)
    assert len(moved) == 1
    assert (tmp_path / "a.bin").exists() or (tmp_path / "b.bin").exists()
    stats = batchutil.folder_stats(tmp_path)
    assert stats["files"] >= 2


def test_diskmap_sizes(tmp_path: Path) -> None:
    (tmp_path / "big.bin").write_bytes(b"x" * 100)
    nested = tmp_path / "sub"
    nested.mkdir()
    (nested / "small.bin").write_bytes(b"y" * 10)
    total, entries, hidden = diskmap.scan_children(tmp_path, skip_known=False)
    assert total == 110
    assert hidden == 0
    names = {e.name: e.size for e in entries}
    assert names["big.bin"] == 100
    assert names["sub"] == 10
    csv_text = diskmap.export_csv(entries)
    assert "big.bin" in csv_text
    with pytest.raises(diskmap.DiskMapError):
        diskmap.scan_children(Path("/"))


def test_path_hits_truncated_when_limit_reached(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"hit-{index}.txt").write_text("x", encoding="utf-8")
    hits = find_core.search_names(tmp_path, "hit", limit=3)
    assert isinstance(hits, find_core.PathHits)
    assert hits.truncated is True
    assert hits.limit == 3
    assert len(hits.paths) == 3
    full = find_core.search_names(tmp_path, "hit", limit=10)
    assert full.truncated is False
    assert len(full.paths) == 5


def test_search_limit_reads_find_max_results() -> None:
    assert app_settings.search_limit({"find_max_results": 400}) == 400
    assert app_settings.search_limit({"find_max_results": 12}) == 12
    assert app_settings.search_limit({}) == 400


def test_language_prompt_first_run_and_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    fresh = app_settings.load_settings()
    assert fresh["language_chosen"] is False
    assert app_settings.needs_language_prompt(fresh) is True
    fresh["language"] = "en"
    fresh["language_chosen"] = True
    app_settings.save_settings(fresh)
    again = app_settings.load_settings()
    assert again["language"] == "en"
    assert again["language_chosen"] is True
    assert app_settings.needs_language_prompt(again) is False
    path = app_settings.settings_path() if hasattr(app_settings, "settings_path") else None
    if path is None:
        from core.paths import settings_path

        path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"language": "fr", "last_page": "find"}\n', encoding="utf-8")
    old = app_settings.load_settings()
    assert old["language_chosen"] is False
    assert app_settings.needs_language_prompt(old) is True


def test_settings_last_folder_and_page_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    loaded = app_settings.load_settings()
    assert loaded["last_folder"] == ""
    assert loaded["last_page"] == "find"
    assert "find_root" not in loaded
    loaded["last_folder"] = str(tmp_path)
    loaded["last_page"] = "lots"
    loaded["find_max_results"] = 250
    loaded["language"] = "EN"
    app_settings.save_settings(loaded)
    again = app_settings.load_settings()
    assert again["last_folder"] == str(tmp_path)
    assert again["last_page"] == "lots"
    assert again["find_max_results"] == 250
    assert again["language"] == "en"


def test_settings_migrates_find_root_to_last_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = app_settings.settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"find_root": "/old/downloads", "language": "fr"}\n', encoding="utf-8")
    loaded = app_settings.load_settings()
    assert loaded["last_folder"] == "/old/downloads"


def test_sha256_duplicates_paths_and_progress(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    c = tmp_path / "c.bin"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    c.write_bytes(b"other")
    seen: list[tuple[int, int]] = []
    groups = batchutil.sha256_duplicates_paths([a, b, c], on_progress=lambda done, total: seen.append((done, total)))
    assert len(groups) == 1 and len(groups[0]) == 2
    assert seen[-1] == (3, 3)
    assert seen[0][1] == 3


def test_move_copies_keeps_one_original(tmp_path: Path) -> None:
    a = tmp_path / "keep.bin"
    b = tmp_path / "copy.bin"
    a.write_bytes(b"same")
    b.write_bytes(b"same")
    dest = tmp_path / "copies"
    moved = batchutil.move_copies([[a, b]], dest)
    assert len(moved) == 1
    remaining = [path for path in (a, b) if path.exists()]
    assert len(remaining) == 1


def test_welcome_language_dialog_uses_compat() -> None:
    window = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "_prompt_language" in window
    assert "compat.present_alert(" in window
    assert "welcome_lang" in window
    assert i18n._FR["welcome_lang"] == i18n._EN["welcome_lang"]
    assert i18n._FR["welcome_lang_body"] == i18n._EN["welcome_lang_body"]


def test_legal_dialog_is_not_truncated() -> None:
    window = (Path(__file__).resolve().parents[1] / "ui" / "main_window.py").read_text(encoding="utf-8")
    assert "[:4000]" not in window


def test_i18n_has_hero_keys() -> None:
    for key in (
        "truncated",
        "send_rename",
        "send_lots",
        "lots_group",
        "hits_count",
        "hits_truncated",
        "nav_daily",
        "nav_files",
        "nav_workshop",
        "send_hash",
        "send_images",
        "send_pdf",
        "send_file",
        "send_textdiff",
        "textdiff",
        "secrets",
        "snippets",
        "group_replace",
        "group_more",
        "find_max_results",
        "welcome_lang",
        "welcome_lang_body",
    ):
        assert key in i18n._FR
        assert key in i18n._EN


def test_workset_from_paths_and_existing_only(tmp_path: Path) -> None:
    alive = tmp_path / "keep.txt"
    gone = tmp_path / "gone.txt"
    alive.write_text("ok", encoding="utf-8")
    gone.write_text("bye", encoding="utf-8")
    raw = workset.from_paths(tmp_path, [alive, gone, tmp_path / "never.txt"])
    assert raw.folder == tmp_path
    assert gone in raw.paths
    gone.unlink()
    cleaned = workset.existing_only(raw)
    assert cleaned.paths == [alive]
    assert cleaned.folder == tmp_path


def test_send_targets_allowlisted() -> None:
    for key in ("rename", "lots", "hash", "resize", "pdf", "file", "textdiff"):
        assert workset.coerce_send_target(key) == key
    with pytest.raises(ValueError):
        workset.coerce_send_target("color")
    with pytest.raises(ValueError):
        workset.coerce_send_target("network")


def test_batch_scan_truncated_flag(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"f-{index}.bin").write_bytes(b"x" * (index + 1))
    hits = batchutil.sha256_duplicates(tmp_path, limit=3)
    assert isinstance(hits, batchutil.GroupHits)
    assert hits.truncated is True
    assert hits.limit == 3
    names = batchutil.same_names(tmp_path, limit=3)
    assert names.truncated is True
    old = batchutil.older_than(tmp_path, 0, limit=3)
    assert isinstance(old, find_core.PathHits)
    assert old.truncated is True
    large = batchutil.larger_than(tmp_path, 0, limit=3)
    assert large.truncated is True


def test_move_copies_subset_of_groups(tmp_path: Path) -> None:
    a1 = tmp_path / "a1.bin"
    a2 = tmp_path / "a2.bin"
    b1 = tmp_path / "b1.bin"
    b2 = tmp_path / "b2.bin"
    a1.write_bytes(b"aaa")
    a2.write_bytes(b"aaa")
    b1.write_bytes(b"bbb")
    b2.write_bytes(b"bbb")
    dest = tmp_path / "out"
    moved = batchutil.move_copies([[a1, a2]], dest)
    assert len(moved) == 1
    assert b1.exists() and b2.exists()
    remaining_a = [path for path in (a1, a2) if path.exists()]
    assert len(remaining_a) == 1


def test_rename_undo_persists_and_refuses_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    src = tmp_path / "once.txt"
    src.write_text("x", encoding="utf-8")
    rows = rename.preview([src], "once", "twice")
    rename.apply(rows)
    renamed = tmp_path / "twice.txt"
    assert renamed.is_file()
    payload = (tmp_path / "data" / "hub-utilitaires" / "rename-undo.json").read_text(encoding="utf-8")
    assert "twice.txt" in payload
    renamed.unlink()
    with pytest.raises(rename.RenameError):
        rename.undo_last()
    src.write_text("x", encoding="utf-8")
    rename.apply(rename.preview([src], "once", "again"))
    assert rename.undo_last()[0].name == "once.txt"


def test_update_dialog_splits_commands_from_body() -> None:
    from core.update_fetch import format_update_dialog_body, format_update_dialog_commands

    info = {
        "version": "2.2.7",
        "current": "2.2.6",
        "html_url": "https://github.com/Mr-Aurevo-X/Hub Utilitaires/releases/tag/Hub-Utilitaires-v2.2.7",
        "channel": "flatpak",
        "notes": "## Hub Utilitaires 2.2.7\nNotes release.",
    }
    body = format_update_dialog_body(info)
    commands = format_update_dialog_commands(info)
    assert "curl -fL" in commands
    assert "flatpak install" in commands
    assert "INSTALLER-RACCOURCI-FLATPAK" in commands
    assert "curl -fL" not in body
    assert "flatpak install" not in body
    assert "Notes release." in body


def test_nav_registry_covers_all_pages() -> None:
    from core import settings as app_settings
    from ui.nav import nav_groups, validate_nav_registry

    validate_nav_registry()
    keys = [page.key for group in nav_groups() for page in group.pages]
    assert len(keys) == len(set(keys))
    assert set(keys) == set(app_settings.PAGE_KEYS)


def test_nav_groups_expanded_settings_roundtrip(tmp_path, monkeypatch) -> None:
    from core import settings as app_settings

    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setattr(app_settings, "config_dir", lambda: cfg)
    settings = app_settings.load_settings()
    state = app_settings.nav_groups_expanded(settings, "hash")
    assert state["media"] is True
    state["explorer"] = False
    app_settings.save_nav_groups_expanded(settings, state)
    loaded = app_settings.load_settings()
    assert loaded["nav_groups_expanded"]["media"] is True
    assert loaded["nav_groups_expanded"]["explorer"] is False
