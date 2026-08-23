# SPDX-License-Identifier: GPL-3.0-or-later
"""Local filename / content search. No network."""

from __future__ import annotations

import csv
import fnmatch
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator

SKIP_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".cache",
        ".local",
        ".npm",
        ".cargo",
        "proc",
        "sys",
    }
)
_SKIP_DIRS = SKIP_DIRS
TEXT_EXT = frozenset(
    {
        ".txt",
        ".md",
        ".py",
        ".rs",
        ".js",
        ".ts",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".cfg",
        ".sh",
        ".css",
        ".html",
        ".xml",
        ".csv",
        ".log",
        ".desktop",
        ".c",
        ".h",
        ".cpp",
        ".go",
    }
)
_TEXT_EXT = TEXT_EXT
_MAX_FILE_BYTES = 2 * 1024 * 1024


class FindError(Exception):
    pass


@dataclass(frozen=True)
class PathHits:
    paths: list[Path]
    truncated: bool
    limit: int

    def __iter__(self):  # type: ignore[override]
        return iter(self.paths)

    def __len__(self) -> int:
        return len(self.paths)

    def __bool__(self) -> bool:
        return bool(self.paths)


def _iter_files(root: Path, *, include_hidden: bool = False) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            if not include_hidden and name.startswith("."):
                continue
            kept.append(name)
        dirnames[:] = kept
        base = Path(dirpath)
        for name in filenames:
            if not include_hidden and name.startswith("."):
                continue
            yield base / name


def _parse_extensions(raw: str | list[str] | None) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.replace(",", " ").split() if p.strip()]
    else:
        parts = [str(p).strip() for p in raw if str(p).strip()]
    if not parts:
        return None
    out: list[str] = []
    for part in parts:
        ext = part.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        out.append(ext)
    return out


def _parse_date(value: str | float | None) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    try:
        return float(text)
    except ValueError as exc:
        raise FindError(f"date invalide : {text}") from exc


def _passes(
    path: Path,
    *,
    extensions: list[str] | None,
    min_bytes: int | None,
    max_bytes: int | None,
    min_mtime: float | None,
    max_mtime: float | None,
) -> bool:
    try:
        st = path.stat()
    except OSError:
        return False
    if extensions is not None and path.suffix.lower() not in extensions:
        return False
    if min_bytes is not None and st.st_size < min_bytes:
        return False
    if max_bytes is not None and st.st_size > max_bytes:
        return False
    if min_mtime is not None and st.st_mtime < min_mtime:
        return False
    if max_mtime is not None and st.st_mtime > max_mtime + 86399:
        return False
    return True


def search_names(
    root: Path,
    pattern: str,
    *,
    limit: int = 400,
    extensions: str | list[str] | None = None,
    min_bytes: int | None = None,
    max_bytes: int | None = None,
    min_mtime: str | float | None = None,
    max_mtime: str | float | None = None,
    include_hidden: bool = False,
) -> PathHits:
    query = (pattern or "").strip()
    if not query:
        return PathHits([], False, limit)
    if not root.is_dir():
        return PathHits([], False, limit)
    exts = _parse_extensions(extensions)
    lo = _parse_date(min_mtime)
    hi = _parse_date(max_mtime)
    regex = None
    glob_pat = query
    if query.startswith("/") and query.endswith("/") and len(query) > 2:
        try:
            regex = re.compile(query[1:-1], re.IGNORECASE)
        except re.error:
            regex = None
    hits: list[Path] = []
    for path in _iter_files(root, include_hidden=include_hidden):
        if not _passes(
            path,
            extensions=exts,
            min_bytes=min_bytes,
            max_bytes=max_bytes,
            min_mtime=lo,
            max_mtime=hi,
        ):
            continue
        name = path.name
        ok = False
        if regex is not None:
            ok = bool(regex.search(name) or regex.search(str(path)))
        else:
            ok = fnmatch.fnmatch(name.lower(), f"*{glob_pat.lower()}*")
        if ok:
            hits.append(path)
            if len(hits) >= limit:
                return PathHits(hits, True, limit)
    return PathHits(hits, False, limit)


def search_content(
    root: Path,
    text: str,
    *,
    limit: int = 200,
    extensions: str | list[str] | None = None,
    min_bytes: int | None = None,
    max_bytes: int | None = None,
    min_mtime: str | float | None = None,
    max_mtime: str | float | None = None,
    include_hidden: bool = False,
) -> PathHits:
    needle = (text or "").strip()
    if not needle or not root.is_dir():
        return PathHits([], False, limit)
    exts = _parse_extensions(extensions)
    lo = _parse_date(min_mtime)
    hi = _parse_date(max_mtime)
    lowered = needle.lower()
    hits: list[Path] = []
    for path in _iter_files(root, include_hidden=include_hidden):
        if path.suffix.lower() not in _TEXT_EXT:
            continue
        if not _passes(
            path,
            extensions=exts,
            min_bytes=min_bytes,
            max_bytes=max_bytes,
            min_mtime=lo,
            max_mtime=hi,
        ):
            continue
        try:
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue
            blob = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in blob[:1024]:
            continue
        try:
            data = blob.decode("utf-8", errors="ignore")
        except Exception:
            continue
        if lowered in data.lower():
            hits.append(path)
            if len(hits) >= limit:
                return PathHits(hits, True, limit)
    return PathHits(hits, False, limit)


def empty_dirs(root: Path, *, limit: int = 400, include_hidden: bool = False) -> PathHits:
    if not root.is_dir():
        return PathHits([], False, limit)
    hits: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept: list[str] = []
        for name in dirnames:
            if name in SKIP_DIRS:
                continue
            if not include_hidden and name.startswith("."):
                continue
            kept.append(name)
        dirnames[:] = kept
        visible = [name for name in filenames if include_hidden or not name.startswith(".")]
        if not dirnames and not visible:
            hits.append(Path(dirpath))
            if len(hits) >= limit:
                return PathHits(hits, True, limit)
    return PathHits(hits, False, limit)


def list_files(root: Path, *, limit: int = 400, include_hidden: bool = False) -> PathHits:
    if not root.is_dir():
        return PathHits([], False, limit)
    hits: list[Path] = []
    for path in _iter_files(root, include_hidden=include_hidden):
        hits.append(path)
        if len(hits) >= limit:
            return PathHits(hits, True, limit)
    return PathHits(hits, False, limit)


def replace_preview(paths: list[Path], needle: str, replacement: str) -> list[tuple[Path, int]]:
    text = needle or ""
    if not text:
        raise FindError("texte à remplacer vide")
    rows: list[tuple[Path, int]] = []
    for path in paths:
        try:
            data = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        count = data.count(text)
        if count:
            rows.append((path, count))
    return rows


def replace_apply(
    paths: list[Path],
    needle: str,
    replacement: str,
    *,
    overwrite: bool = False,
) -> list[Path]:
    text = needle or ""
    if not text:
        raise FindError("texte à remplacer vide")
    done: list[Path] = []
    for path in paths:
        try:
            data = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise FindError(f"lecture impossible : {path}") from exc
        if text not in data:
            continue
        dest = path if overwrite else path.with_name(f"{path.stem}_kit{path.suffix}")
        dest.write_text(data.replace(text, replacement), encoding="utf-8")
        done.append(dest)
    return done


def export_paths(paths: list[Path], *, csv_mode: bool = False, json_mode: bool = False) -> str:
    if json_mode:
        payload = []
        for path in paths:
            try:
                st = path.stat()
                payload.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "bytes": st.st_size,
                        "mtime": st.st_mtime,
                    }
                )
            except OSError:
                payload.append({"path": str(path), "name": path.name})
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if csv_mode:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["path", "name", "bytes"])
        for path in paths:
            try:
                size = path.stat().st_size
            except OSError:
                size = ""
            writer.writerow([str(path), path.name, size])
        return buf.getvalue()
    return "\n".join(str(path) for path in paths) + ("\n" if paths else "")
