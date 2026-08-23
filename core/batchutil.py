# SPDX-License-Identifier: GPL-3.0-or-later
"""Local batch scans (duplicates, empties, stats). No deletes."""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from urllib.parse import unquote, urlparse

from core import fileutil, resize
from core.find import SKIP_DIRS, TEXT_EXT, PathHits, empty_dirs
from core.hashutil import checksums_manifest, file_hash

_DOC_LINK_EXTS = frozenset({".md", ".markdown", ".html", ".htm", ".rst"})
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
_HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_RST_LINK = re.compile(r"\.\.\s+(?:image|include|figure)::\s+(\S+)")
_SKIP_HREF_PREFIX = ("http://", "https://", "ftp://", "mailto:", "data:", "javascript:", "#")
_EOL_TEXT_EXT = TEXT_EXT | {".htm", ".rst", ".markdown"}

ProgressFn = Callable[[int, int], None]


class BatchError(Exception):
    pass


@dataclass(frozen=True)
class GroupHits:
    groups: list[list[Path]]
    truncated: bool
    limit: int

    def __iter__(self) -> Iterator[list[Path]]:
        return iter(self.groups)

    def __len__(self) -> int:
        return len(self.groups)

    def __getitem__(self, index: int) -> list[Path]:
        return self.groups[index]


def _cancelled(cancel: Event | None) -> bool:
    return cancel is not None and cancel.is_set()


def _iter_files(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    if not root.is_dir():
        raise BatchError("dossier invalide")
    if _cancelled(cancel):
        return PathHits([], True, limit)
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if _cancelled(cancel):
            return PathHits(out, True, limit)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        base = Path(dirpath)
        for name in filenames:
            if name.startswith("."):
                continue
            out.append(base / name)
            if len(out) >= limit or _cancelled(cancel):
                return PathHits(out, True, limit)
    return PathHits(out, False, limit)


def sha256_duplicates_paths(
    paths: list[Path],
    *,
    on_progress: ProgressFn | None = None,
    cancel: Event | None = None,
) -> list[list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    total = len(paths)
    for index, path in enumerate(paths, start=1):
        if _cancelled(cancel):
            break
        if on_progress is not None:
            on_progress(index, total)
        try:
            digest = file_hash(path, "sha256")
        except OSError:
            continue
        groups[digest].append(path)
    return [sorted(items, key=lambda item: (item.stat().st_mtime, str(item))) for items in groups.values() if len(items) > 1]


def sha256_duplicates(
    root: Path,
    *,
    limit: int = 8000,
    on_progress: ProgressFn | None = None,
    cancel: Event | None = None,
) -> GroupHits:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    return GroupHits(
        sha256_duplicates_paths(scanned.paths, on_progress=on_progress, cancel=cancel),
        scanned.truncated or _cancelled(cancel),
        scanned.limit,
    )


def same_names(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> GroupHits:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in scanned.paths:
        groups[path.name.lower()].append(path)
    found = [sorted(items, key=lambda item: str(item)) for items in groups.values() if len(items) > 1]
    return GroupHits(found, scanned.truncated or _cancelled(cancel), scanned.limit)


def older_than(root: Path, days: float, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    cutoff = datetime.now(tz=timezone.utc).timestamp() - max(0.0, float(days)) * 86400
    hits: list[Path] = []
    for path in scanned.paths:
        try:
            if path.stat().st_mtime < cutoff:
                hits.append(path)
        except OSError:
            continue
    return PathHits(hits, scanned.truncated or _cancelled(cancel), scanned.limit)


def larger_than(root: Path, megabytes: float, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    threshold = max(0.0, float(megabytes)) * 1024 * 1024
    hits: list[Path] = []
    for path in scanned.paths:
        try:
            if path.stat().st_size >= threshold:
                hits.append(path)
        except OSError:
            continue
    return PathHits(hits, scanned.truncated or _cancelled(cancel), scanned.limit)


def empty_files(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    hits: list[Path] = []
    for path in scanned.paths:
        if _cancelled(cancel):
            return PathHits(hits, True, limit)
        try:
            if path.is_file() and not path.is_symlink() and path.stat().st_size == 0:
                hits.append(path)
        except OSError:
            continue
    return PathHits(hits, scanned.truncated or _cancelled(cancel), scanned.limit)


def folder_stats(root: Path, *, limit: int = 8000) -> dict[str, object]:
    files = _iter_files(root, limit=limit).paths
    dirs = 0
    for dirpath, dirnames, _filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        dirs += 1
        if dirs > limit:
            break
    total = 0
    ext_sizes: dict[str, int] = defaultdict(int)
    dir_sizes: dict[str, int] = defaultdict(int)
    for path in files:
        try:
            size = path.stat().st_size
        except OSError:
            continue
        total += size
        ext = path.suffix.lower() or "(none)"
        ext_sizes[ext] += size
        try:
            parent = str(path.parent.relative_to(root))
        except ValueError:
            parent = str(path.parent)
        dir_sizes[parent] += size
    top_ext = sorted(ext_sizes.items(), key=lambda item: item[1], reverse=True)[:8]
    top_dirs = sorted(dir_sizes.items(), key=lambda item: item[1], reverse=True)[:8]
    return {
        "files": len(files),
        "dirs": dirs,
        "bytes": total,
        "top_ext": top_ext,
        "top_dirs": top_dirs,
    }


def stats_text(root: Path) -> str:
    data = folder_stats(root)
    lines = [
        f"fichiers: {data['files']}",
        f"dossiers: {data['dirs']}",
        f"octets: {data['bytes']}",
        "extensions:",
    ]
    for ext, size in data["top_ext"]:
        lines.append(f"  {ext} {size}")
    lines.append("dossiers:")
    for name, size in data["top_dirs"]:
        lines.append(f"  {name or '.'} {size}")
    return "\n".join(lines)


def preview_move_copies(groups: list[list[Path]], dest_dir: Path) -> list[tuple[Path, Path]]:
    planned: list[tuple[Path, Path]] = []
    reserved: set[Path] = set()
    for group in groups:
        if len(group) < 2:
            continue
        try:
            ordered = sorted(group, key=lambda item: (item.stat().st_mtime, str(item)))
        except OSError:
            continue
        for extra in ordered[1:]:
            target = dest_dir / extra.name
            n = 2
            while target.exists() or target in reserved:
                target = dest_dir / f"{extra.stem}_{n}{extra.suffix}"
                n += 1
            reserved.add(target)
            planned.append((extra, target))
    return planned


def move_copies(groups: list[list[Path]], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for extra, target in preview_move_copies(groups, dest_dir):
        shutil.move(str(extra), str(target))
        moved.append(target)
    return moved


def export_paths(paths: list[Path], *, csv_mode: bool = False) -> str:
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


def empty_folders(root: Path) -> PathHits:
    return empty_dirs(root)


def broken_symlinks(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    if not root.is_dir():
        raise BatchError("dossier invalide")
    if _cancelled(cancel):
        return PathHits([], True, limit)
    hits: list[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if _cancelled(cancel):
            return PathHits(hits, True, limit)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        base = Path(dirpath)
        for name in list(dirnames) + list(filenames):
            path = base / name
            if not path.is_symlink():
                continue
            try:
                target = path.readlink()
                resolved = path.resolve(strict=False)
                if not resolved.exists():
                    hits.append(path)
                    if len(hits) >= limit:
                        truncated = True
                        return PathHits(hits, truncated, limit)
            except OSError:
                hits.append(path)
                if len(hits) >= limit:
                    truncated = True
                    return PathHits(hits, truncated, limit)
    return PathHits(hits, truncated, limit)


def trash_peek() -> list[dict[str, object]]:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    trash_files = data_home / "Trash" / "files"
    trash_info = data_home / "Trash" / "info"
    if not trash_files.is_dir():
        return []
    rows: list[dict[str, object]] = []
    for path in sorted(trash_files.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() and not path.is_symlink():
            continue
        deleted = ""
        info_path = trash_info / f"{path.name}.trashinfo"
        if info_path.is_file():
            try:
                for line in info_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("DeletionDate="):
                        deleted = line.split("=", 1)[1].strip()
                        break
            except OSError:
                pass
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        rows.append({"name": path.name, "bytes": size, "deleted": deleted, "path": str(path)})
    return rows


def trash_peek_text() -> str:
    lines = ["name\tbytes\tdeleted"]
    for row in trash_peek():
        lines.append(f"{row['name']}\t{row['bytes']}\t{row['deleted']}")
    return "\n".join(lines) + ("\n" if lines else "")


def write_manifest(root: Path, *, on_progress: ProgressFn | None = None) -> str:
    return checksums_manifest(root, on_progress=on_progress)


def _hrefs_from_text(text: str, suffix: str) -> list[str]:
    found = list(_MD_LINK.findall(text))
    if suffix in {".html", ".htm"}:
        found.extend(_HTML_LINK.findall(text))
    if suffix == ".rst":
        found.extend(_RST_LINK.findall(text))
    return found


def _resolve_local_href(source: Path, href: str) -> Path | None:
    raw = (href or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    if lower.startswith(_SKIP_HREF_PREFIX):
        return None
    raw = raw.split("#", 1)[0].split("?", 1)[0].strip()
    if not raw or raw.lower().startswith(_SKIP_HREF_PREFIX):
        return None
    if lower.startswith("file:"):
        parsed = urlparse(raw)
        path_text = unquote(parsed.path or "")
        if not path_text:
            return None
        return Path(path_text)
    return (source.parent / raw).resolve()


def _iter_broken_doc_rows(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> list[tuple[Path, str, Path]]:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    rows: list[tuple[Path, str, Path]] = []
    for path in scanned.paths:
        if path.suffix.lower() not in _DOC_LINK_EXTS:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for href in _hrefs_from_text(text, path.suffix.lower()):
            resolved = _resolve_local_href(path, href)
            if resolved is None:
                continue
            try:
                missing = not resolved.exists()
            except OSError:
                missing = True
            if missing:
                rows.append((path, href, resolved))
    return rows


def broken_doc_links(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> PathHits:
    rows = _iter_broken_doc_rows(root, limit=limit, cancel=cancel)
    seen: list[Path] = []
    for source, _href, _resolved in rows:
        if source not in seen:
            seen.append(source)
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    return PathHits(seen, scanned.truncated or _cancelled(cancel), scanned.limit)


def broken_doc_links_text(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> str:
    lines = [f"{source}\t{href}" for source, href, _resolved in _iter_broken_doc_rows(root, limit=limit, cancel=cancel)]
    return "\n".join(lines) + ("\n" if lines else "")


def _eol_kind(data: bytes) -> str:
    crlf = data.count(b"\r\n")
    lf_only = data.count(b"\n") - crlf
    cr_only = data.count(b"\r") - crlf
    kinds: list[str] = []
    if lf_only:
        kinds.append("lf")
    if crlf:
        kinds.append("crlf")
    if cr_only:
        kinds.append("cr")
    if len(kinds) > 1:
        return "mixed"
    return kinds[0] if kinds else "lf"


def eol_audit(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> list[dict[str, str]]:
    scanned = _iter_files(root, limit=limit, cancel=cancel)
    rows: list[dict[str, str]] = []
    for path in scanned.paths:
        if path.suffix.lower() not in _EOL_TEXT_EXT:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:8192]:
            continue
        try:
            encoding = fileutil.guess_encoding(path)
        except fileutil.FileUtilError:
            encoding = "unknown"
        rows.append({"path": str(path), "endings": _eol_kind(data), "encoding": encoding})
    return rows


def eol_audit_text(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> str:
    lines = ["path\tendings\tencoding"]
    for row in eol_audit(root, limit=limit, cancel=cancel):
        lines.append(f"{row['path']}\t{row['endings']}\t{row['encoding']}")
    return "\n".join(lines) + "\n"


def near_duplicate_images(root: Path, *, limit: int = 8000, cancel: Event | None = None) -> GroupHits:
    images = resize.list_images(root, limit=limit)
    groups: dict[tuple[int, int, int], list[Path]] = defaultdict(list)
    for path in images:
        if _cancelled(cancel):
            break
        try:
            info = resize.image_info(path)
            key = (int(info["width"]), int(info["height"]), int(info["bytes"]))
        except (OSError, TypeError, ValueError, resize.ResizeError):
            continue
        groups[key].append(path)
    found = [sorted(items, key=lambda item: str(item)) for items in groups.values() if len(items) > 1]
    return GroupHits(found, len(images) >= limit or _cancelled(cancel), limit)
