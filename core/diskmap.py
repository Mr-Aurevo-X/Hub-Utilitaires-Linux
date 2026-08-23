# SPDX-License-Identifier: GPL-3.0-or-later
"""Local folder size scan. No network, no deletes."""

from __future__ import annotations

import csv
import io
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from core.find import SKIP_DIRS

DISPLAY_CAP = 400


class DiskMapError(Exception):
    pass


@dataclass(frozen=True)
class DiskEntry:
    path: Path
    name: str
    is_dir: bool
    size: int
    percent: float


def human_size(n: int) -> str:
    value = float(max(0, int(n)))
    for unit in ("o", "Kio", "Mio", "Gio", "Tio"):
        if value < 1024.0 or unit == "Tio":
            if unit == "o":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(n)} o"


def _dir_size(root: Path, *, skip_known: bool, cancel: Event | None) -> int:
    total = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        if cancel is not None and cancel.is_set():
            break
        if skip_known:
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            if cancel is not None and cancel.is_set():
                break
            path = base / name
            if path.is_symlink():
                continue
            try:
                total += path.stat().st_size
            except OSError:
                continue
    return total


def scan_children(
    root: Path,
    *,
    skip_known: bool = True,
    cancel: Event | None = None,
    display_cap: int = DISPLAY_CAP,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[int, list[DiskEntry], int]:
    if root == Path("/"):
        raise DiskMapError("scan de / interdit — choisissez un dossier")
    if not root.is_dir():
        raise DiskMapError("dossier invalide")
    raw: list[tuple[Path, bool, int]] = []
    try:
        children = list(root.iterdir())
    except OSError as exc:
        raise DiskMapError(str(exc)) from exc
    total_kids = len(children)
    for index, child in enumerate(children, start=1):
        if on_progress is not None:
            on_progress(index, total_kids)
        if cancel is not None and cancel.is_set():
            break
        if child.is_symlink():
            continue
        if skip_known and child.is_dir() and child.name in SKIP_DIRS:
            continue
        try:
            if child.is_dir():
                size = _dir_size(child, skip_known=skip_known, cancel=cancel)
                raw.append((child, True, size))
            elif child.is_file():
                raw.append((child, False, child.stat().st_size))
        except OSError:
            continue
    raw.sort(key=lambda item: item[2], reverse=True)
    total = sum(item[2] for item in raw)
    hidden = max(0, len(raw) - display_cap)
    shown = raw[:display_cap]
    if hidden:
        rest = sum(item[2] for item in raw[display_cap:])
        shown.append((root / "(reste)", False, rest))
    entries: list[DiskEntry] = []
    for path, is_dir, size in shown:
        percent = (size / total * 100.0) if total else 0.0
        name = path.name if path.parent == root or path.name == "(reste)" else path.name
        if hidden and path.name == "(reste)":
            name = f"(reste ×{hidden})"
            is_dir = False
        entries.append(DiskEntry(path=path, name=name, is_dir=is_dir, size=size, percent=percent))
    return total, entries, hidden


def export_csv(entries: list[DiskEntry]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["path", "name", "is_dir", "bytes", "percent"])
    for entry in entries:
        writer.writerow(
            [
                str(entry.path),
                entry.name,
                int(entry.is_dir),
                entry.size,
                f"{entry.percent:.2f}",
            ]
        )
    return buf.getvalue()
