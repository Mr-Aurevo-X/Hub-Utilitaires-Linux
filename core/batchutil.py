# SPDX-License-Identifier: GPL-3.0-or-later
"""Local batch scans (duplicates, empties, stats). No deletes."""

from __future__ import annotations

import csv
import io
import os
import shutil
from collections import defaultdict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from core.find import SKIP_DIRS, PathHits, empty_dirs
from core.hashutil import checksums_manifest, file_hash

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


def _iter_files(root: Path, *, limit: int = 8000) -> PathHits:
    if not root.is_dir():
        raise BatchError("dossier invalide")
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        base = Path(dirpath)
        for name in filenames:
            if name.startswith("."):
                continue
            out.append(base / name)
            if len(out) >= limit:
                return PathHits(out, True, limit)
    return PathHits(out, False, limit)


def sha256_duplicates_paths(
    paths: list[Path],
    *,
    on_progress: ProgressFn | None = None,
) -> list[list[Path]]:
    groups: dict[str, list[Path]] = defaultdict(list)
    total = len(paths)
    for index, path in enumerate(paths, start=1):
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
) -> GroupHits:
    scanned = _iter_files(root, limit=limit)
    return GroupHits(
        sha256_duplicates_paths(scanned.paths, on_progress=on_progress),
        scanned.truncated,
        scanned.limit,
    )


def same_names(root: Path, *, limit: int = 8000) -> GroupHits:
    scanned = _iter_files(root, limit=limit)
    groups: dict[str, list[Path]] = defaultdict(list)
    for path in scanned.paths:
        groups[path.name.lower()].append(path)
    found = [sorted(items, key=lambda item: str(item)) for items in groups.values() if len(items) > 1]
    return GroupHits(found, scanned.truncated, scanned.limit)


def older_than(root: Path, days: float, *, limit: int = 8000) -> PathHits:
    scanned = _iter_files(root, limit=limit)
    cutoff = datetime.now(tz=timezone.utc).timestamp() - max(0.0, float(days)) * 86400
    hits: list[Path] = []
    for path in scanned.paths:
        try:
            if path.stat().st_mtime < cutoff:
                hits.append(path)
        except OSError:
            continue
    return PathHits(hits, scanned.truncated, scanned.limit)


def larger_than(root: Path, megabytes: float, *, limit: int = 8000) -> PathHits:
    scanned = _iter_files(root, limit=limit)
    threshold = max(0.0, float(megabytes)) * 1024 * 1024
    hits: list[Path] = []
    for path in scanned.paths:
        try:
            if path.stat().st_size >= threshold:
                hits.append(path)
        except OSError:
            continue
    return PathHits(hits, scanned.truncated, scanned.limit)


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


def move_copies(groups: list[list[Path]], dest_dir: Path) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for group in groups:
        if len(group) < 2:
            continue
        ordered = sorted(group, key=lambda item: (item.stat().st_mtime, str(item)))
        for extra in ordered[1:]:
            target = dest_dir / extra.name
            n = 2
            while target.exists():
                target = dest_dir / f"{extra.stem}_{n}{extra.suffix}"
                n += 1
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


def broken_symlinks(root: Path, *, limit: int = 8000) -> PathHits:
    if not root.is_dir():
        raise BatchError("dossier invalide")
    hits: list[Path] = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
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
