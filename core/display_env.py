# SPDX-License-Identifier: GPL-3.0-or-later
"""GTK4 display fallbacks before Gtk is imported.

Mint 21.3 / Jammy / VMs: GSK GL + EGL DRI2 fail (`libEGL warning: DRI2:
failed to authenticate`). Gio.Application then drops its use-count and
run() returns 0 with no window.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_OS_RELEASE_CANDIDATES = (
    Path("/etc/os-release"),
    Path("/run/host/etc/os-release"),
    Path("/var/run/host/etc/os-release"),
)
_DMI_PRODUCT = Path("/sys/class/dmi/id/product_name")
_VM_MARKERS = ("virtualbox", "vmware", "qemu", "kvm", "bochs", "virtual machine", "hyper-v")

_SAFE_ENV = (
    ("GSK_RENDERER", "cairo"),
    ("GDK_BACKEND", "x11"),
    ("GDK_DEBUG", "gl-disable"),
    ("GDK_DISABLE", "gl,egl,vulkan"),
    ("LIBGL_ALWAYS_SOFTWARE", "1"),
    ("MESA_LOADER_DRIVER_OVERRIDE", "llvmpipe"),
    ("GALLIUM_DRIVER", "llvmpipe"),
    ("NO_AT_BRIDGE", "1"),
    ("GTK_A11Y", "none"),
)


def read_os_release(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return data
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key] = value.strip().strip('"')
    return data


def detect_virt() -> str:
    try:
        proc = subprocess.run(
            ["systemd-detect-virt"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return (proc.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def needs_safe_display(
    os_release: dict[str, str],
    *,
    product_name: str = "",
    virt: str = "",
) -> bool:
    name = (virt or "").strip()
    if name and name != "none":
        return True
    os_id = (os_release.get("ID") or "").lower()
    like = (os_release.get("ID_LIKE") or "").lower()
    version = os_release.get("VERSION_ID") or ""
    ubuntu = (os_release.get("UBUNTU_CODENAME") or os_release.get("VERSION_CODENAME") or "").lower()
    if os_id == "linuxmint":
        return True
    if ubuntu == "jammy":
        return True
    if os_id == "ubuntu" and version.startswith("22.04"):
        return True
    if "ubuntu" in like and version.startswith("22.04"):
        return True
    product = product_name.lower()
    return any(marker in product for marker in _VM_MARKERS)


def apply_safe_display_env() -> dict[str, str]:
    """Set software GTK/GDK env on Mint/Jammy/VM. Returns keys actually applied."""
    os_release: dict[str, str] = {}
    for path in _OS_RELEASE_CANDIDATES:
        os_release = read_os_release(path)
        if os_release:
            break
    product = ""
    try:
        product = _DMI_PRODUCT.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        product = ""
    if not needs_safe_display(os_release, product_name=product, virt=detect_virt()):
        return {}
    applied: dict[str, str] = {}
    for key, value in _SAFE_ENV:
        if key == "GSK_RENDERER" and os.environ.get("GSK_RENDERER"):
            applied[key] = os.environ[key]
            continue
        if key == "GDK_BACKEND" and os.environ.get("GDK_BACKEND"):
            applied[key] = os.environ[key]
            continue
        os.environ[key] = value
        applied[key] = value
    return applied
