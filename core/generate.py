# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import math
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import segno
except ImportError:  # pragma: no cover
    segno = None  # type: ignore[assignment]


class GenerateError(Exception):
    pass


LENGTH_TO_M = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in": 0.0254,
    "ft": 0.3048,
    "yd": 0.9144,
    "mi": 1609.344,
}
MASS_TO_KG = {
    "mg": 0.000001,
    "g": 0.001,
    "kg": 1.0,
    "oz": 0.028349523125,
    "lb": 0.45359237,
}
SIZE_TO_B = {
    "b": 1.0,
    "kib": 1024.0,
    "mib": 1024.0**2,
    "gib": 1024.0**3,
}
# Embedded word list — no network fetch.
_WORDS = (
    "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima "
    "mike november oscar papa quebec romeo sierra tango uniform victor whiskey "
    "xray yankee zulu apple river cedar maple granite harbor meadow canyon "
    "orchid pebble quartz amber willow coral ember frost glacier harbor "
    "island jungle lantern meadow nectar orchard pebble quartz raven "
    "saddle timber umber velvet willow xenon yarrow zenith "
    "anchor blossom canyon drift ember fjord grove hollow inlet "
    "jasper knoll lagoon meadow nexus orchard prairie quartz ridge "
    "summit timber upland valley willow "
).split()
_LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. "
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris. "
    "Duis aute irure dolor in reprehenderit in voluptate velit esse. "
    "Excepteur sint occaecat cupidatat non proident, sunt in culpa."
).split(". ")


def new_uuid() -> str:
    return str(uuid.uuid4())


def new_uuid5(name: str, *, namespace: str = "dns") -> str:
    key = (namespace or "dns").strip().lower()
    table = {
        "dns": uuid.NAMESPACE_DNS,
        "url": uuid.NAMESPACE_URL,
        "oid": uuid.NAMESPACE_OID,
        "x500": uuid.NAMESPACE_X500,
    }
    ns = table.get(key)
    if ns is None:
        try:
            ns = uuid.UUID(namespace)
        except ValueError as exc:
            raise GenerateError("namespace UUID : dns / url / oid / x500 / UUID") from exc
    text = (name or "").strip()
    if not text:
        raise GenerateError("nom UUID v5 vide")
    return str(uuid.uuid5(ns, text))


def unix_to_iso(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise GenerateError("timestamp vide")
    try:
        stamp = float(text)
    except ValueError as exc:
        raise GenerateError("timestamp Unix invalide") from exc
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def iso_to_unix(value: str) -> str:
    text = (value or "").strip()
    if not text:
        raise GenerateError("date vide")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise GenerateError("date ISO invalide") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return str(parsed.timestamp())


def now_unix_iso() -> tuple[str, str]:
    now = datetime.now(tz=timezone.utc)
    return str(now.timestamp()), now.isoformat().replace("+00:00", "Z")


def date_plus_days(days: int) -> str:
    now = datetime.now(tz=timezone.utc) + timedelta(days=int(days))
    return now.isoformat().replace("+00:00", "Z")


def week_number(value: str = "") -> int:
    text = (value or "").strip()
    if not text:
        parsed = datetime.now(tz=timezone.utc)
    else:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise GenerateError("date ISO invalide") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.isocalendar().week)


def convert_unit(value: float, src: str, dest: str, kind: str) -> float:
    if kind == "length":
        table = LENGTH_TO_M
    elif kind == "mass":
        table = MASS_TO_KG
    elif kind == "temp":
        return _convert_temp(value, src, dest)
    elif kind == "size":
        table = SIZE_TO_B
    elif kind == "angle":
        return _convert_angle(value, src, dest)
    elif kind == "duration":
        return _convert_duration(value, src, dest)
    else:
        raise GenerateError(f"grandeur inconnue : {kind}")
    src_u = (src or "").strip().lower()
    dest_u = (dest or "").strip().lower()
    if src_u not in table or dest_u not in table:
        raise GenerateError("unité inconnue")
    meters_or_kg = value * table[src_u]
    return meters_or_kg / table[dest_u]


def _convert_temp(value: float, src: str, dest: str) -> float:
    src_u, dest_u = src.lower(), dest.lower()

    def to_c(unit: str, amount: float) -> float:
        if unit == "c":
            return amount
        if unit == "f":
            return (amount - 32.0) * 5.0 / 9.0
        if unit == "k":
            return amount - 273.15
        raise GenerateError("unité température : C / F / K")

    def from_c(unit: str, celsius: float) -> float:
        if unit == "c":
            return celsius
        if unit == "f":
            return celsius * 9.0 / 5.0 + 32.0
        if unit == "k":
            return celsius + 273.15
        raise GenerateError("unité température : C / F / K")

    return from_c(dest_u, to_c(src_u, value))


def _convert_angle(value: float, src: str, dest: str) -> float:
    src_u, dest_u = src.lower(), dest.lower()
    to_rad = {"deg": math.pi / 180.0, "rad": 1.0}
    if src_u not in to_rad or dest_u not in to_rad:
        raise GenerateError("unité angle : deg / rad")
    return value * to_rad[src_u] / to_rad[dest_u]


def _convert_duration(value: float, src: str, dest: str) -> float:
    table = {"s": 1.0, "m": 60.0, "h": 3600.0}
    src_u, dest_u = src.lower(), dest.lower()
    if src_u not in table or dest_u not in table:
        raise GenerateError("unité durée : s / m / h")
    return value * table[src_u] / table[dest_u]


def convert_base(value: str, src_base: int, dest_base: int) -> str:
    text = (value or "").strip().replace(" ", "")
    if not text:
        raise GenerateError("valeur vide")
    try:
        number = int(text, int(src_base))
    except ValueError as exc:
        raise GenerateError("nombre invalide") from exc
    dest = int(dest_base)
    if dest < 2 or dest > 16:
        raise GenerateError("base cible : 2–16")
    if dest == 10:
        return str(number)
    digits = "0123456789abcdef"
    sign = "-" if number < 0 else ""
    number = abs(number)
    if number == 0:
        return "0"
    out: list[str] = []
    while number:
        number, rem = divmod(number, dest)
        out.append(digits[rem])
    return sign + "".join(reversed(out))


_AMBIGUOUS = frozenset("0OIl1")
_SYMBOLS = "!@#$%^&*()-_=+[]{}"


def _filter_alpha(text: str, *, exclude_ambiguous: bool) -> str:
    if not exclude_ambiguous:
        return text
    return "".join(ch for ch in text if ch not in _AMBIGUOUS)


def password(
    length: int = 16,
    *,
    lower: bool = True,
    upper: bool = True,
    digits: bool = True,
    symbols: bool = False,
    exclude_ambiguous: bool = False,
    ensure_classes: bool = False,
) -> tuple[str, float]:
    size = max(4, min(128, int(length)))
    pools: list[str] = []
    if lower:
        pools.append(_filter_alpha(string.ascii_lowercase, exclude_ambiguous=exclude_ambiguous))
    if upper:
        pools.append(_filter_alpha(string.ascii_uppercase, exclude_ambiguous=exclude_ambiguous))
    if digits:
        pools.append(_filter_alpha(string.digits, exclude_ambiguous=exclude_ambiguous))
    if symbols:
        pools.append(_SYMBOLS)
    pools = [pool for pool in pools if pool]
    if not pools:
        raise GenerateError("aucune classe de caractères")
    alphabet = "".join(pools)
    if ensure_classes:
        if size < len(pools):
            raise GenerateError("longueur trop courte pour toutes les classes")
        chars = [secrets.choice(pool) for pool in pools]
        chars.extend(secrets.choice(alphabet) for _ in range(size - len(chars)))
        for index in range(len(chars) - 1, 0, -1):
            swap = secrets.randbelow(index + 1)
            chars[index], chars[swap] = chars[swap], chars[index]
    else:
        chars = [secrets.choice(alphabet) for _ in range(size)]
    entropy = size * math.log2(len(alphabet))
    return "".join(chars), entropy


def password_batch(
    count: int = 1,
    *,
    length: int = 16,
    lower: bool = True,
    upper: bool = True,
    digits: bool = True,
    symbols: bool = False,
    exclude_ambiguous: bool = False,
    ensure_classes: bool = False,
) -> list[tuple[str, float]]:
    size = max(1, min(50, int(count)))
    return [
        password(
            length,
            lower=lower,
            upper=upper,
            digits=digits,
            symbols=symbols,
            exclude_ambiguous=exclude_ambiguous,
            ensure_classes=ensure_classes,
        )
        for _ in range(size)
    ]


def pin(length: int = 6) -> str:
    size = max(4, min(12, int(length)))
    return "".join(secrets.choice(string.digits) for _ in range(size))


def passphrase(words: int = 4) -> str:
    count = max(3, min(12, int(words)))
    return "-".join(secrets.choice(_WORDS) for _ in range(count))


def lorem(*, paragraphs: int = 1, sentences: int = 3) -> str:
    p_count = max(1, min(8, int(paragraphs)))
    s_count = max(1, min(8, int(sentences)))
    blocks: list[str] = []
    idx = 0
    pool = [part.strip().rstrip(".") for part in _LOREM if part.strip()]
    for _ in range(p_count):
        parts: list[str] = []
        for _s in range(s_count):
            parts.append(pool[idx % len(pool)] + ".")
            idx += 1
        blocks.append(" ".join(parts))
    return "\n\n".join(blocks)


def qr_png(text: str, dest: Path, *, scale: int = 8) -> Path:
    if segno is None:
        raise GenerateError("segno n’est pas installé (python-segno). Utilisez le Flatpak ou installez le paquet.")
    payload = (text or "").strip()
    if not payload:
        raise GenerateError("texte QR vide")
    dest.parent.mkdir(parents=True, exist_ok=True)
    qr = segno.make(payload, error="m")
    qr.save(str(dest), kind="png", scale=max(4, min(16, scale)))
    return dest


def dummy_file(dest: Path, megabytes: float) -> Path:
    size = max(1, int(float(megabytes) * 1024 * 1024))
    dest.parent.mkdir(parents=True, exist_ok=True)
    chunk = b"\x00" * min(size, 1024 * 1024)
    remaining = size
    with dest.open("wb") as handle:
        while remaining > 0:
            block = chunk[: min(len(chunk), remaining)]
            handle.write(block)
            remaining -= len(block)
    return dest


def desktop_entry(
    *,
    name: str,
    exec_cmd: str,
    icon: str = "org.mraurevox.HubUtilitaires",
    terminal: bool = False,
    dest_dir: Path | None = None,
) -> Path:
    title = (name or "").strip()
    command = (exec_cmd or "").strip()
    if not title or not command:
        raise GenerateError("nom et Exec requis")
    apps = dest_dir or (Path.home() / ".local" / "share" / "applications")
    apps.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch if ch.isalnum() else "-" for ch in title.lower()).strip("-") or "app"
    dest = apps / f"{slug}.desktop"
    term = "true" if terminal else "false"
    dest.write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={title}",
                f"Exec={command}",
                f"Icon={icon or 'application-x-executable'}",
                f"Terminal={term}",
                "Categories=Utility;",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return dest


def qr_read_image(path: Path) -> str:
    from core import host

    zbar = host.which("zbarimg")
    if not zbar:
        raise GenerateError("zbarimg introuvable (installez zbar sur l’hôte)")
    import subprocess

    cmd = host.wrap([zbar, "-q", "--raw", str(path)])
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            cwd=host.host_cwd() if host.is_flatpak() else None,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GenerateError(str(exc)) from exc
    text = (completed.stdout or "").strip()
    if completed.returncode != 0 or not text:
        raise GenerateError((completed.stderr or "QR illisible").strip())
    return text


def markdown_to_pango(text: str) -> str:
    import html
    import re

    lines = (text or "").splitlines()
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            out.append("")
            continue
        if line.startswith("### "):
            out.append(f"<b>{html.escape(line[4:])}</b>")
        elif line.startswith("## "):
            out.append(f"<span size='large'><b>{html.escape(line[3:])}</b></span>")
        elif line.startswith("# "):
            out.append(f"<span size='x-large'><b>{html.escape(line[2:])}</b></span>")
        elif line.startswith("- "):
            out.append(f"• {html.escape(line[2:])}")
        else:
            escaped = html.escape(line)
            escaped = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", escaped)
            out.append(escaped)
    return "\n".join(out)


def cron_next(expression: str, *, count: int = 5) -> list[str]:
    parts = (expression or "").strip().split()
    if len(parts) != 5:
        raise GenerateError("expression cron : 5 champs (min h dom mois dow)")
    now = datetime.now(tz=timezone.utc)
    hits: list[str] = []
    probe = now
    for _ in range(60 * 24 * 366):
        probe += timedelta(minutes=1)
        if _cron_match(parts, probe):
            hits.append(probe.isoformat().replace("+00:00", "Z"))
            if len(hits) >= max(1, min(count, 20)):
                break
    if not hits:
        raise GenerateError("aucune occurrence trouvée (fenêtre 1 an)")
    return hits


def _cron_match(fields: list[str], moment: datetime) -> bool:
    minute, hour, dom, month, dow = fields
    return (
        _cron_field(minute, moment.minute, 0, 59)
        and _cron_field(hour, moment.hour, 0, 23)
        and _cron_field(dom, moment.day, 1, 31)
        and _cron_field(month, moment.month, 1, 12)
        and _cron_field(dow, moment.weekday(), 0, 6)
    )


def _cron_field(field: str, value: int, low: int, high: int) -> bool:
    if field == "*":
        return True
    for part in field.split(","):
        if part.isdigit():
            if int(part) == value:
                return True
        elif "/" in part:
            base, step = part.split("/", 1)
            step_n = int(step)
            start = low if base == "*" else int(base)
            if value >= start and (value - start) % step_n == 0:
                return True
        elif "-" in part:
            a, b = part.split("-", 1)
            if int(a) <= value <= int(b):
                return True
    return False


def gitignore_suggest(root: Path) -> str:
    if not root.is_dir():
        raise GenerateError("dossier invalide")
    ext_counts: dict[str, int] = {}
    for path in root.rglob("*"):
        if not path.is_file() or any(part.startswith(".") for part in path.parts):
            continue
        ext = path.suffix.lower() or "(none)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
    common = {
        ".pyc": "__pycache__/\n*.py[cod]",
        ".log": "*.log",
        ".tmp": "*.tmp",
        ".zip": "*.zip",
        ".tar": "*.tar\n*.tar.gz",
    }
    lines = ["# Suggestion Hub Utilitaires — relire avant commit", ""]
    if (root / "node_modules").is_dir():
        lines.append("node_modules/")
    if (root / "venv").is_dir() or (root / ".venv").is_dir():
        lines.append("venv/\n.venv/")
    for ext, block in common.items():
        if ext_counts.get(ext, 0) >= 3:
            lines.append(block)
    lines.append("")
    return "\n".join(lines)


def env_inspect(path: Path, *, mask: bool = True) -> str:
    if not path.is_file():
        raise GenerateError("fichier .env introuvable")
    lines_out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            lines_out.append(raw)
            continue
        if "=" not in line:
            lines_out.append(f"# INVALID: {line}")
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        value = val.strip().strip("'\"")
        if mask and value:
            value = "***"
        if not key:
            lines_out.append("# EMPTY KEY")
        else:
            lines_out.append(f"{key}={value}")
    return "\n".join(lines_out) + "\n"
