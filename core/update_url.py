# SPDX-License-Identifier: GPL-3.0-or-later
"""GitHub allowlist for Hub Utilitaires updates. No other host."""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Literal

Channel = Literal["flatpak", "native"]

SOURCE_REPO = "Mr-Aurevo-X/Hub-Utilitaires-Linux"
KIT_REPO = SOURCE_REPO
FLATPAK_RELEASES_API = f"https://api.github.com/repos/{SOURCE_REPO}/releases"
FLATPAK_RELEASES_LATEST_API = f"{FLATPAK_RELEASES_API}/latest"
FLATPAK_RELEASES_LIST_API = f"{FLATPAK_RELEASES_API}?per_page=5"
FLATPAK_PUBLIC_RELEASES = f"https://github.com/{SOURCE_REPO}/releases"
FLATPAK_ASSET = "org.mraurevox.HubUtilitaires.flatpak"
FLATPAK_DIRECT = (
    f"https://github.com/{SOURCE_REPO}/releases/download/"
    "v{version}/" + FLATPAK_ASSET
)
SHORTCUT_ASSET = "INSTALLER-RACCOURCI-FLATPAK.sh"
SHORTCUT_DIRECT = (
    f"https://github.com/{SOURCE_REPO}/releases/download/"
    "v{version}/" + SHORTCUT_ASSET
)

NATIVE_RELEASES_API = "https://api.github.com/repos/Mr-Aurevo-X/linux-releases/releases"
NATIVE_RELEASES_LATEST_API = f"{NATIVE_RELEASES_API}/latest"
NATIVE_RELEASES_LIST_API = f"{NATIVE_RELEASES_API}?per_page=5"
NATIVE_PUBLIC_RELEASES = "https://github.com/Mr-Aurevo-X/linux-releases/releases"
NATIVE_ASSET_TMPL = "MrAurevoX_Kit-{version}.tar.gz"
NATIVE_DIRECT = (
    "https://github.com/Mr-Aurevo-X/linux-releases/releases/download/"
    "v{version}/" + NATIVE_ASSET_TMPL
)

APP_ID = "org.mraurevox.HubUtilitaires"
TAG_PREFIX = "v"
_TAG_RE = re.compile(r"v(\d+\.\d+\.\d+)")
_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_NOTES_MAX = 480

RELEASES_API = FLATPAK_RELEASES_API
PUBLIC_RELEASES = FLATPAK_PUBLIC_RELEASES
ASSET_NAME = FLATPAK_ASSET
DIRECT_URL = (
    f"https://github.com/{SOURCE_REPO}/releases/download/"
    f"{TAG_PREFIX}{{version}}/{FLATPAK_ASSET}"
)

_ALLOWED_API_URLS = frozenset(
    {
        FLATPAK_RELEASES_API,
        FLATPAK_RELEASES_LATEST_API,
        FLATPAK_RELEASES_LIST_API,
        NATIVE_RELEASES_API,
        NATIVE_RELEASES_LATEST_API,
        NATIVE_RELEASES_LIST_API,
    }
)
_TRANSIENT_HTTP = frozenset({502, 503, 504})
_ALLOWED_GITHUB_PATH_PREFIXES = (
    f"/repos/{SOURCE_REPO}/",
    f"/{SOURCE_REPO}/",
    "/repos/Mr-Aurevo-X/linux-releases/",
    "/Mr-Aurevo-X/linux-releases/",
)
_CDN_HOSTS = frozenset(
    {
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
        "github-releases.githubusercontent.com",
    }
)
_MAX_JSON_BYTES = 2 * 1024 * 1024
_MAX_BUNDLE_BYTES = 80 * 1024 * 1024


class UpdateError(Exception):
    """Raised when download or install fails after an update was offered."""


def _require_allowed_url(url: str, *, kind: Literal["api", "download", "any"] = "any") -> str:
    """Reject anything that is not HTTPS GitHub (API, our repos, or release CDN)."""
    text = (url or "").strip()
    if not text:
        raise UpdateError("URL vide")
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme != "https":
        raise UpdateError("URL non HTTPS refusée")
    if parsed.username or parsed.password:
        raise UpdateError("URL avec identifiants refusée")
    host = (parsed.hostname or "").lower()
    if parsed.port not in (None, 443):
        raise UpdateError("Port non autorisé")
    path = parsed.path or "/"

    if kind in ("api", "any") and text in _ALLOWED_API_URLS:
        return text
    if kind == "api":
        raise UpdateError("API de mise à jour non autorisée")

    github_ok = host in {"github.com", "api.github.com"} and any(
        path.startswith(prefix) for prefix in _ALLOWED_GITHUB_PATH_PREFIXES
    )
    if kind == "download":
        if github_ok:
            return text
        raise UpdateError(f"Hôte ou dépôt non autorisé : {host}{path}")

    if github_ok or host in _CDN_HOSTS:
        return text
    raise UpdateError(f"Hôte ou dépôt non autorisé : {host}{path}")


class _BlockHttpHandler(urllib.request.BaseHandler):
    def http_open(self, req: urllib.request.Request) -> Any:
        raise urllib.error.URLError("HTTP clair interdit")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        _require_allowed_url(str(newurl), kind="any")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def _opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        _BlockHttpHandler(),
        _SafeRedirectHandler(),
        urllib.request.HTTPSHandler(context=_ssl_context()),
    )


def parse_semver(version: str) -> tuple[int, int, int] | None:
    match = _SEMVER_RE.fullmatch(version.strip())
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def version_from_release(tag: str, name: str = "") -> str | None:
    for text in (tag, name):
        match = _TAG_RE.search(text or "")
        if match:
            return match.group(1)
    if tag.startswith(TAG_PREFIX):
        rest = tag[len(TAG_PREFIX) :].strip()
        if parse_semver(rest):
            return rest
    return None
