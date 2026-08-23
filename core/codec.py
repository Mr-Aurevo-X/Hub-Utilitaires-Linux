# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import codecs
import configparser
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import quote, unquote
from xml.dom import minidom
from xml.parsers.expat import ExpatError

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]


class CodecError(Exception):
    pass


def pretty_json(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodecError(f"JSON invalide : {exc}") from exc
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def pretty_yaml(text: str) -> str:
    if yaml is None:
        raise CodecError("PyYAML n’est pas installé (python-yaml / python3-yaml).")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CodecError(f"YAML invalide : {exc}") from exc
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def minify_json(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodecError(f"JSON invalide : {exc}") from exc
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _iter_json_values(text: str) -> list[object]:
    decoder = json.JSONDecoder()
    values: list[object] = []
    idx = 0
    raw = text or ""
    length = len(raw)
    while idx < length:
        while idx < length and raw[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            value, end = decoder.raw_decode(raw, idx)
        except json.JSONDecodeError as exc:
            line = raw.count("\n", 0, idx) + 1
            raise CodecError(f"ligne {line}: {exc.msg}") from exc
        values.append(value)
        idx = end
    return values


def validate_jsonl(text: str) -> None:
    _iter_json_values(text)


def pretty_jsonl(text: str) -> str:
    parts = [json.dumps(value, indent=2, ensure_ascii=False) for value in _iter_json_values(text)]
    return "\n".join(parts) + ("\n" if parts else "")


def minify_jsonl(text: str) -> str:
    parts = [json.dumps(value, separators=(",", ":"), ensure_ascii=False) for value in _iter_json_values(text)]
    return "\n".join(parts) + ("\n" if parts else "")


def merge_csv_files(paths: list[Path], dest: Path) -> Path:
    if not paths:
        raise CodecError("aucun CSV")
    headers: list[str] | None = None
    rows: list[list[str]] = []
    for path in paths:
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                try:
                    header = next(reader)
                except StopIteration as exc:
                    raise CodecError(f"CSV vide : {path}") from exc
                if headers is None:
                    headers = header
                elif header != headers:
                    raise CodecError("en-têtes CSV différents")
                rows.extend(list(reader))
        except OSError as exc:
            raise CodecError(str(exc)) from exc
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(headers or [])
        writer.writerows(rows)
    return dest


def split_csv_file(src: Path, dest_dir: Path, rows_per_file: int) -> list[Path]:
    size = max(1, int(rows_per_file))
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        with src.open(encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise CodecError("CSV vide") from exc
            data = list(reader)
    except OSError as exc:
        raise CodecError(str(exc)) from exc
    if not data:
        raise CodecError("CSV sans lignes")
    written: list[Path] = []
    index = 1
    for start in range(0, len(data), size):
        dest = dest_dir / f"{src.stem}_part{index:03d}.csv"
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            writer.writerows(data[start : start + size])
        written.append(dest)
        index += 1
    return written


def pretty_xml(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        raise CodecError("XML vide")
    try:
        parsed = minidom.parseString(raw.encode("utf-8"))
    except ExpatError as exc:
        raise CodecError(f"XML invalide : {exc}") from exc
    pretty = parsed.toprettyxml(indent="  ")
    lines = [line for line in pretty.splitlines() if line.strip()]
    return "\n".join(lines) + "\n"


def pretty_ini(text: str) -> str:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise CodecError(f"INI invalide : {exc}") from exc
    buf = io.StringIO()
    parser.write(buf)
    return buf.getvalue()


def rot13(text: str) -> str:
    return codecs.encode(text, "rot_13")


def hash_text(text: str, algo: str = "sha256") -> str:
    name = (algo or "sha256").lower().replace("-", "")
    if name in {"blake2", "blake2b"}:
        name = "blake2b"
    if name not in {"sha256", "blake2b"}:
        raise CodecError(f"algo texte inconnu : {algo}")
    return hashlib.new(name, text.encode("utf-8")).hexdigest()


def hexdump_text(text: str, *, limit: int = 4096) -> str:
    data = text.encode("utf-8")[: max(16, int(limit))]
    lines: list[str] = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hexpart = " ".join(f"{byte:02x}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{offset:08x}  {hexpart:<48}  {ascii_part}")
    return "\n".join(lines)


def _b64url_decode(part: str) -> bytes:
    padded = part + "=" * (-len(part) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise CodecError("JWT : segment Base64 invalide") from exc


def decode_jwt(token: str) -> str:
    raw = (token or "").strip()
    if not raw:
        raise CodecError("jeton vide")
    parts = raw.split(".")
    if len(parts) < 2:
        raise CodecError("JWT invalide (header.payload[.signature])")
    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        payload = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except CodecError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CodecError(f"JWT illisible : {exc}") from exc
    signed = len(parts) >= 3 and bool(parts[2])
    note = "signature présente — non vérifiée (décodage local uniquement)"
    if not signed:
        note = "pas de signature"
    return (
        json.dumps({"header": header, "payload": payload, "note": note}, indent=2, ensure_ascii=False)
        + "\n"
    )


def b64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def b64_decode(text: str) -> str:
    compact = "".join((text or "").split())
    if not compact:
        raise CodecError("Base64 vide")
    compact += "=" * (-len(compact) % 4)
    try:
        return base64.b64decode(compact).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise CodecError(f"Base64 invalide : {exc}") from exc


def url_encode(text: str) -> str:
    return quote(text, safe="")


def url_decode(text: str) -> str:
    return unquote(text)


def csv_to_json(text: str) -> str:
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as exc:
        raise CodecError(f"CSV invalide : {exc}") from exc
    if reader.fieldnames is None:
        raise CodecError("CSV sans en-tête")
    return json.dumps(rows, indent=2, ensure_ascii=False) + "\n"


def json_to_csv(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodecError(f"JSON invalide : {exc}") from exc
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not data:
        raise CodecError("JSON : tableau d’objets attendu")
    keys: list[str] = []
    seen: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            raise CodecError("JSON : objets uniquement")
        for key in row:
            if key not in seen:
                seen.add(key)
                keys.append(str(key))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow({key: row.get(key, "") for key in keys})
    return buf.getvalue()


def json_to_yaml(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodecError(f"JSON invalide : {exc}") from exc
    if yaml is None:
        raise CodecError("PyYAML n’est pas installé (python-yaml / python3-yaml).")
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def yaml_to_json(text: str) -> str:
    if yaml is None:
        raise CodecError("PyYAML n’est pas installé (python-yaml / python3-yaml).")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CodecError(f"YAML invalide : {exc}") from exc
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def flatten_json(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CodecError(f"JSON invalide : {exc}") from exc
    flat: dict[str, object] = {}

    def walk(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            if not node:
                flat[prefix or "{}"] = {}
                return
            for key, value in node.items():
                nxt = f"{prefix}.{key}" if prefix else str(key)
                walk(value, nxt)
            return
        if isinstance(node, list):
            if not node:
                flat[prefix or "[]"] = []
                return
            for index, value in enumerate(node):
                walk(value, f"{prefix}[{index}]")
            return
        flat[prefix] = node

    walk(data, "")
    return json.dumps(flat, indent=2, ensure_ascii=False) + "\n"
