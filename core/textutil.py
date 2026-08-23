# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import difflib
import hashlib
import html
import re
import unicodedata


class TextError(Exception):
    pass


def regex_matches(pattern: str, text: str, *, ignore_case: bool = False) -> tuple[list[str], int]:
    if not pattern:
        raise TextError("motif vide")
    flags = re.MULTILINE
    if ignore_case:
        flags |= re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise TextError(f"regex invalide : {exc}") from exc
    found = compiled.findall(text)
    rows: list[str] = []
    for item in found:
        if isinstance(item, tuple):
            rows.append(" | ".join(str(part) for part in item))
        else:
            rows.append(str(item))
    return rows, len(rows)


def unified_diff(left: str, right: str, *, left_name: str = "a", right_name: str = "b") -> str:
    lines = difflib.unified_diff(
        left.splitlines(keepends=True),
        right.splitlines(keepends=True),
        fromfile=left_name,
        tofile=right_name,
        lineterm="",
    )
    return "\n".join(lines)


def lined_diff(left: str, right: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in difflib.ndiff(left.splitlines(), right.splitlines()):
        if line.startswith("? "):
            continue
        if line.startswith("- "):
            rows.append(("-", line[2:]))
        elif line.startswith("+ "):
            rows.append(("+", line[2:]))
        elif line.startswith("  "):
            rows.append((" ", line[2:]))
    return rows


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def slugify(text: str) -> str:
    base = strip_accents(text).lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


def counts(text: str) -> dict[str, int]:
    lines = text.splitlines()
    words = re.findall(r"\S+", text)
    graphemes = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        graphemes += 1
    return {
        "chars": len(text),
        "bytes": len(text.encode("utf-8")),
        "lines": len(lines) if text else 0,
        "words": len(words),
        "graphemes": graphemes,
    }


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def wrap_text(text: str, width: int = 80) -> str:
    limit = max(8, int(width))
    out: list[str] = []
    for line in text.splitlines():
        if len(line) <= limit:
            out.append(line)
            continue
        current = line
        while len(current) > limit:
            cut = current.rfind(" ", 0, limit + 1)
            if cut <= 0:
                cut = limit
            out.append(current[:cut].rstrip())
            current = current[cut:].lstrip()
        if current:
            out.append(current)
    return "\n".join(out)


def transform(text: str, mode: str) -> str:
    key = (mode or "").lower()
    if key == "upper":
        return text.upper()
    if key == "lower":
        return text.lower()
    if key == "title":
        return text.title()
    if key == "trim":
        return "\n".join(line.strip() for line in text.splitlines())
    if key == "squeeze":
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(lines)
    if key == "slug":
        return slugify(text)
    if key == "accents":
        return strip_accents(text)
    if key == "nfc":
        return unicodedata.normalize("NFC", text)
    if key == "nfd":
        return unicodedata.normalize("NFD", text)
    if key == "html_escape":
        return html.escape(text, quote=True)
    if key == "html_unescape":
        return html.unescape(text)
    if key == "lf":
        return text.replace("\r\n", "\n").replace("\r", "\n")
    if key == "crlf":
        return transform(text, "lf").replace("\n", "\r\n")
    if key == "cr":
        return transform(text, "lf").replace("\n", "\r")
    if key == "sort":
        return "\n".join(sorted(text.splitlines()))
    if key == "unique":
        seen: set[str] = set()
        rows: list[str] = []
        for line in text.splitlines():
            if line in seen:
                continue
            seen.add(line)
            rows.append(line)
        return "\n".join(rows)
    if key == "reverse":
        return "\n".join(reversed(text.splitlines()))
    if key == "rstrip":
        return "\n".join(line.rstrip() for line in text.splitlines())
    if key == "wrap":
        return wrap_text(text, 80)
    raise TextError(f"transformation inconnue : {mode}")


def normalize_clipboard(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        try:
            import json

            return json.dumps(json.loads(cleaned), indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    return transform(cleaned, "trim")


def _norm_line(line: str, *, ignore_ws: bool, ignore_eol: bool) -> str:
    out = line
    if ignore_eol:
        out = out.rstrip("\r\n")
    if ignore_ws:
        out = re.sub(r"\s+", " ", out.strip())
    return out


def lined_diff_options(left: str, right: str, *, ignore_ws: bool = False, ignore_eol: bool = False) -> list[tuple[str, str]]:
    ll = [_norm_line(line, ignore_ws=ignore_ws, ignore_eol=ignore_eol) for line in left.splitlines()]
    rr = [_norm_line(line, ignore_ws=ignore_ws, ignore_eol=ignore_eol) for line in right.splitlines()]
    return lined_diff("\n".join(ll), "\n".join(rr))


def regex_replace_preview(pattern: str, repl: str, text: str, *, ignore_case: bool = False) -> str:
    flags = re.MULTILINE
    if ignore_case:
        flags |= re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise TextError(f"regex invalide : {exc}") from exc
    return compiled.sub(repl, text)
