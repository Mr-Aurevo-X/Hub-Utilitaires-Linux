# SPDX-License-Identifier: GPL-3.0-or-later
"""Compat wrapper — prefer core.display_env."""

from __future__ import annotations

import os

from core.display_env import apply_safe_display_env, needs_safe_display, read_os_release


def choose_renderer(*, os_release: str, virt: str | None) -> str | None:
    if os.environ.get("GSK_RENDERER"):
        return None
    data: dict[str, str] = {}
    for line in os_release.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    if needs_safe_display(data, virt=virt or ""):
        return "cairo"
    return None


def apply_gsk_fallback() -> str | None:
    applied = apply_safe_display_env()
    return applied.get("GSK_RENDERER")


__all__ = ["apply_gsk_fallback", "choose_renderer", "apply_safe_display_env", "read_os_release"]
