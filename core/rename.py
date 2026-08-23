# SPDX-License-Identifier: GPL-3.0-or-later
"""Batch rename with regex preview. Local only."""

from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

_LAST_UNDO: list[tuple[Path, Path]] = []


def _data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    path = base / "hub-utilitaires"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def _undo_path() -> Path:
    return _data_dir() / "rename-undo.json"


def _save_undo(mapping: list[tuple[Path, Path]]) -> None:
    payload = [[str(current), str(original)] for current, original in mapping]
    try:
        _undo_path().write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        return


def _load_undo() -> list[tuple[Path, Path]]:
    try:
        path = _undo_path()
    except OSError:
        return list(_LAST_UNDO)
    if not path.is_file():
        return list(_LAST_UNDO)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return list(_LAST_UNDO)
    if not isinstance(raw, list) or not raw:
        return list(_LAST_UNDO)
    out: list[tuple[Path, Path]] = []
    for item in raw:
        if isinstance(item, list) and len(item) == 2:
            out.append((Path(str(item[0])), Path(str(item[1]))))
    return out or list(_LAST_UNDO)


class RenameError(Exception):
    pass


def _exif_date(path: Path) -> str:
    try:
        from PIL import ExifTags, Image
    except ImportError:
        return ""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return ""
            tags = getattr(ExifTags, "TAGS", {})
            wanted = {name: key for key, name in tags.items() if name in {"DateTimeOriginal", "DateTime"}}
            for name in ("DateTimeOriginal", "DateTime"):
                key = wanted.get(name)
                if key is None:
                    continue
                raw = exif.get(key)
                if not raw:
                    continue
                text = str(raw).strip().replace(":", "-", 2)
                return text.split(" ")[0]
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _mtime_dt(path: Path) -> datetime:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime)
    except OSError:
        return datetime.now()


def _expand_tokens(path: Path, name: str, counter: int) -> str:
    now = datetime.now()
    mtime = _mtime_dt(path)
    out = name
    out = re.sub(r"\{mtime:([^}]+)\}", lambda m: mtime.strftime(m.group(1)), out)
    out = out.replace("{mtime}", mtime.strftime("%Y-%m-%d"))
    out = re.sub(r"\{date:([^}]+)\}", lambda m: now.strftime(m.group(1)), out)
    out = out.replace("{date}", now.strftime("%Y-%m-%d"))
    if "{exif_date}" in out:
        out = out.replace("{exif_date}", _exif_date(path) or now.strftime("%Y-%m-%d"))
    out = out.replace("{stem}", path.stem)
    out = out.replace("{ext}", path.suffix)
    out = out.replace("{parent}", path.parent.name)
    if "{hash8}" in out:
        try:
            from core.hashutil import file_hash

            out = out.replace("{hash8}", file_hash(path, "sha256")[:8])
        except OSError:
            out = out.replace("{hash8}", "00000000")
    out = out.replace("{n:04d}", f"{counter:04d}")
    out = out.replace("{n:03d}", f"{counter:03d}")
    out = out.replace("{n}", str(counter))
    return out


def _case_name(name: str, mode: str) -> str:
    key = (mode or "").strip().lower()
    if not key:
        return name
    stem, suffix = Path(name).stem, Path(name).suffix
    if key == "lower":
        return stem.lower() + suffix.lower()
    if key == "upper":
        return stem.upper() + suffix.upper()
    if key == "title":
        return stem.title() + suffix
    if key == "snake":
        cleaned = re.sub(r"[^\w]+", "_", stem, flags=re.UNICODE).strip("_").lower()
        return (cleaned or stem.lower()) + suffix.lower()
    if key == "kebab":
        cleaned = re.sub(r"[^\w]+", "-", stem, flags=re.UNICODE).strip("-").lower()
        return (cleaned or stem.lower()) + suffix.lower()
    raise RenameError(f"casse inconnue : {mode}")


def _sanitize(name: str) -> str:
    stem, suffix = Path(name).stem, Path(name).suffix
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip(" ._")
    return (cleaned or "file") + suffix


def _affix(name: str, prefix: str, suffix: str) -> str:
    stem, ext = Path(name).stem, Path(name).suffix
    return f"{prefix}{stem}{suffix}{ext}"


def _unique_name(src: Path, new_name: str, used: set[str], policy: str) -> str | None:
    dest = src.with_name(new_name)
    key = str(dest.resolve()) if dest.parent.exists() else str(dest)
    if dest == src:
        used.add(key)
        return new_name
    if key not in used and not dest.exists():
        used.add(key)
        return new_name
    if policy == "overwrite":
        used.add(key)
        return new_name
    if policy == "skip":
        return None
    if policy not in {"suffix", "error"}:
        raise RenameError(f"collision inconnue : {policy}")
    if policy == "error" and (dest.exists() or key in used):
        raise RenameError(f"existe déjà : {dest}")
    stem, ext = Path(new_name).stem, Path(new_name).suffix
    n = 2
    while n < 10000:
        cand = f"{stem}_{n}{ext}"
        dest = src.with_name(cand)
        key = str(dest)
        if key not in used and not dest.exists():
            used.add(key)
            return cand
        n += 1
    raise RenameError(f"trop de collisions : {new_name}")


def preview(
    paths: list[Path],
    pattern: str,
    repl: str,
    *,
    case_mode: str = "",
    prefix: str = "",
    suffix: str = "",
    sanitize: bool = False,
    collision: str = "suffix",
) -> list[tuple[Path, str]]:
    compiled = None
    raw_pat = pattern or ""
    if raw_pat:
        try:
            compiled = re.compile(raw_pat)
        except re.error as exc:
            raise RenameError(f"regex invalide : {exc}") from exc
    rows: list[tuple[Path, str]] = []
    used: set[str] = set()
    counter = 0
    for path in paths:
        counter += 1
        if compiled is None:
            new_name = repl
        else:
            new_name = compiled.sub(repl, path.name)
        new_name = _expand_tokens(path, new_name, counter)
        new_name = _affix(new_name, prefix, suffix)
        if sanitize:
            new_name = _sanitize(new_name)
        new_name = _case_name(new_name, case_mode)
        if not new_name or new_name in {".", ".."} or "/" in new_name or "\\" in new_name:
            raise RenameError(f"nom cible interdit : {new_name!r}")
        resolved = _unique_name(path, new_name, used, collision)
        if resolved is None:
            continue
        rows.append((path, resolved))
    return rows


def apply(rows: list[tuple[Path, str]], *, record_undo: bool = True, overwrite: bool = False) -> list[Path]:
    global _LAST_UNDO
    done: list[Path] = []
    temps: list[tuple[Path, Path, Path]] = []
    for src, new_name in rows:
        dest = src.with_name(new_name)
        if dest == src:
            continue
        tmp = src.with_name(f".kit-ren-{src.name}.tmp")
        n = 0
        while tmp.exists():
            n += 1
            tmp = src.with_name(f".kit-ren-{n}-{src.name}.tmp")
        temps.append((src, tmp, dest))
    mapping: list[tuple[Path, Path]] = []
    try:
        for src, tmp, _dest in temps:
            src.rename(tmp)
        for src, tmp, dest in temps:
            if dest.exists():
                if not overwrite:
                    raise RenameError(f"existe déjà : {dest}")
                dest.unlink()
            tmp.rename(dest)
            done.append(dest)
            mapping.append((dest, src))
    except OSError as exc:
        raise RenameError(str(exc)) from exc
    if record_undo:
        _LAST_UNDO = mapping
        _save_undo(mapping)
    return done


def apply_copies(rows: list[tuple[Path, str]], dest_dir: Path, *, overwrite: bool = False) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    done: list[Path] = []
    try:
        for src, new_name in rows:
            dest = dest_dir / Path(new_name).name
            if dest.exists() and not overwrite:
                raise RenameError(f"existe déjà : {dest}")
            shutil.copy2(src, dest)
            done.append(dest)
    except OSError as exc:
        raise RenameError(str(exc)) from exc
    return done


def undo_last() -> list[Path]:
    global _LAST_UNDO
    mapping = _load_undo()
    if not mapping:
        raise RenameError("rien à annuler")
    for current, _original in mapping:
        if not current.exists():
            raise RenameError(f"fichier disparu : {current}")
    rows = [(current, original.name) for current, original in mapping]
    _LAST_UNDO = []
    _save_undo([])
    return apply(rows, record_undo=False)


def last_undo_count() -> int:
    return len(_load_undo())


def _presets_path() -> Path:
    return _data_dir() / "rename-presets.json"


def load_presets() -> dict[str, dict[str, str]]:
    path = _presets_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def save_preset(name: str, data: dict[str, str]) -> None:
    presets = load_presets()
    presets[name.strip()] = {k: str(v) for k, v in data.items()}
    _presets_path().write_text(json.dumps(presets, indent=2) + "\n", encoding="utf-8")


def preview_from_csv(paths: list[Path], mapping: dict[str, str], **kwargs: object) -> list[tuple[Path, str]]:
    rows: list[tuple[Path, str]] = []
    for path in paths:
        target = mapping.get(path.name)
        if not target:
            continue
        rows.extend(preview([path], "", target, **kwargs))  # type: ignore[arg-type]
    return rows


def parse_rename_csv(text: str) -> dict[str, str]:
    import csv
    import io

    out: dict[str, str] = {}
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 2:
            continue
        old, new = row[0].strip(), row[1].strip()
        if old and new and old != "old":
            out[old] = new
    return out
