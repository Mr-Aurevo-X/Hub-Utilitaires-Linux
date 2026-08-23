# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from pathlib import Path

HOLDER = "Mr-Aurevo-X"
YEAR = "2026"


def copyright_line() -> str:
    return f"© {YEAR} {HOLDER}"


def _legal_paths() -> list[Path]:
    root = Path(__file__).resolve().parent.parent
    return [
        root / "LEGAL.md",
        Path("/app/share/hub-utilitaires/LEGAL.md"),
        Path.home() / ".local" / "share" / "hub-utilitaires" / "LEGAL.md",
    ]


def _extract_lang(markdown: str, lang: str) -> str:
    wanted = f"<!-- lang:{lang} -->"
    other = "<!-- lang:en -->" if lang == "fr" else "<!-- lang:fr -->"
    start = markdown.find(wanted)
    if start < 0:
        return markdown.strip()
    body = markdown[start + len(wanted) :]
    end = body.find(other)
    if end >= 0:
        body = body[:end]
    return body.strip()


def legal_markdown(lang: str | None = None) -> str:
    code = (lang or "fr").split("-", 1)[0].lower()
    if code not in {"fr", "en"}:
        code = "fr"
    for path in _legal_paths():
        try:
            if path.is_file():
                return _extract_lang(path.read_text(encoding="utf-8"), code)
        except OSError:
            continue
    return f"{copyright_line()}\n\nGPL-3.0-or-later. Local app; GitHub only for optional updates."
