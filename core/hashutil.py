# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import hashlib
import hmac
import os
import zlib
from collections.abc import Callable
from pathlib import Path

from core.find import SKIP_DIRS

_CHUNK = 1024 * 1024
ALGOS = ("sha256", "sha512", "blake2b", "md5", "sha1", "crc32")
LEGACY = frozenset({"md5", "sha1"})


def _algo_name(algo: str) -> str:
    name = algo.lower().replace("-", "")
    if name in {"blake2", "blake2b"}:
        return "blake2b"
    if name not in ALGOS:
        raise ValueError(f"algo inconnu : {algo}")
    return name


def file_hash(path: Path, algo: str = "sha256") -> str:
    name = _algo_name(algo)
    if name == "crc32":
        digest = 0
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(_CHUNK)
                if not chunk:
                    break
                digest = zlib.crc32(chunk, digest)
        return f"{digest & 0xFFFFFFFF:08x}"
    hasher = hashlib.new(name)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def file_hmac(path: Path, key: str, algo: str = "sha256") -> str:
    name = _algo_name(algo)
    if name == "crc32":
        raise ValueError("HMAC indisponible pour CRC32")
    digest = hmac.new(key.encode("utf-8"), digestmod=name)
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def matches(path: Path, expected: str, algo: str = "sha256") -> bool:
    want = "".join((expected or "").split()).lower()
    if not want:
        return False
    return file_hash(path, algo) == want


def compare_files(left: Path, right: Path, algo: str = "sha256") -> tuple[str, str, bool]:
    ha = file_hash(left, algo)
    hb = file_hash(right, algo)
    return ha, hb, ha == hb


def checksums_manifest(
    root: Path,
    *,
    algo: str = "sha256",
    limit: int = 4000,
    on_progress: Callable[[int, int], None] | None = None,
) -> str:
    if not root.is_dir():
        raise ValueError("dossier invalide")
    lines: list[str] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        base = Path(dirpath)
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = base / name
            try:
                digest = file_hash(path, algo)
            except OSError:
                continue
            rel = path.relative_to(root).as_posix()
            lines.append(f"{digest}  {rel}")
            count += 1
            if on_progress is not None:
                on_progress(count, limit)
            if count >= limit:
                break
        if count >= limit:
            break
    return "\n".join(lines) + ("\n" if lines else "")


def parse_manifest_line(line: str) -> tuple[str, str] | None:
    text = (line or "").strip()
    if not text or text.startswith("#"):
        return None
    parts = text.split(None, 1)
    if len(parts) != 2:
        return None
    digest, name = parts
    if name.startswith("*") or name.startswith(" "):
        name = name[1:]
    return digest.lower(), name


def matches_manifest_line(path: Path, line: str, *, algo: str = "sha256") -> bool:
    parsed = parse_manifest_line(line)
    if parsed is None:
        return False
    digest, _name = parsed
    return file_hash(path, algo) == digest


def verify_manifest(root: Path, manifest_text: str, *, algo: str = "sha256") -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in (manifest_text or "").splitlines():
        parsed = parse_manifest_line(line)
        if parsed is None:
            continue
        digest, rel = parsed
        path = root / rel
        if not path.is_file():
            rows.append((rel, "MANQUANT"))
            continue
        try:
            got = file_hash(path, algo)
        except OSError:
            rows.append((rel, "MANQUANT"))
            continue
        rows.append((rel, "OK" if got == digest.lower() else "DIFF"))
    return rows


def compare_directories(left: Path, right: Path, *, algo: str = "sha256") -> list[tuple[str, str]]:
    if not left.is_dir() or not right.is_dir():
        raise ValueError("deux dossiers requis")

    def index(root: Path) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
            base = Path(dirpath)
            for name in filenames:
                if name.startswith("."):
                    continue
                rel = (base / name).relative_to(root).as_posix()
                out[rel] = base / name
        return out

    left_map = index(left)
    right_map = index(right)
    keys = sorted(set(left_map) | set(right_map))
    rows: list[tuple[str, str]] = []
    for rel in keys:
        lp = left_map.get(rel)
        rp = right_map.get(rel)
        if lp is None:
            rows.append((rel, "EXTRA_RIGHT"))
            continue
        if rp is None:
            rows.append((rel, "MISSING_RIGHT"))
            continue
        try:
            same = file_hash(lp, algo) == file_hash(rp, algo)
        except OSError:
            rows.append((rel, "ERROR"))
            continue
        rows.append((rel, "OK" if same else "DIFF"))
    return rows


def sha256sums_file(root: Path, dest: Path, *, limit: int = 4000) -> Path:
    text = checksums_manifest(root, algo="sha256", limit=limit)
    dest.write_text(text, encoding="utf-8")
    return dest
