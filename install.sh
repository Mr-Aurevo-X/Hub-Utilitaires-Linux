#!/usr/bin/env bash
# Hub Utilitaires — installation utilisateur (~/.local) + deps systeme (sudo)
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

APP_ID="hub-utilitaires"
APP_NAME="Hub Utilitaires"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION_FILE="${SCRIPT_DIR}/VERSION"
VERSION="$(tr -d '[:space:]' < "${VERSION_FILE}" 2>/dev/null || echo "1.0.0")"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="${HOME}/.local/bin"
INSTALL_DIR="${DATA_HOME}/${APP_ID}"
APPS_DIR="${DATA_HOME}/applications"
ICONS_DIR="${DATA_HOME}/icons/hicolor/128x128/apps"
DESKTOP_DST="${APPS_DIR}/${APP_ID}.desktop"
LAUNCHER="${BIN_DIR}/${APP_ID}"
ICON_DST="${ICONS_DIR}/org.mraurevox.HubUtilitaires.png"

SKIP_DEPS=0
for arg in "$@"; do
  case "$arg" in
    --skip-deps) SKIP_DEPS=1 ;;
    -h|--help)
      echo "Usage: bash install.sh [--skip-deps]"
      echo "  Installe ${APP_NAME} dans ${INSTALL_DIR}"
      echo "  Launcher : ~/.local/bin/${APP_ID}"
      exit 0
      ;;
  esac
done

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

detect_os_pretty() {
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${PRETTY_NAME:-${NAME:-Linux}} (${ID:-inconnu})"
  else
    echo "Linux (os-release absent)"
  fi
}

detect_pkg_family() {
  if need_cmd apt-get; then
    echo "apt (Debian/Ubuntu/Mint)"
  elif need_cmd dnf; then
    echo "dnf (Fedora/RHEL)"
  elif need_cmd pacman; then
    echo "pacman (Arch/CachyOS)"
  elif need_cmd zypper; then
    echo "zypper (openSUSE)"
  elif need_cmd apk; then
    echo "apk (Alpine)"
  else
    echo "aucun (apt/dnf/pacman/zypper/apk)"
  fi
}

flatpak_hint() {
  echo
  echo "Si GTK4 / Libadwaita ne sont pas disponibles sur cette distro, utilisez le Flatpak :"
  echo "  https://github.com/Mr-Aurevo-X/linux-flatpak-releases"
  echo "  (runtime Flathub org.gnome.Platform 49 — compatible toutes distros)"
}

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif need_cmd sudo; then
    sudo "$@"
  else
    echo "ERREUR : droits administrateur requis et sudo introuvable." >&2
    echo "Relancez en root ou installez sudo." >&2
    exit 1
  fi
}

install_deps_apt() {
  echo "==> Dependances systeme (apt)…"
  run_as_root apt-get update
  run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-gi \
    python3-gi-cairo \
    python3-venv \
    python3-pip \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    python3-pil \
    python3-yaml
  for pkg in python3-pypdf python3-segno; do
    run_as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y "${pkg}" \
      || echo "ATTENTION : ${pkg} absent des dépôts (Mint 21 / Jammy) — venv pip."
  done
}

install_deps_dnf() {
  echo "==> Dependances systeme (dnf)…"
  run_as_root dnf install -y \
    python3 \
    python3-gobject \
    gtk4 \
    libadwaita \
    python3-pillow \
    python3-pypdf \
    python3-pyyaml \
    python3-segno
}

install_deps_pacman() {
  echo "==> Dependances systeme (pacman)…"
  run_as_root pacman -Sy --needed --noconfirm \
    python \
    python-gobject \
    gtk4 \
    libadwaita \
    python-pillow \
    python-pypdf \
    python-yaml
  run_as_root pacman -S --needed --noconfirm python-segno \
    || echo "ATTENTION : python-segno absent des dépôts — pip --user ou Flatpak."
}

install_deps_zypper() {
  echo "==> Dependances systeme (zypper)…"
  run_as_root zypper --non-interactive install \
    python3 \
    python3-gobject \
    typelib-1_0-Gtk-4_0 \
    typelib-1_0-Adw-1 \
    python3-Pillow \
    python3-pypdf \
    python3-PyYAML \
    python3-segno
}

install_deps_apk() {
  echo "==> Dependances systeme (apk)…"
  run_as_root apk add --no-cache \
    python3 \
    py3-gobject3 \
    gtk4.0 \
    libadwaita \
    py3-pillow \
    py3-pypdf \
    py3-yaml \
    py3-segno
}

install_system_deps() {
  if [[ "${SKIP_DEPS}" -eq 1 ]]; then
    echo "==> --skip-deps : installation des paquets ignoree."
    return 0
  fi
  if need_cmd apt-get; then
    install_deps_apt
  elif need_cmd dnf; then
    install_deps_dnf
  elif need_cmd pacman; then
    install_deps_pacman
  elif need_cmd zypper; then
    install_deps_zypper
  elif need_cmd apk; then
    install_deps_apk
  else
    echo "ATTENTION : gestionnaire de paquets non detecte (apt/dnf/pacman/zypper/apk)."
    echo "Installez manuellement : python3, PyGObject, GTK4, Libadwaita, Pillow, pypdf, PyYAML, segno."
    flatpak_hint
  fi
}

verify_python_stack() {
  if ! need_cmd python3; then
    echo "ERREUR : python3 introuvable apres installation."
    flatpak_hint
    exit 1
  fi
  if ! python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    print(f"Python 3.10+ requis (trouvé {sys.version.split()[0]}).", file=sys.stderr)
    raise SystemExit(1)
try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw  # noqa: F401
    from PIL import Image  # noqa: F401
except Exception as exc:
    print(exc, file=sys.stderr)
    raise SystemExit(1)
PY
  then
    echo "ERREUR : GTK4 / Libadwaita / Pillow indisponibles pour python3."
    echo "Cause fréquente : paquets manquants ou trop anciens sur cette distro."
    echo "Relancez sans --skip-deps, ou installez les paquets listés dans packaging/COMPAT.md."
    flatpak_hint
    exit 1
  fi
}

ensure_extra_python_libs() {
  local py="python3"
  if [[ -x "${INSTALL_DIR}/.venv/bin/python" ]]; then
    py="${INSTALL_DIR}/.venv/bin/python"
  fi
  if "${py}" - <<'PY' >/dev/null 2>&1
import importlib
importlib.import_module("pypdf")
importlib.import_module("yaml")
importlib.import_module("segno")
PY
  then
    return 0
  fi
  echo "==> venv local (--system-site-packages) : pypdf / PyYAML / segno"
  if ! python3 -m venv --system-site-packages "${INSTALL_DIR}/.venv"; then
    echo "ERREUR : python3 -m venv a échoué."
    echo "  Debian/Mint/Ubuntu : sudo apt install -y python3-venv python3-pip"
    echo "  ou installez le Flatpak (chemin garanti, y compris Mint 21.3)."
    flatpak_hint
    return 0
  fi
  "${INSTALL_DIR}/.venv/bin/pip" install -q "pypdf>=5.1,<7" "PyYAML>=6.0.1,<7" "segno>=1.6,<2" || {
    echo "ATTENTION : pypdf / PyYAML / segno introuvables (PEP 668 / dépôts)."
    echo "  Arch : sudo pacman -S --needed python-pypdf python-yaml"
    echo "  Mint 21.3 : python3-pypdf / python-segno absents → Flatpak, ou pip dans le venv."
    return 0
  }
}

install_app_files() {
  echo "==> Fichiers application → ${INSTALL_DIR}"
  mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${APPS_DIR}" "${ICONS_DIR}"

  if need_cmd rsync; then
    rsync -a --delete \
      --exclude '.git/' \
      --exclude '.cursor/' \
      --exclude 'venv/' \
      --exclude '.venv/' \
      --exclude '__pycache__/' \
      --exclude '*.pyc' \
      --exclude 'dist/' \
      --exclude '.pytest_cache/' \
      --exclude 'graphify-out/' \
      --exclude 'updates/' \
      "${SCRIPT_DIR}/" "${INSTALL_DIR}/"
  else
    find "${INSTALL_DIR}" -mindepth 1 -maxdepth 1 ! -name 'updates' -exec rm -rf {} +
    for item in main.py VERSION LICENSE COPYRIGHT LEGAL.md README.md requirements.txt \
                LANCER.sh INSTALLER-RACCOURCI.sh Hub-Utilitaires.desktop \
                install.sh uninstall.sh Makefile MANIFEST \
                core ui packaging; do
      if [[ -e "${SCRIPT_DIR}/${item}" ]]; then
        cp -a "${SCRIPT_DIR}/${item}" "${INSTALL_DIR}/"
      fi
    done
    find "${INSTALL_DIR}" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
  fi

  chmod +x "${INSTALL_DIR}/LANCER.sh" \
           "${INSTALL_DIR}/install.sh" \
           "${INSTALL_DIR}/uninstall.sh" \
           "${INSTALL_DIR}/INSTALLER-RACCOURCI.sh" \
           "${INSTALL_DIR}/main.py" 2>/dev/null || true

  if [[ -f "${SCRIPT_DIR}/packaging/flatpak/org.mraurevox.HubUtilitaires.png" ]]; then
    cp -a "${SCRIPT_DIR}/packaging/flatpak/org.mraurevox.HubUtilitaires.png" "${ICON_DST}"
  fi
}

install_launcher() {
  echo "==> Launcher → ${LAUNCHER}"
  cat > "${LAUNCHER}" << EOF
#!/usr/bin/env bash
# Launcher ${APP_NAME} (installe)
set -euo pipefail
INSTALL_DIR="${INSTALL_DIR}"
export PYTHONPATH="\${INSTALL_DIR}\${PYTHONPATH:+:\$PYTHONPATH}"
exec bash "\${INSTALL_DIR}/LANCER.sh" "\$@"
EOF
  chmod +x "${LAUNCHER}"
}

install_desktop_entry() {
  echo "==> Entree bureau → ${DESKTOP_DST}"
  if [[ -f "${SCRIPT_DIR}/packaging/${APP_ID}.desktop" ]]; then
    sed -e "s|@INSTALL_DIR@|${INSTALL_DIR}|g" \
        -e "s|@LAUNCHER@|${LAUNCHER}|g" \
        "${SCRIPT_DIR}/packaging/${APP_ID}.desktop" > "${DESKTOP_DST}"
  else
    cat > "${DESKTOP_DST}" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=${APP_NAME}
Comment=Boite d'outils locale (recherche, pipette, hash, images, PDF, atelier)
Exec=${LAUNCHER}
Path=${INSTALL_DIR}
Icon=org.mraurevox.HubUtilitaires
Terminal=false
Categories=Utility;GTK;
StartupNotify=true
EOF
  fi
  chmod +x "${DESKTOP_DST}"
  if need_cmd update-desktop-database; then
    update-desktop-database "${APPS_DIR}" 2>/dev/null || true
  fi
  if need_cmd gtk-update-icon-cache; then
    gtk-update-icon-cache -f "${DATA_HOME}/icons/hicolor" 2>/dev/null || true
  fi
  if need_cmd gio; then
    gio set "${DESKTOP_DST}" metadata::trusted true 2>/dev/null || true
  fi
}

ensure_path_hint() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
      echo
      echo "Note : ${BIN_DIR} n'est pas dans votre PATH."
      echo "Ajoutez par exemple dans ~/.bashrc :"
      echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
      ;;
  esac
}

main() {
  echo "${APP_NAME} v${VERSION} — installation native"
  echo "Source : ${SCRIPT_DIR}"
  echo "Systeme : $(detect_os_pretty)"
  echo "Paquets : $(detect_pkg_family)"
  [[ -f "${SCRIPT_DIR}/main.py" ]] || {
    echo "ERREUR : main.py introuvable. Lancez depuis le dossier extrait / clone."
    exit 1
  }

  install_system_deps
  verify_python_stack
  install_app_files
  ensure_extra_python_libs
  install_launcher
  install_desktop_entry
  ensure_path_hint

  echo
  echo "OK — ${APP_NAME} v${VERSION} installe (pile GTK de cette distro)."
  echo "  App     : ${INSTALL_DIR}"
  echo "  Lancer  : ${APP_ID}"
  echo "  ou      : ${LAUNCHER}"
  echo "  ou      : bash ${INSTALL_DIR}/LANCER.sh"
  echo "Desinstaller : bash ${INSTALL_DIR}/uninstall.sh"
  echo "Flatpak (toutes distros) : https://github.com/Mr-Aurevo-X/linux-flatpak-releases"
}

main "$@"
