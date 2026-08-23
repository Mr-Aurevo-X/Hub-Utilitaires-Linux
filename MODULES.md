# Modules Hub Utilitaires

Inventaire métier. Pas de code mort ici — idées et mapping seulement.

## Navigation (2.3)

Sidebar **repliable** en 5 sections : Explorateur · Média & intégrité · Fichier · Studio · Audit (`ui/nav_sidebar.py`).

## Déjà dans le Kit (ne pas recoder / ne pas cloner)

| Idée brief | Où c’est |
| --- | --- |
| Recherche fichiers (+ export CSV/JSON) | Page Recherche |
| Hash un-fichier + compare A/B + dossiers + SHA256SUMS | Page Hash |
| Manifeste `.sha256` (écrire) | Hash + Lots |
| Vérifier manifeste OK / MANQUANT / DIFF | Hash |
| Images batch + icônes PNG multi-tailles + EXIF rotate + compare | Page Images |
| Strip EXIF / GPS | Images (case EXIF) |
| Renommer (+ `{hash8}`, presets, CSV) | Page Renommer |
| Undo renommage | `~/.local/share/hub-utilitaires/rename-undo.json` |
| PDF (+ réordonner pages, extraire images) | Page PDF |
| Carte disque | Page Carte |
| PrettyJSON / minify / valider | Atelier → Encode (+ `.env` inspect) |
| JSONL pretty / min / valider | Atelier → Encode |
| LineEndings CRLF ↔ LF | Atelier → Texte ; Fichier → réécrire LF |
| ArchivePeek + **create** zip/tar.gz | Fichier → Archive |
| UuidGen / PassGen / DummyFile / DesktopMaker / QrRead / Cron / Gitignore | Atelier → Générer |
| MdPreview | Atelier → Aperçu |
| QR generate | Atelier → Générer (`segno`) |
| Unités / devises / epoch | Atelier Générer |
| Color picker + export palette + historique session | Page Pipette |
| CsvTools fusion / coupe N lignes | Atelier → Données |
| TextDiff (+ ignore espaces/EOL) | Page Diff texte |
| SecretScan + export rapport | Page Secrets |
| Snippets (+ tags, import/export JSON) | Page Snippets |
| BrokenLinks | Lots |
| TrashPeek | Lots |
| MimeGuess (magic bytes) | Fichier → Inspect |
| Dossiers récents / favoris | FolderBar |
| Journal opérations | `core/opslog.py` + Préférences |
| Palette commandes Ctrl+K | Fenêtre principale |

## Interdit

Cleaner système, find-everything dédié, PortWho, LAN/WOL, overlap Gest, historique presse-papiers (CopyQ), clone outils Windows dédiés hors cas ci-dessus.
