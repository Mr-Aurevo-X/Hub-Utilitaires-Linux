# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore[assignment]
    PdfWriter = None  # type: ignore[assignment]


class PdfError(Exception):
    pass


def _require() -> None:
    if PdfReader is None or PdfWriter is None:
        raise PdfError("pypdf n’est pas installé (python-pypdf / python3-pypdf).")


def _open_reader(src: Path, password: str = "") -> object:
    reader = PdfReader(str(src))
    if getattr(reader, "is_encrypted", False):
        if not password:
            raise PdfError("PDF chiffré : mot de passe requis")
        try:
            ok = reader.decrypt(password)
        except Exception as exc:  # noqa: BLE001
            raise PdfError(str(exc)) from exc
        if ok == 0:
            raise PdfError("mot de passe PDF incorrect")
    return reader


def parse_ranges(spec: str, page_count: int) -> list[int]:
    """1-based ranges like '1-3,5,8-10' → 0-based unique indexes in order."""
    text = (spec or "").replace(" ", "")
    if not text:
        raise PdfError("plages vides")
    if page_count < 1:
        raise PdfError("PDF vide")
    out: list[int] = []
    seen: set[int] = set()
    for chunk in text.split(","):
        if not chunk:
            continue
        if "-" in chunk:
            start_s, end_s = chunk.split("-", 1)
            try:
                start, end = int(start_s), int(end_s)
            except ValueError as exc:
                raise PdfError(f"plage invalide : {chunk}") from exc
            if start > end:
                start, end = end, start
            for page in range(start, end + 1):
                idx = page - 1
                if idx < 0 or idx >= page_count:
                    raise PdfError(f"page hors limites : {page}")
                if idx not in seen:
                    seen.add(idx)
                    out.append(idx)
        else:
            try:
                page = int(chunk)
            except ValueError as exc:
                raise PdfError(f"page invalide : {chunk}") from exc
            idx = page - 1
            if idx < 0 or idx >= page_count:
                raise PdfError(f"page hors limites : {page}")
            if idx not in seen:
                seen.add(idx)
                out.append(idx)
    if not out:
        raise PdfError("aucune page sélectionnée")
    return out


def info(src: Path, password: str = "") -> dict[str, object]:
    _require()
    try:
        reader = _open_reader(src, password)
        meta = getattr(reader, "metadata", None)
        title = author = created = modified = ""
        if meta is not None:
            title = str(getattr(meta, "title", None) or meta.get("/Title") or "")
            author = str(getattr(meta, "author", None) or meta.get("/Author") or "")
            created = str(getattr(meta, "creation_date", None) or meta.get("/CreationDate") or "")
            modified = str(getattr(meta, "modification_date", None) or meta.get("/ModDate") or "")
        return {
            "pages": len(reader.pages),
            "title": title,
            "author": author,
            "created": created,
            "modified": modified,
            "encrypted": bool(getattr(PdfReader(str(src)), "is_encrypted", False)),
        }
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc


def merge(paths: list[Path], dest: Path, *, order: list[int] | None = None) -> Path:
    _require()
    if len(paths) < 1:
        raise PdfError("aucun PDF")
    sequence = list(paths)
    if order is not None:
        try:
            sequence = [paths[i] for i in order]
        except IndexError as exc:
            raise PdfError("ordre de fusion invalide") from exc
    writer = PdfWriter()
    try:
        for path in sequence:
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def extract(src: Path, dest: Path, ranges: str, *, password: str = "") -> Path:
    _require()
    try:
        reader = _open_reader(src, password)
        indexes = parse_ranges(ranges, len(reader.pages))
        writer = PdfWriter()
        for idx in indexes:
            writer.add_page(reader.pages[idx])
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def split_pages(src: Path, dest_dir: Path, *, password: str = "") -> list[Path]:
    _require()
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        reader = _open_reader(src, password)
        for index, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            dest = dest_dir / f"{src.stem}-p{index:03d}.pdf"
            with dest.open("wb") as handle:
                writer.write(handle)
            written.append(dest)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    if not written:
        raise PdfError("PDF vide")
    return written


def insert_blank(src: Path, dest: Path, index: int, *, password: str = "") -> Path:
    _require()
    try:
        reader = _open_reader(src, password)
        count = len(reader.pages)
        pos = max(0, min(int(index), count))
        writer = PdfWriter()
        for i, page in enumerate(reader.pages):
            if i == pos:
                writer.add_blank_page(width=72, height=72)
            writer.add_page(page)
        if pos == count:
            writer.add_blank_page(width=72, height=72)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def strip_metadata(src: Path, dest: Path, *, password: str = "") -> Path:
    _require()
    try:
        reader = _open_reader(src, password)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        if hasattr(writer, "add_metadata"):
            writer.add_metadata({})
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def encrypt(src: Path, dest: Path, password: str) -> Path:
    _require()
    secret = (password or "").strip()
    if not secret:
        raise PdfError("mot de passe vide")
    try:
        reader = PdfReader(str(src))
        if getattr(reader, "is_encrypted", False):
            raise PdfError("déjà chiffré")
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        try:
            writer.encrypt(secret, algorithm="AES-256")
        except TypeError:
            writer.encrypt(secret)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def decrypt(src: Path, dest: Path, password: str) -> Path:
    _require()
    secret = (password or "").strip()
    if not secret:
        raise PdfError("mot de passe vide")
    try:
        reader = _open_reader(src, secret)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def rotate(src: Path, dest: Path, degrees: int = 90, *, password: str = "") -> Path:
    _require()
    if degrees % 90 != 0:
        raise PdfError("rotation : 90 / 180 / 270")
    try:
        reader = _open_reader(src, password)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page.rotate(degrees))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as handle:
            writer.write(handle)
    except PdfError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PdfError(str(exc)) from exc
    return dest


def reorder_pages(src: Path, dest: Path, order: list[int], *, password: str = "") -> Path:
    _require()
    reader = _open_reader(src, password)
    pages = list(reader.pages)
    writer = PdfWriter()
    for idx in order:
        if idx < 0 or idx >= len(pages):
            raise PdfError(f"index page invalide : {idx}")
        writer.add_page(pages[idx])
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as handle:
        writer.write(handle)
    return dest


def extract_images(src: Path, dest_dir: Path, *, password: str = "") -> list[Path]:
    _require()
    reader = _open_reader(src, password)
    dest_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for page_no, page in enumerate(reader.pages, 1):
        images = getattr(page, "images", None)
        if not images:
            continue
        for img_no, image in enumerate(images, 1):
            data = image.data
            ext = ".bin"
            filt = str(getattr(image, "filter", "") or "")
            if "DCTDecode" in filt:
                ext = ".jpg"
            elif "FlateDecode" in filt:
                ext = ".png"
            dest = dest_dir / f"page{page_no:03d}-{img_no:02d}{ext}"
            dest.write_bytes(data)
            written.append(dest)
    return written
