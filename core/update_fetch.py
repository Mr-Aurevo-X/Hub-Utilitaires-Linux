# SPDX-License-Identifier: GPL-3.0-or-later
"""Check and download Hub Utilitaires updates (GitHub allowlist only)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from core import host
from core.update_url import (
    APP_ID,
    Channel,
    FLATPAK_ASSET,
    FLATPAK_DIRECT,
    FLATPAK_PUBLIC_RELEASES,
    FLATPAK_RELEASES_API,
    SHORTCUT_ASSET,
    SHORTCUT_DIRECT,
    NATIVE_ASSET_TMPL,
    NATIVE_DIRECT,
    NATIVE_PUBLIC_RELEASES,
    NATIVE_RELEASES_API,
    TAG_PREFIX,
    UpdateError,
    _MAX_BUNDLE_BYTES,
    _MAX_JSON_BYTES,
    _NOTES_MAX,
    _opener,
    _require_allowed_url,
    parse_semver,
    version_from_release,
)

log = logging.getLogger("kit.updater")


def update_channel() -> Channel:
    """Public Hub Utilitaires releases are Flatpak-only (Mr-Aurevo-X/Hub Utilitaires)."""
    return "flatpak"


def local_version() -> str:
    """Installed app version (bundle VERSION, not AppStream cache)."""
    candidates: list[Path] = []
    if host.is_flatpak():
        candidates.append(Path("/app/share/hub-utilitaires/VERSION"))
    candidates.append(Path(__file__).resolve().parent.parent / "VERSION")
    if not host.is_flatpak():
        candidates.append(Path.home() / ".local" / "share" / "hub-utilitaires" / "VERSION")
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            if path.is_file():
                text = path.read_text(encoding="utf-8").strip()
                if text:
                    return text
        except OSError:
            continue
    return "0.0.0"


def updates_dir() -> Path:
    """Host-visible cache (not sandbox XDG_DATA_HOME)."""
    path = Path.home() / ".local" / "share" / "hub-utilitaires" / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def public_download_url(version: str, channel: Channel | None = None) -> str:
    ch = channel or update_channel()
    if ch == "flatpak":
        return FLATPAK_DIRECT.format(version=version)
    return NATIVE_DIRECT.format(version=version)


def restart_hint(channel: Channel | None = None) -> str:
    ch = channel or update_channel()
    if ch == "flatpak":
        return f"flatpak run {APP_ID}"
    return "hub-utilitaires"


def flatpak_install_block(info: dict[str, Any]) -> str:
    version = str(info.get("version") or "")
    url = str(info.get("download_url") or public_download_url(version, "flatpak"))
    asset = str(info.get("asset_name") or FLATPAK_ASSET)
    shortcut_url = str(info.get("shortcut_url") or SHORTCUT_DIRECT.format(version=version))
    return (
        f"curl -fL -o {asset} \\\n  {url}\n"
        f"flatpak install --user -y --reinstall ./{asset}\n"
        f"curl -fL -o {SHORTCUT_ASSET} \\\n  {shortcut_url}\n"
        f"bash ./{SHORTCUT_ASSET}\n"
        f"flatpak run {APP_ID}"
    )


def format_update_dialog_commands(info: dict[str, Any]) -> str:
    channel = str(info.get("channel") or update_channel())
    if channel == "flatpak":
        return flatpak_install_block(info)
    latest = str(info.get("version") or "?")
    url = str(info.get("download_url") or public_download_url(latest, "native"))
    asset = NATIVE_ASSET_TMPL.format(version=latest)
    return f"curl -fL -o {asset} \\\n  {url}"


def format_update_dialog_body(info: dict[str, Any]) -> str:
    latest = str(info.get("version") or "?")
    current = str(info.get("current") or local_version())
    release_url = str(info.get("html_url") or PUBLIC_RELEASES)
    parts = [
        f"Hub Utilitaires {latest} disponible (vous avez {current}).",
        "",
        f"Release : {release_url}",
    ]
    notes = str(info.get("notes") or "").strip()
    if notes:
        parts.extend(["", notes])
    return "\n".join(parts)


def app_display_name() -> str:
    return f"Hub Utilitaires {local_version()}"


def _user_agent() -> str:
    return f"HubUtilitaires/{local_version()}"


def _http_json(url: str, timeout: float = 15.0) -> Any:
    _require_allowed_url(url, kind="api")
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _user_agent(),
            "Accept": "application/vnd.github+json",
        },
    )
    with _opener().open(req, timeout=timeout) as resp:
        raw = resp.read(_MAX_JSON_BYTES + 1)
    if len(raw) > _MAX_JSON_BYTES:
        raise UpdateError("Réponse de mise à jour trop volumineuse")
    return json.loads(raw.decode("utf-8"))


def _snippet(body: str | None) -> str:
    text = (body or "").strip().replace("\r\n", "\n")
    if not text:
        return ""
    if len(text) > _NOTES_MAX:
        return text[: _NOTES_MAX - 1].rstrip() + "…"
    return text


def _asset_name(channel: Channel, version: str) -> str:
    if channel == "flatpak":
        return FLATPAK_ASSET
    return NATIVE_ASSET_TMPL.format(version=version)


def _asset_url(item: dict[str, Any], version: str, channel: Channel) -> str:
    wanted = _asset_name(channel, version)
    for asset in item.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") != wanted:
            continue
        url = str(asset.get("browser_download_url") or "").strip()
        if not url:
            continue
        try:
            return _require_allowed_url(url, kind="download")
        except UpdateError:
            continue
    return public_download_url(version, channel)


def check_for_update(*, raise_on_error: bool = False) -> dict[str, Any] | None:
    """Return latest newer Hub Utilitaires release for the active channel, or None."""
    channel = update_channel()
    api = FLATPAK_RELEASES_API if channel == "flatpak" else NATIVE_RELEASES_API
    public = FLATPAK_PUBLIC_RELEASES if channel == "flatpak" else NATIVE_PUBLIC_RELEASES
    try:
        payload = _http_json(api)
    except urllib.error.HTTPError as exc:
        log.info("update check skipped (HTTP %s, channel=%s)", exc.code, channel)
        if raise_on_error:
            raise UpdateError(f"HTTP {exc.code}") from exc
        return None
    except UpdateError:
        if raise_on_error:
            raise
        log.info("update check skipped (url refusée, channel=%s)", channel)
        return None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        log.info("update check skipped (%s, channel=%s)", exc, channel)
        if raise_on_error:
            raise UpdateError(str(exc)) from exc
        return None

    if not isinstance(payload, list):
        if raise_on_error:
            raise UpdateError("Réponse invalide du canal de mises à jour")
        return None

    current = local_version()
    current_tuple = parse_semver(current) or (0, 0, 0)
    best: dict[str, Any] | None = None
    best_tuple = current_tuple

    for item in payload:
        if not isinstance(item, dict):
            continue
        if item.get("draft") or item.get("prerelease"):
            continue
        tag = str(item.get("tag_name") or "")
        name = str(item.get("name") or "")
        version = version_from_release(tag, name)
        if version is None:
            continue
        parsed = parse_semver(version)
        if parsed is None or parsed <= best_tuple:
            continue
        # Prefer releases that actually ship the expected asset.
        url = _asset_url(item, version, channel)
        try:
            url = _require_allowed_url(url, kind="download")
        except UpdateError:
            continue
        if channel == "native" and not url.split("?", 1)[0].endswith(".tar.gz"):
            continue
        if channel == "flatpak" and not url.split("?", 1)[0].endswith(".flatpak"):
            continue
        best_tuple = parsed
        best = {
            "version": version,
            "current": current,
            "tag": tag or f"{TAG_PREFIX}{version}",
            "name": name,
            "notes": _snippet(str(item.get("body") or "")),
            "html_url": str(item.get("html_url") or public),
            "download_url": url,
            "channel": channel,
            "asset_name": _asset_name(channel, version),
        }

    return best


def download_bundle(url: str, dest: Path | None = None) -> Path:
    safe_url = _require_allowed_url(url, kind="download")
    if dest is None:
        dest = updates_dir() / "update.bin"
    target = dest
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    req = urllib.request.Request(
        safe_url,
        headers={"User-Agent": _user_agent(), "Accept": "application/octet-stream"},
    )
    written = 0
    try:
        with _opener().open(req, timeout=120) as resp, tmp.open("wb") as out:
            while True:
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > _MAX_BUNDLE_BYTES:
                    raise UpdateError("Fichier de mise à jour trop volumineux")
                out.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError, UpdateError) as exc:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, UpdateError):
            raise
        raise UpdateError(f"Téléchargement impossible : {exc}") from exc
    if tmp.stat().st_size <= 0:
        tmp.unlink(missing_ok=True)
        raise UpdateError("Fichier de mise à jour vide")
    tmp.replace(target)
    return target
