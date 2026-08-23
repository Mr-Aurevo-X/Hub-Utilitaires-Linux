#!/usr/bin/env bash
# Publie le .flatpak Hub Utilitaires sur le dépôt public Mr-Aurevo-X/Hub Utilitaires.
#
# Usage :
#   bash packaging/publish-flatpak-release.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_REPO="Mr-Aurevo-X/Hub-Utilitaires-Linux"
APP_ID="org.mraurevox.HubUtilitaires"

FROM_DIR=""
FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-dir)
      FROM_DIR="${2:?}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,7p' "$0"
      exit 0
      ;;
    *)
      FILES+=("$1")
      shift
      ;;
  esac
done

VERSION="$(tr -d '[:space:]' < "${ROOT}/VERSION" 2>/dev/null || true)"
if [[ -z "${VERSION}" ]]; then
  echo "ERREUR : VERSION introuvable."
  exit 1
fi

TAG="Hub-Utilitaires-v${VERSION}"
TITLE="Hub Utilitaires ${VERSION}"
LEGAL_NOTES=""
if [[ -f "${ROOT}/packaging/public-legal-notes.md" ]]; then
  LEGAL_NOTES="$(cat "${ROOT}/packaging/public-legal-notes.md")"
fi
NOTES="$(cat <<EOF
## Hub Utilitaires ${VERSION}

Barre de titre (MAJ · Préférences · À propos · $), notification MAJ avec commandes copiables.

\`\`\`bash
curl -fL -o ${APP_ID}.flatpak \\
  https://github.com/${PUBLIC_REPO}/releases/download/${TAG}/${APP_ID}.flatpak
flatpak install --user -y --reinstall ./${APP_ID}.flatpak
curl -fL -o INSTALLER-RACCOURCI-FLATPAK.sh \\
  https://github.com/${PUBLIC_REPO}/releases/download/${TAG}/INSTALLER-RACCOURCI-FLATPAK.sh
bash ./INSTALLER-RACCOURCI-FLATPAK.sh
flatpak run ${APP_ID}
\`\`\`

Données : \`~/.config/hub-utilitaires/\`  \`~/.local/share/hub-utilitaires/\`

${LEGAL_NOTES}
EOF
)"

if [[ -n "${FROM_DIR}" ]]; then
  if [[ ! -d "${FROM_DIR}" ]]; then
    echo "ERREUR : dossier introuvable : ${FROM_DIR}"
    exit 1
  fi
  while IFS= read -r -d '' f; do
    FILES+=("$f")
  done < <(find "${FROM_DIR}" -type f -name "${APP_ID}*.flatpak" -print0)
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  unversioned="${ROOT}/dist/${APP_ID}.flatpak"
  versioned="${ROOT}/dist/${APP_ID}-${VERSION}.flatpak"
  if [[ ! -f "${unversioned}" && -f "${versioned}" ]]; then
    cp "${versioned}" "${unversioned}"
  fi
  if [[ -f "${unversioned}" ]]; then
    FILES+=("${unversioned}")
  fi
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "ERREUR : aucun .flatpak à publier (make flatpak)."
  exit 1
fi

for f in "${FILES[@]}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERREUR : fichier introuvable : ${f}"
    exit 1
  fi
  case "${f}" in
    *.flatpak) ;;
    *)
      echo "ERREUR : ${f} n'est pas un .flatpak"
      exit 1
      ;;
  esac
  base="$(basename "${f}")"
  case "${base}" in
    org.mraurevox.GestLinuxPro*|org.mraurevox.CryptoTracker*)
      echo "ERREUR : refus de publier un asset Gest/Crypto depuis le script Kit : ${f}"
      exit 1
      ;;
  esac
done

if [[ -f "${ROOT}/LEGAL.md" ]]; then
  FILES+=("${ROOT}/LEGAL.md")
fi

if [[ -f "${ROOT}/INSTALLER-RACCOURCI-FLATPAK.sh" ]]; then
  FILES+=("${ROOT}/INSTALLER-RACCOURCI-FLATPAK.sh")
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERREUR : GitHub CLI (gh) introuvable."
  exit 1
fi

if [[ -z "${GH_TOKEN:-}" ]] && ! gh auth status >/dev/null 2>&1; then
  echo "ERREUR : gh auth login"
  exit 1
fi

echo "==> Public ${PUBLIC_REPO}  tag=${TAG}"
printf '    %s\n' "${FILES[@]}"

if gh release view "${TAG}" -R "${PUBLIC_REPO}" >/dev/null 2>&1; then
  gh release upload "${TAG}" "${FILES[@]}" -R "${PUBLIC_REPO}" --clobber
  gh release edit "${TAG}" -R "${PUBLIC_REPO}" --title "${TITLE}" --notes "${NOTES}"
else
  gh release create "${TAG}" "${FILES[@]}" -R "${PUBLIC_REPO}" \
    --title "${TITLE}" --notes "${NOTES}"
fi

echo "OK → https://github.com/${PUBLIC_REPO}/releases/tag/${TAG}"
