#!/usr/bin/env bash
# Publie le tar.gz NATIF sur le repo PUBLIC linux-releases.
# N'écrase jamais les tags Gest / Crypto Tracker.
#
# Usage :
#   bash packaging/publish-to-linux-releases.sh
#   bash packaging/publish-to-linux-releases.sh dist/MrAurevoX_Kit-0.1.0.tar.gz
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_REPO="Mr-Aurevo-X/linux-releases"

FROM_DIR=""
FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-dir)
      FROM_DIR="${2:?}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,8p' "$0"
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
Hub Utilitaires ${VERSION} — archive native + install.sh.

\`\`\`bash
curl -fL -O https://github.com/${PUBLIC_REPO}/releases/download/${TAG}/MrAurevoX_Kit-${VERSION}.tar.gz
tar -xzf MrAurevoX_Kit-${VERSION}.tar.gz
cd MrAurevoX_Kit-${VERSION}
bash install.sh
\`\`\`

Launcher : hub-utilitaires
Données : ~/.config/hub-utilitaires/  ~/.local/share/hub-utilitaires/
Canal Flatpak : https://github.com/Mr-Aurevo-X/linux-flatpak-releases

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
  done < <(find "${FROM_DIR}" -type f \( -name 'MrAurevoX_Kit-*.tar.gz' -o -name 'MrAurevoX_Kit-*.tar.gz.sha256' \) -print0)
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  candidate="${ROOT}/dist/MrAurevoX_Kit-${VERSION}.tar.gz"
  if [[ -f "${candidate}" ]]; then
    FILES+=("${candidate}")
  fi
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "ERREUR : aucun tar.gz Kit à publier (make dist)."
  exit 1
fi

for f in "${FILES[@]}"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERREUR : fichier introuvable : ${f}"
    exit 1
  fi
  case "${f}" in
    *.flatpak)
      echo "ERREUR : ${f} est un Flatpak → publish-to-linux-flatpak-releases.sh"
      exit 1
      ;;
    *Gest*|*crypto-tracker*|*CryptoTracker*)
      echo "ERREUR : refus de publier un asset Gest/Crypto depuis le script Kit : ${f}"
      exit 1
      ;;
  esac
done

if [[ -f "${ROOT}/LEGAL.md" ]]; then
  FILES+=("${ROOT}/LEGAL.md")
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
echo "Les tags Gest_Linux_Pro-v* et crypto-tracker-v* n'ont pas été touchés."
