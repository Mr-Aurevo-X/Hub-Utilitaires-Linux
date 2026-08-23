#!/usr/bin/env bash
# Lance Hub Utilitaires.
# - code sur un partage (souvent noexec) → toujours via bash + python3 système
# - GTK4 / Libadwaita / PyGObject / Pillow viennent des paquets distro
# - logs en local XDG
set +e
SHARE="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -f "$SHARE/main.py" ]]; then
  echo "ERREUR : main.py introuvable dans $SHARE"
  echo "Depuis le dossier projet : bash LANCER.sh"
  exit 1
fi
LOCAL="${XDG_DATA_HOME:-$HOME/.local/share}/hub-utilitaires"
LOG="$LOCAL/launch.log"

mkdir -p "$LOCAL"
chmod 700 "$LOCAL" 2>/dev/null || true
touch "$LOG"
chmod 600 "$LOG" 2>/dev/null || true

exec > >(tee -a "$LOG") 2>&1

echo "========== $(date) =========="
echo "SHARE=$SHARE"
echo "LOCAL=$LOCAL"
echo "DISPLAY=${DISPLAY-}"
echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE-}"
echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY-}"
echo

pause() {
  echo
  echo "Appuie sur Entrée pour fermer…"
  if [[ -r /dev/tty ]]; then
    read -r _ </dev/tty
  else
    sleep 8
  fi
}

need_pkg() {
  echo "ERREUR : dépendance manquante — $1"
  echo
  echo "Installe les paquets système adaptés à ta distribution :"
  echo "  Debian/Ubuntu : sudo apt update && sudo apt install -y python3 python3-gi python3-gi-cairo python3-venv python3-pip gir1.2-gtk-4.0 gir1.2-adw-1 python3-pil python3-yaml"
  echo "  Fedora        : sudo dnf install -y python3 python3-gobject gtk4 libadwaita python3-pillow python3-pypdf python3-pyyaml python3-segno"
  echo "  Arch/CachyOS  : sudo pacman -Sy --needed python python-gobject gtk4 libadwaita python-pillow python-pypdf python-yaml python-segno"
  echo "  openSUSE      : sudo zypper install python3 python3-gobject typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1 python3-Pillow python3-pypdf python3-PyYAML python3-segno"
  echo "  Alpine        : sudo apk add python3 py3-gobject3 gtk4.0 libadwaita py3-pillow py3-pypdf py3-yaml py3-segno"
  echo "  Mint 21.3     : python3-pypdf / python3-segno absents des dépôts — bash install.sh (venv) ou Flatpak."
  pause
  exit 1
}

command -v python3 >/dev/null || need_pkg "python3"

PY="python3"
if [[ -x "$SHARE/.venv/bin/python" ]]; then
  PY="$SHARE/.venv/bin/python"
fi

cd "$SHARE" || { pause; exit 1; }
export PYTHONPATH="$SHARE${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1

# Env GTK4 AVANT tout import Gtk (probe inclus).
while IFS= read -r line; do
  [[ -z "${line}" || "${line}" != *=* ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  export "${key}=${val}"
  echo "${key}=${val} (Mint / Jammy / VM)"
done < <("$PY" -c "from core.display_env import apply_safe_display_env
for k,v in apply_safe_display_env().items():
    print(f'{k}={v}')" 2>/dev/null || true)

"$PY" - <<'PY' || need_pkg "python3-gi / GTK4 / Libadwaita / Pillow"
import sys
if sys.version_info < (3, 10):
    print(f"Python 3.10+ requis (trouvé {sys.version.split()[0]}).", file=sys.stderr)
    sys.exit(1)
try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw  # noqa: F401
    from PIL import Image  # noqa: F401
except Exception as exc:
    print(exc, file=sys.stderr)
    sys.exit(1)
PY

"$PY" - <<'PY' || echo "ATTENTION : pypdf / PyYAML / segno manquants — PDF / YAML / QR. Paquets distro ou Flatpak (python-segno souvent absent)."
import importlib
for name in ("pypdf", "yaml", "segno"):
    importlib.import_module(name)
PY

echo "Python : $PY"
echo "Démarrage UI…"
START_TS="$(date +%s)"
"$PY" "$SHARE/main.py"
CODE=$?
END_TS="$(date +%s)"
DUR="$((END_TS - START_TS))"
echo "exit=$CODE duration=${DUR}s"
if [[ $CODE -ne 0 ]]; then
  echo "Erreur — détails dans $LOG"
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -u critical "Hub Utilitaires" "Échec du lancement. Voir ${LOG}"
  fi
  pause
  exit "$CODE"
fi
if [[ "${DUR}" -lt 2 ]]; then
  echo "ERREUR : l'UI s'est fermée tout de suite (D-Bus / fenêtre non mappée)."
  echo "Processus kit encore vivants :"
  pgrep -af -u "${USER}" 'hub-utilitaires|Hub Utilitaires/main.py' || true
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -u critical "Hub Utilitaires" "Fenêtre fermée immédiatement. Voir ${LOG}"
  fi
  pause
  exit 1
fi
exit 0
