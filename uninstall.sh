#!/usr/bin/env bash
# Hub Utilitaires — desinstallation (chemins utilisateur)
# SPDX-License-Identifier: GPL-3.0-or-later
set -euo pipefail

APP_ID="hub-utilitaires"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_DIR="${HOME}/.local/bin"
INSTALL_DIR="${DATA_HOME}/${APP_ID}"
APPS_DIR="${DATA_HOME}/applications"
DESKTOP_DST="${APPS_DIR}/${APP_ID}.desktop"
LAUNCHER="${BIN_DIR}/${APP_ID}"
DESKTOP_ALT="${APPS_DIR}/Hub-Utilitaires.desktop"
ICON_DST="${DATA_HOME}/icons/hicolor/128x128/apps/org.mraurevox.HubUtilitaires.png"

echo "Desinstallation de Hub Utilitaires…"

if [[ -d "${INSTALL_DIR}" ]]; then
  rm -rf "${INSTALL_DIR}"
  echo "  Supprime : ${INSTALL_DIR}"
else
  echo "  (absent) ${INSTALL_DIR}"
fi

if [[ -f "${LAUNCHER}" ]] || [[ -L "${LAUNCHER}" ]]; then
  rm -f "${LAUNCHER}"
  echo "  Supprime : ${LAUNCHER}"
fi

for desk in "${DESKTOP_DST}" "${DESKTOP_ALT}"; do
  if [[ -f "${desk}" ]]; then
    rm -f "${desk}"
    echo "  Supprime : ${desk}"
  fi
done

if [[ -f "${ICON_DST}" ]]; then
  rm -f "${ICON_DST}"
  echo "  Supprime : ${ICON_DST}"
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "${APPS_DIR}" 2>/dev/null || true
fi

echo "OK — desinstalle."
echo "Les paquets systeme (python3-gi, GTK4, Pillow) ne sont pas retires."
echo "Les preferences (~/.config/hub-utilitaires/) sont conservees."
