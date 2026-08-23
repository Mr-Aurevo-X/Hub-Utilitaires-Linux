#!/usr/bin/env bash
# Crée un raccourci Bureau qui lance correctement l'app (partage noexec).
set -e
SHARE="$(cd "$(dirname "$0")" && pwd)"
if [[ ! -f "$SHARE/LANCER.sh" || ! -f "$SHARE/main.py" ]]; then
  echo "ERREUR : ce script doit être lancé depuis le dossier Hub Utilitaires."
  echo "  Trouvé : $SHARE"
  echo "  Déjà dans le dossier : bash INSTALLER-RACCOURCI.sh"
  exit 1
fi
DESKTOP="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
[[ -d "$DESKTOP" ]] || DESKTOP="$HOME/Bureau"
[[ -d "$DESKTOP" ]] || DESKTOP="$HOME"

OUT="$DESKTOP/Hub-Utilitaires.desktop"

cat > "$OUT" << EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Hub Utilitaires
Comment=Boîte d'outils locale (recherche, pipette, hash, images)
Exec=bash "$SHARE/LANCER.sh"
Path=$SHARE
Icon=org.mraurevox.HubUtilitaires
Terminal=true
Categories=Utility;GTK;
StartupNotify=true
EOF

chmod +x "$OUT"
gio set "$OUT" metadata::trusted true 2>/dev/null || true

echo "Raccourci créé : $OUT"
echo "Double-clique CE fichier sur le Bureau (pas le .sh du partage)."
