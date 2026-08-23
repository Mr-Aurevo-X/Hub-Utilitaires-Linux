# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal Flatpak-aware helpers for the updater (no host sysadmin bridge)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

_orig_run = subprocess.run
_orig_which = shutil.which
_HOST_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_UNSET_HOST_ENV = (
    "LD_LIBRARY_PATH",
    "LD_PRELOAD",
    "PYTHONPATH",
    "PYTHONHOME",
    "GI_TYPELIB_PATH",
)


def is_flatpak() -> bool:
    return Path("/.flatpak-info").exists() or bool(os.environ.get("FLATPAK_ID"))


def _is_sandbox_path(path: str) -> bool:
    return path == "/app" or path.startswith("/app/")


def host_cwd() -> str:
    for raw in (os.environ.get("HOME"), str(Path.home()), "/"):
        if not raw:
            continue
        path = os.path.abspath(raw)
        if _is_sandbox_path(path):
            continue
        try:
            if os.path.isdir(path):
                return path
        except OSError:
            continue
    return "/"


def wrap(cmd: list[str]) -> list[str]:
    if not is_flatpak() or not cmd or cmd[0] == "flatpak-spawn":
        return list(cmd)
    env_cmd: list[str] = ["/usr/bin/env"]
    for name in _UNSET_HOST_ENV:
        env_cmd.extend(["-u", name])
    env_cmd.append(f"PATH={_HOST_PATH}")
    env_cmd.extend(cmd)
    return ["flatpak-spawn", "--host", f"--directory={host_cwd()}", "--", *env_cmd]


def run(cmd: Any, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    if isinstance(cmd, (list, tuple)):
        cmd = wrap([str(part) for part in cmd])
        if is_flatpak() and cmd and cmd[0] == "flatpak-spawn":
            kwargs = dict(kwargs)
            kwargs["cwd"] = host_cwd()
    return _orig_run(cmd, *args, **kwargs)


def which(cmd: str) -> str | None:
    if not cmd or cmd.startswith("-"):
        return None
    if not is_flatpak():
        return _orig_which(cmd)
    try:
        completed = _orig_run(
            wrap(["sh", "-c", 'command -v "$1"', "sh", cmd]),
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            cwd=host_cwd(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    lines = (completed.stdout or "").strip().splitlines()
    if completed.returncode == 0 and lines:
        return lines[0].strip() or None
    return None
