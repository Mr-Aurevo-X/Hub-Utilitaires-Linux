# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

try:
    from PIL import ExifTags, Image, ImageDraw, ImageEnhance, ImageOps
except ImportError:  # pragma: no cover
    ExifTags = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]
    ImageDraw = None  # type: ignore[assignment]
    ImageEnhance = None  # type: ignore[assignment]
    ImageOps = None  # type: ignore[assignment]


class ResizeError(Exception):
    pass


_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
    ".bmp": "BMP",
}
IMAGE_EXTS = frozenset(_FORMATS)


def _require_pillow() -> None:
    if Image is None:
        raise ResizeError("Pillow n’est pas installé (python-pillow / python3-pil).")


def _save_format(path: Path) -> str:
    fmt = _FORMATS.get(path.suffix.lower())
    if fmt is None:
        raise ResizeError(f"format non géré : {path.suffix}")
    return fmt


def image_info(path: Path) -> dict[str, object]:
    _require_pillow()
    with Image.open(path) as img:
        dpi = img.info.get("dpi")
        return {
            "width": img.size[0],
            "height": img.size[1],
            "mode": img.mode,
            "format": img.format or "",
            "bytes": path.stat().st_size,
            "dpi": dpi,
        }


def resize_image(src: Path, dest: Path, *, max_width: int, quality: int = 85) -> Path:
    return convert_image(src, dest, max_width=max_width, quality=quality, strip_exif=False)


def convert_image(
    src: Path,
    dest: Path,
    *,
    max_width: int | None = None,
    max_height: int | None = None,
    scale_percent: float | None = None,
    keep_ratio: bool = True,
    quality: int = 85,
    strip_exif: bool = False,
    rotate: int = 0,
    flip_h: bool = False,
    flip_v: bool = False,
    grayscale: bool = False,
    invert: bool = False,
    pixelate: int = 0,
    brightness: int = 0,
    watermark: str = "",
    watermark_corner: str = "se",
    max_side: int | None = None,
) -> Path:
    _require_pillow()
    quality = max(40, min(95, int(quality)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    fmt = _save_format(dest)
    with Image.open(src) as img:
        work = img
        if fmt in {"JPEG", "WEBP", "BMP"} and work.mode not in {"RGB", "L"}:
            work = work.convert("RGB")
        elif work.mode == "P":
            work = work.convert("RGBA")
        if rotate and rotate % 90 == 0:
            work = work.rotate(int(rotate), expand=True)
        if flip_h and ImageOps is not None:
            work = ImageOps.mirror(work)
        if flip_v and ImageOps is not None:
            work = ImageOps.flip(work)
        if scale_percent is not None and scale_percent > 0:
            width, height = work.size
            ratio = float(scale_percent) / 100.0
            work = work.resize((max(1, int(width * ratio)), max(1, int(height * ratio))))
        if max_side is not None and max_side >= 16:
            side_w, side_h = work.size
            if max(side_w, side_h) > max_side:
                work.thumbnail((max_side, max_side))
        width, height = work.size
        target_w, target_h = width, height
        if max_width is not None and max_width >= 16:
            target_w = min(target_w, max_width)
        if max_height is not None and max_height >= 16:
            target_h = min(target_h, max_height)
        if (target_w, target_h) != (width, height):
            if keep_ratio:
                work.thumbnail((target_w, target_h))
            else:
                work = work.resize((target_w, target_h))
        if grayscale:
            work = work.convert("L")
            if fmt in {"JPEG", "WEBP", "BMP"}:
                work = work.convert("RGB")
        if invert and ImageOps is not None:
            if work.mode not in {"RGB", "L"}:
                work = work.convert("RGB")
            work = ImageOps.invert(work)
        if pixelate >= 2:
            w, h = work.size
            small = work.resize((max(1, w // pixelate), max(1, h // pixelate)))
            work = small.resize((w, h), Image.Resampling.NEAREST if hasattr(Image, "Resampling") else 0)
        if brightness and ImageEnhance is not None:
            factor = max(0.1, min(3.0, 1.0 + (int(brightness) / 100.0)))
            work = ImageEnhance.Brightness(work).enhance(factor)
        mark = (watermark or "").strip()
        if mark and ImageDraw is not None:
            if work.mode not in {"RGB", "RGBA"}:
                work = work.convert("RGB")
            work = work.copy()
            draw = ImageDraw.Draw(work)
            bbox = draw.textbbox((0, 0), mark)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pad = 8
            w, h = work.size
            corner = (watermark_corner or "se").lower()
            if corner == "nw":
                xy = (pad, pad)
            elif corner == "ne":
                xy = (max(pad, w - tw - pad), pad)
            elif corner == "sw":
                xy = (pad, max(pad, h - th - pad))
            else:
                xy = (max(pad, w - tw - pad), max(pad, h - th - pad))
            draw.text(xy, mark, fill=(255, 255, 255))
        save_kw: dict[str, object] = {}
        if fmt in {"JPEG", "WEBP"}:
            save_kw["quality"] = quality
        if fmt == "JPEG":
            save_kw["optimize"] = True
            if strip_exif:
                save_kw["exif"] = b""
        if strip_exif:
            work = work.copy()
            work.info.pop("exif", None)
        work.save(dest, fmt, **save_kw)
    return dest


def exif_text(path: Path) -> str:
    _require_pillow()
    with Image.open(path) as img:
        exif = img.getexif()
        if not exif:
            return ""
        tags = getattr(ExifTags, "TAGS", {}) if ExifTags is not None else {}
        lines: list[str] = []
        for key, value in exif.items():
            name = tags.get(key, str(key))
            text = str(value)
            if len(text) > 200:
                text = text[:197] + "…"
            lines.append(f"{name}: {text}")
        return "\n".join(lines)


def list_images(root: Path, *, limit: int = 4000) -> list[Path]:
    if not root.is_dir():
        raise ResizeError("dossier invalide")
    from core.find import SKIP_DIRS

    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and not name.startswith(".")]
        for name in sorted(filenames):
            if name.startswith("."):
                continue
            path = Path(dirpath) / name
            if path.suffix.lower() not in IMAGE_EXTS:
                continue
            found.append(path)
            if len(found) >= max(1, int(limit)):
                return found
    return found


def batch_convert(
    files: list[Path],
    dest_dir: Path,
    *,
    suffix: str = "",
    on_progress: Callable[[int, int], None] | None = None,
    **kwargs: object,
) -> list[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    total = len(files)
    for index, src in enumerate(files, 1):
        ext = suffix if suffix else src.suffix
        if ext and not str(ext).startswith("."):
            ext = f".{ext}"
        dest = dest_dir / f"{src.stem}{ext or src.suffix}"
        convert_image(src, dest, **kwargs)  # type: ignore[arg-type]
        out.append(dest)
        if on_progress is not None:
            on_progress(index, total)
    return out


def export_icons(src: Path, dest_dir: Path, sizes: tuple[int, ...] = (16, 32, 48, 128)) -> list[Path]:
    _require_pillow()
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with Image.open(src) as img:
        work = img.convert("RGBA")
        for size in sizes:
            side = max(16, min(256, int(size)))
            copy = work.copy()
            copy.thumbnail((side, side))
            dest = dest_dir / f"{src.stem}-{side}.png"
            copy.save(dest, "PNG")
            written.append(dest)
    return written


def auto_rotate_exif(src: Path, dest: Path) -> Path:
    _require_pillow()
    if ImageOps is None:
        raise ResizeError("Pillow incomplet")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        work = ImageOps.exif_transpose(img)
        work.save(dest, _save_format(dest))
    return dest


def compare_images(left: Path, right: Path) -> str:
    from core.hashutil import file_hash

    li = image_info(left)
    ri = image_info(right)
    same = file_hash(left, "sha256") == file_hash(right, "sha256")
    return (
        f"left: {left.name} {li['width']}x{li['height']} {li['bytes']}o\n"
        f"right: {right.name} {ri['width']}x{ri['height']} {ri['bytes']}o\n"
        f"identical: {same}"
    )


def export_icons(src: Path, dest_dir: Path, sizes: tuple[int, ...] = (16, 32, 48, 128)) -> list[Path]:
    _require_pillow()
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with Image.open(src) as img:
        work = img.convert("RGBA")
        for size in sizes:
            side = max(16, min(256, int(size)))
            copy = work.copy()
            copy.thumbnail((side, side))
            dest = dest_dir / f"{src.stem}-{side}.png"
            copy.save(dest, "PNG")
            written.append(dest)
    return written


def auto_rotate_exif(src: Path, dest: Path) -> Path:
    _require_pillow()
    if ImageOps is None:
        raise ResizeError("Pillow incomplet")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        work = ImageOps.exif_transpose(img)
        work.save(dest, _save_format(dest))
    return dest


def compare_images(left: Path, right: Path) -> str:
    from core.hashutil import file_hash

    li = image_info(left)
    ri = image_info(right)
    same = file_hash(left, "sha256") == file_hash(right, "sha256")
    return (
        f"left: {left.name} {li['width']}x{li['height']} {li['bytes']}o\n"
        f"right: {right.name} {ri['width']}x{ri['height']} {ri['bytes']}o\n"
        f"identical: {same}"
    )
