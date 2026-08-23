# SPDX-License-Identifier: GPL-3.0-or-later
"""Local file inspect / archive helpers. No network."""

from __future__ import annotations

import bz2
import gzip
import mimetypes
import os
import shutil
import stat
import subprocess
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_HEX_LIMIT = 64 * 1024

_MAGIC: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"PK\x03\x04", "application/zip", ".zip"),
    (b"\x7fELF", "application/x-elf", ".elf"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"RIFF", "application/octet-stream", ".riff"),
)


class FileUtilError(Exception):
    pass


def inspect(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileUtilError("fichier introuvable")
    st = path.stat()
    mime, _enc = mimetypes.guess_type(path.name)
    magic = detect_mime_magic(path)
    ext_mime = mime or "application/octet-stream"
    return {
        "path": str(path),
        "name": path.name,
        "mime": ext_mime,
        "magic_mime": magic.get("mime"),
        "magic_hint": magic.get("hint"),
        "mime_match": magic.get("match"),
        "size": st.st_size,
        "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "ctime": datetime.fromtimestamp(st.st_ctime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "atime": datetime.fromtimestamp(st.st_atime, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "inode": st.st_ino,
        "nlink": st.st_nlink,
        "mode": oct(st.st_mode & 0o777),
        "rwx": stat.filemode(st.st_mode),
        "chmod_suggest": f"chmod {oct(st.st_mode & 0o777)[-3:]}",
        "is_symlink": path.is_symlink(),
        "is_dir": path.is_dir(),
    }


def detect_mime_magic(path: Path, *, nbytes: int = 512) -> dict[str, object]:
    ext = path.suffix.lower()
    ext_mime, _ = mimetypes.guess_type(path.name)
    try:
        head = path.read_bytes()[: max(16, min(nbytes, 512))]
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    magic_mime = "application/octet-stream"
    hint = ""
    for prefix, mime, suffix in _MAGIC:
        if head.startswith(prefix):
            magic_mime = mime
            hint = suffix
            break
    if head.startswith(b"RIFF") and len(head) >= 12 and head[8:12] == b"WEBP":
        magic_mime = "image/webp"
        hint = ".webp"
    match = True
    if ext_mime and magic_mime != "application/octet-stream":
        match = ext_mime.split("/", 1)[0] == magic_mime.split("/", 1)[0] or ext == hint
    return {"mime": magic_mime, "hint": hint, "match": match, "extension": ext}


def tree_size(paths: list[Path]) -> dict[str, object]:
    total = 0
    files = 0
    for path in paths:
        if path.is_file():
            try:
                total += path.stat().st_size
                files += 1
            except OSError:
                continue
        elif path.is_dir():
            for root, _dirs, filenames in os.walk(path, followlinks=False):
                for name in filenames:
                    try:
                        total += (Path(root) / name).stat().st_size
                        files += 1
                    except OSError:
                        continue
    return {"bytes": total, "files": files}


def flatpak_info(app_id: str = "org.mraurevox.HubUtilitaires") -> str:
    from core import host

    exe = host.which("flatpak") or "flatpak"
    try:
        completed = subprocess.run(
            [exe, "info", app_id],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise FileUtilError(str(exc)) from exc
    out = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        raise FileUtilError(out or "flatpak info a échoué")
    return out


def inspect_text(path: Path) -> str:
    data = inspect(path)
    lines = [f"{key}: {data[key]}" for key in data]
    return "\n".join(lines)


def chmod_path(path: Path, mode: str) -> Path:
    text = (mode or "").strip()
    if not text:
        raise FileUtilError("mode vide")
    try:
        value = int(text, 8) if text.isdigit() else int(text, 0)
    except ValueError as exc:
        raise FileUtilError(f"mode invalide : {mode}") from exc
    if value < 0 or value > 0o777:
        raise FileUtilError("mode hors 000–777")
    path.chmod(value)
    return path


def hexdump_file(path: Path, *, limit: int = _HEX_LIMIT) -> str:
    cap = max(16, min(_HEX_LIMIT, int(limit)))
    try:
        data = path.read_bytes()[:cap]
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    lines: list[str] = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hexpart = " ".join(f"{byte:02x}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{offset:08x}  {hexpart:<48}  {ascii_part}")
    if path.stat().st_size > cap:
        lines.append(f"… {path.stat().st_size - cap} octets non affichés")
    return "\n".join(lines)


def first_diff(left: Path, right: Path) -> int | None:
    chunk = 64 * 1024
    offset = 0
    try:
        with left.open("rb") as a, right.open("rb") as b:
            while True:
                ca = a.read(chunk)
                cb = b.read(chunk)
                if not ca and not cb:
                    return None
                if ca != cb:
                    limit = max(len(ca), len(cb))
                    for i in range(limit):
                        ba = ca[i] if i < len(ca) else None
                        bb = cb[i] if i < len(cb) else None
                        if ba != bb:
                            return offset + i
                offset += len(ca)
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc


def guess_encoding(path: Path) -> str:
    try:
        raw = path.read_bytes()[:8192]
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be"
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "latin-1"


def line_count(path: Path) -> tuple[int, str]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    shebang = ""
    if data.startswith(b"#!"):
        shebang = data.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1), shebang


def touch_mtime(path: Path) -> Path:
    path.touch()
    return path


def create_symlink(target: Path, dest: Path) -> Path:
    if dest.is_symlink() or (dest.exists() and not (dest.is_file() and dest.stat().st_size == 0)):
        raise FileUtilError(f"existe déjà : {dest}")
    if dest.exists():
        dest.unlink()
    dest.symlink_to(target)
    return dest


def relink_symlink(link: Path, new_target: Path) -> Path:
    if not link.is_symlink():
        raise FileUtilError("pas un lien symbolique")
    link.unlink()
    link.symlink_to(new_target)
    return link


def rewrite_text(path: Path, dest: Path, *, mode: str) -> Path:
    key = (mode or "").lower()
    try:
        data = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise FileUtilError(str(exc)) from exc
    if key == "lf":
        out = data.replace("\r\n", "\n").replace("\r", "\n")
    elif key == "utf8":
        out = data
    elif key == "rstrip":
        out = "\n".join(line.rstrip() for line in data.splitlines())
        if data.endswith("\n"):
            out += "\n"
    else:
        raise FileUtilError(f"réécriture inconnue : {mode}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    return dest


def split_file(src: Path, dest_dir: Path, chunk_mb: float) -> list[Path]:
    size = max(1, int(float(chunk_mb) * 1024 * 1024))
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    index = 1
    try:
        with src.open("rb") as handle:
            while True:
                chunk = handle.read(size)
                if not chunk:
                    break
                dest = dest_dir / f"{src.name}.part{index:03d}"
                dest.write_bytes(chunk)
                written.append(dest)
                index += 1
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    if not written:
        raise FileUtilError("fichier vide")
    return written


def join_files(parts: list[Path], dest: Path) -> Path:
    if not parts:
        raise FileUtilError("aucune partie")
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with dest.open("wb") as out:
            for part in parts:
                out.write(part.read_bytes())
    except OSError as exc:
        raise FileUtilError(str(exc)) from exc
    return dest


def copy_to(src: Path, dest_dir: Path) -> Path:
    if not dest_dir.is_dir():
        dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        raise FileUtilError(f"existe déjà : {dest}")
    shutil.copy2(src, dest)
    return dest


def diff_archive_members(left: Path, right: Path) -> dict[str, list[str]]:
    only_a = set(list_archive(left))
    only_b = set(list_archive(right))
    return {
        "only_a": sorted(only_a - only_b),
        "only_b": sorted(only_b - only_a),
        "both": sorted(only_a & only_b),
    }


def list_archive(path: Path) -> list[str]:
    suffix = "".join(path.suffixes).lower()
    try:
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as zf:
                return zf.namelist()
        if tarfile.is_tarfile(path):
            with tarfile.open(path) as tf:
                return [name for name in tf.getnames() if name]
        if suffix.endswith(".gz") and not suffix.endswith(".tar.gz"):
            with gzip.open(path, "rb") as handle:
                size = len(handle.read())
            return [f"{path.stem} ({size} octets décompressés)"]
        if suffix.endswith(".bz2") and not suffix.endswith(".tar.bz2"):
            with bz2.open(path, "rb") as handle:
                size = len(handle.read())
            return [f"{path.stem} ({size} octets décompressés)"]
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise FileUtilError(str(exc)) from exc
    raise FileUtilError("archive non reconnue")


def create_zip(files: list[Path], dest: Path) -> Path:
    if not files:
        raise FileUtilError("aucun fichier")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, arcname=path.name)
    return dest


def create_tar_gz(files: list[Path], dest: Path) -> Path:
    if not files:
        raise FileUtilError("aucun fichier")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(dest, "w:gz") as tf:
        for path in files:
            tf.add(path, arcname=path.name)
    return dest


def extract_archive(src: Path, dest_dir: Path, *, name_filter: str = "") -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    needle = (name_filter or "").strip().lower()
    written: list[Path] = []

    def wanted(name: str) -> bool:
        return not needle or needle in name.lower()

    try:
        if zipfile.is_zipfile(src):
            with zipfile.ZipFile(src) as zf:
                for info in zf.infolist():
                    if info.is_dir() or not wanted(info.filename):
                        continue
                    target = _safe_extract_path(dest_dir, info.filename)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(info))
                    written.append(target)
            return written
        if tarfile.is_tarfile(src):
            with tarfile.open(src) as tf:
                for member in tf.getmembers():
                    if not member.isfile() or not wanted(member.name):
                        continue
                    target = _safe_extract_path(dest_dir, member.name)
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(extracted.read())
                    written.append(target)
            return written
        suffix = "".join(src.suffixes).lower()
        if suffix.endswith(".gz"):
            target = dest_dir / src.stem
            target.write_bytes(gzip.decompress(src.read_bytes()))
            return [target]
        if suffix.endswith(".bz2"):
            target = dest_dir / src.stem
            target.write_bytes(bz2.decompress(src.read_bytes()))
            return [target]
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise FileUtilError(str(exc)) from exc
    raise FileUtilError("archive non reconnue")


def _safe_extract_path(dest_dir: Path, name: str) -> Path:
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise FileUtilError(f"chemin d’archive interdit : {name}")
    target = (dest_dir / rel).resolve()
    root = dest_dir.resolve()
    if root not in target.parents and target != root:
        raise FileUtilError(f"chemin d’archive interdit : {name}")
    return target
