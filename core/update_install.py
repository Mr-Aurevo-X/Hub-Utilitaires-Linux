# SPDX-License-Identifier: GPL-3.0-or-later
"""Install Kit updates (Flatpak / native) and launch the terminal scripts."""

from __future__ import annotations

import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from core import host
from core.update_fetch import (
    _asset_name,
    download_bundle,
    local_version,
    update_channel,
    updates_dir,
)
from core.update_url import (
    APP_ID,
    Channel,
    SHORTCUT_ASSET,
    SHORTCUT_DIRECT,
    UpdateError,
    _MAX_BUNDLE_BYTES,
    _require_allowed_url,
    parse_semver,
)


def install_flatpak_bundle(path: Path) -> None:
    bundle = path.expanduser().resolve()
    if not bundle.is_file():
        raise UpdateError(f"Paquet introuvable : {bundle}")
    if not bundle.read_bytes()[:7].startswith(b"flatpak"):
        raise UpdateError("Fichier Flatpak invalide (magic)")
    exe = host.which("flatpak") or "flatpak"
    completed = host.run(
        [exe, "install", "--user", "-y", str(bundle)],
        check=False,
        capture_output=True,
        text=True,
        timeout=600,
        cwd=host.host_cwd(),
    )
    if completed.returncode == 0:
        return
    err = (completed.stderr or completed.stdout or "flatpak install a échoué").strip()
    raise UpdateError(err)


def _find_extract_root(extract_dir: Path) -> Path:
    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    for child in children:
        if (child / "install.sh").is_file() and (child / "main.py").is_file():
            return child
    if (extract_dir / "install.sh").is_file() and (extract_dir / "main.py").is_file():
        return extract_dir
    raise UpdateError("Archive native invalide : install.sh / main.py introuvables")


def install_native_tarball(path: Path) -> None:
    archive = path.expanduser().resolve()
    if not archive.is_file():
        raise UpdateError(f"Archive introuvable : {archive}")
    # Extract outside the live install tree — rsync --delete into
    # ~/.local/share/hub-utilitaires would delete a nested source mid-copy.
    work = Path(tempfile.mkdtemp(prefix="kit-update-"))
    try:
        try:
            with tarfile.open(archive, "r:gz") as tar:
                # Python 3.12+: refuse suspicious members when available.
                extract_kw: dict[str, Any] = {}
                if hasattr(tarfile, "data_filter"):
                    extract_kw["filter"] = "data"
                tar.extractall(work, **extract_kw)
        except (tarfile.TarError, OSError) as exc:
            raise UpdateError(f"Extraction impossible : {exc}") from exc
        root = _find_extract_root(work)
        install_sh = root / "install.sh"
        completed = host.run(
            ["bash", str(install_sh), "--skip-deps"],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(root),
        )
        if completed.returncode != 0:
            err = (completed.stderr or completed.stdout or "install.sh a échoué").strip()
            raise UpdateError(err)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def install_bundle(path: Path, channel: Channel | None = None) -> None:
    ch = channel or update_channel()
    if ch == "flatpak":
        install_flatpak_bundle(path)
    else:
        install_native_tarball(path)


def apply_update(info: dict[str, Any]) -> Path:
    url = _require_allowed_url(str(info.get("download_url") or ""), kind="download")
    channel: Channel = "flatpak"
    raw_ch = str(info.get("channel") or update_channel())
    if raw_ch in ("flatpak", "native"):
        channel = raw_ch  # type: ignore[assignment]
    version = str(info.get("version") or "").strip()
    if parse_semver(version) is None:
        raise UpdateError("Version de mise à jour invalide")
    dest = updates_dir() / _asset_name(channel, version)
    bundle = download_bundle(url, dest=dest)
    install_bundle(bundle, channel=channel)
    return bundle


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def write_check_report_script(
    *,
    info: dict[str, Any] | None = None,
    error: str | None = None,
) -> Path:
    """Terminal script that shows the update-check result (and optional install)."""
    script = updates_dir() / "run-check.sh"
    current = local_version()
    channel = update_channel()
    canal = "Flatpak" if channel == "flatpak" else "natif"
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'echo "=========================================="',
        'echo " Hub Utilitaires — vérification MAJ"',
        'echo "=========================================="',
        "echo",
        f'echo "Version locale : {current}"',
        f'echo "Canal         : {canal}"',
        "echo",
    ]
    if error:
        lines += [
            'echo "Résultat : ÉCHEC"',
            f"echo {_shell_quote(error)}",
            "echo",
        ]
    elif info is None:
        lines += [
            'echo "Résultat : déjà à jour."',
            "echo",
        ]
    else:
        latest = str(info.get("version") or "?")
        notes = str(info.get("notes") or "").strip()
        update_script = write_update_script(info)
        q_upd = _shell_quote(str(update_script.resolve()))
        flag = updates_dir() / "proceed-install"
        q_flag = _shell_quote(str(flag.resolve()))
        try:
            flag.unlink(missing_ok=True)
        except OSError:
            pass
        lines += [
            f'echo "Résultat : mise à jour {latest} disponible."',
            "echo",
        ]
        if notes:
            lines += [f"echo {_shell_quote(notes)}", "echo"]
        lines += [
            'echo "Installation dans ce terminal (recommandé)."',
            'read -r -p "Installer maintenant ? [O/n] " ans || true',
            'ans="${ans:-O}"',
            'if [[ "${ans}" == [nN]* ]]; then',
            '  echo "Annulé."',
            "  exit 0",
            "fi",
            f"touch {q_flag}",
            "echo",
            'echo "L\'application va se fermer, puis installation…"',
            "sleep 1",
            f"bash {q_upd}",
            "echo",
        ]
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    script.chmod(0o755)
    return script


def write_update_script(info: dict[str, Any]) -> Path:
    """Write a visible bash updater that downloads, installs, then relaunches."""
    url = _require_allowed_url(str(info.get("download_url") or "").strip(), kind="download")
    channel: Channel = "flatpak"
    raw_ch = str(info.get("channel") or update_channel())
    if raw_ch in ("flatpak", "native"):
        channel = raw_ch  # type: ignore[assignment]
    version = str(info.get("version") or "?").strip() or "?"
    if parse_semver(version) is None:
        raise UpdateError("Version de mise à jour invalide")
    dest = updates_dir() / _asset_name(channel, version)
    script = updates_dir() / "run-update.sh"
    # /tmp — never extract under ~/.local/share/hub-utilitaires (rsync self-delete).
    work = Path(tempfile.gettempdir()) / f"kit-update-{version}"
    curl = (
        "curl -fL --proto '=https' --tlsv1.2 "
        f"--max-filesize {_MAX_BUNDLE_BYTES} --progress-bar -o "
        f"{_shell_quote(str(dest))} {_shell_quote(url)}"
    )

    if channel == "flatpak":
        shortcut_url = SHORTCUT_DIRECT.format(version=version)
        shortcut_dest = updates_dir() / SHORTCUT_ASSET
        body = f"""#!/usr/bin/env bash
set -euo pipefail
echo "=========================================="
echo " Hub Utilitaires — mise à jour Flatpak {version}"
echo "=========================================="
echo
echo "==> Téléchargement…"
{curl}
echo
echo "==> Installation Flatpak (utilisateur)…"
flatpak install --user -y {_shell_quote(str(dest))}
echo
echo "==> Raccourci menu…"
curl -fL --proto '=https' --tlsv1.2 --max-filesize {_MAX_BUNDLE_BYTES} -o {_shell_quote(str(shortcut_dest))} {_shell_quote(shortcut_url)}
bash {_shell_quote(str(shortcut_dest))}
echo
echo "==> Relance de l'application…"
nohup flatpak run {APP_ID} >/dev/null 2>&1 &
sleep 1
echo
echo "OK — Hub Utilitaires {version} installé."
echo "Vous pouvez fermer ce terminal."
"""
    else:
        body = f"""#!/usr/bin/env bash
set -euo pipefail
echo "=========================================="
echo " Hub Utilitaires — mise à jour native {version}"
echo "=========================================="
echo
echo "==> Téléchargement…"
{curl}
echo
echo "==> Extraction…"
rm -rf {_shell_quote(str(work))}
mkdir -p {_shell_quote(str(work))}
tar -xzf {_shell_quote(str(dest))} -C {_shell_quote(str(work))}
ROOT="$(find {_shell_quote(str(work))} -maxdepth 2 -type f -name install.sh | head -n1 | xargs -r dirname)"
if [[ -z "${{ROOT}}" || ! -f "${{ROOT}}/install.sh" ]]; then
  echo "ERREUR : install.sh introuvable dans l'archive." >&2
  exit 1
fi
echo "==> Installation (install.sh --skip-deps)…"
bash "${{ROOT}}/install.sh" --skip-deps
rm -rf {_shell_quote(str(work))}
echo
echo "==> Relance de l'application…"
if command -v hub-utilitaires >/dev/null 2>&1; then
  nohup hub-utilitaires >/dev/null 2>&1 &
elif [[ -x "$HOME/.local/bin/hub-utilitaires" ]]; then
  nohup "$HOME/.local/bin/hub-utilitaires" >/dev/null 2>&1 &
elif [[ -f "$HOME/.local/share/hub-utilitaires/LANCER.sh" ]]; then
  nohup bash "$HOME/.local/share/hub-utilitaires/LANCER.sh" >/dev/null 2>&1 &
else
  echo "ATTENTION : lanceur introuvable — relancez manuellement hub-utilitaires."
fi
sleep 1
echo
echo "OK — Hub Utilitaires {version} installé."
echo "Vous pouvez fermer ce terminal."
"""

    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)
    return script


def _terminal_commands(script: Path) -> list[list[str]]:
    path = str(script.resolve())
    hold = (
        f"bash {_shell_quote(path)}; echo; "
        "echo 'Appuyez sur Entrée pour fermer…'; read -r _ || true"
    )
    hold_q = _shell_quote(hold)
    # Prefer Konsole so the user always sees check/install progress.
    return [
        ["konsole", "--hide-menubar", "-e", "bash", "-lc", hold],
        ["xdg-terminal-exec", "--", "bash", "-lc", hold],
        ["gnome-terminal", "--", "bash", "-lc", hold],
        ["kgx", "-e", "bash", "-lc", hold],
        ["xfce4-terminal", "-e", f"bash -lc {hold_q}"],
        ["mate-terminal", "-e", f"bash -lc {hold_q}"],
        ["xterm", "-hold", "-e", "bash", path],
    ]


def _maybe_host(cmd: list[str]) -> list[str]:
    if not host.is_flatpak():
        return cmd
    home = str(Path.home())
    return ["flatpak-spawn", "--host", f"--directory={home}", "--", *cmd]


def open_terminal_script(script: Path) -> None:
    """Open Konsole (or another terminal) running the script; do not wait for exit."""
    last_err = "aucun terminal trouvé"
    for cmd in _terminal_commands(script):
        wrapped = _maybe_host(cmd)
        probe = wrapped[0]
        if probe not in {"flatpak-spawn", "xdg-terminal-exec"}:
            if host.which(probe) is None:
                continue
        try:
            proc = subprocess.Popen(
                wrapped,
                start_new_session=True,
                cwd=str(Path.home()),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            last_err = str(exc)
            continue
        time.sleep(0.35)
        code = proc.poll()
        if code in (None, 0):
            return
        last_err = f"{probe} code {code}"
    raise UpdateError(
        "Impossible d'ouvrir Konsole pour suivre la mise à jour "
        f"({last_err}). Installez konsole."
    )


def launch_check_terminal(
    *,
    info: dict[str, Any] | None = None,
    error: str | None = None,
) -> Path:
    """Show update-check result in Konsole; may install if the user confirms."""
    script = write_check_report_script(info=info, error=error)
    open_terminal_script(script)
    return script


def launch_update_terminal(info: dict[str, Any]) -> Path:
    """Prepare and open the update terminal; caller should quit the app."""
    script = write_update_script(info)
    open_terminal_script(script)
    return script
