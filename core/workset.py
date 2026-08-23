# SPDX-License-Identifier: GPL-3.0-or-later
"""Session workset: one folder + selected paths. RAM only for paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SendTarget = Literal["rename", "lots", "hash", "resize", "pdf", "file", "textdiff"]
SEND_TARGETS: tuple[SendTarget, ...] = ("rename", "lots", "hash", "resize", "pdf", "file", "textdiff")


@dataclass(frozen=True)
class Workset:
    folder: Path
    paths: list[Path]


def from_paths(folder: Path, paths: list[Path]) -> Workset:
    return Workset(folder=folder, paths=list(paths))


def existing_only(item: Workset) -> Workset:
    return Workset(folder=item.folder, paths=[path for path in item.paths if path.exists()])


def coerce_send_target(value: object) -> SendTarget:
    key = str(value or "").strip()
    if key not in SEND_TARGETS:
        raise ValueError(f"cible inconnue : {key}")
    return key  # type: ignore[return-value]
