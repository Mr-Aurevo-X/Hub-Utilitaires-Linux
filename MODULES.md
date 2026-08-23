# Modules Hub Utilitaires

Inventaire métier. Pas de code mort ici — idées et mapping seulement.

## Navigation

Sidebar **repliable** en 4 sections (`ui/nav.py`) : Explorateur · Média & intégrité · Fichier · Studio.

| Groupe | Pages |
| --- | --- |
| Explorateur | Recherche, Renommer, Lots, Carte |
| Média & intégrité | Hash, Images, PDF |
| Fichier | Fichier (inspect + archive) |
| Studio | Pipette, Atelier |

Préférences = dialogue chrome (`Ctrl+,`), pas une entrée sidebar.

## Déjà dans le hub (ne pas recoder)

| Idée | Où c’est |
| --- | --- |
| Recherche fichiers (+ export CSV/JSON, replace aperçu) | Page Recherche |
| Hash un-fichier + compare A/B + dossiers + SHA256SUMS | Page Hash |
| Manifeste `.sha256` (écrire / vérifier) | Hash + Lots |
| Images batch + icônes PNG + EXIF rotate + compare | Page Images |
| Strip EXIF / GPS | Images (case EXIF) |
| Renommer (`{hash8}`, presets, CSV, undo) | Page Renommer |
| PDF (fusion, pages, inventaire CSV, extraire images) | Page PDF |
| Carte disque + treemap | Page Carte |
| PrettyJSON / minify / JSONL / JWT / `.env` inspect | Atelier → Encode |
| LineEndings CRLF ↔ LF (fichier) | Atelier → Texte ; Fichier → réécrire LF |
| Audit EOL / encodage (dossier) | Lots → Plus |
| ArchivePeek + create zip/tar.gz + **diff membres** | Fichier → Archive |
| UuidGen / PassGen / DummyFile / DesktopMaker / Qr / Cron / Gitignore | Atelier → Générer |
| MdPreview | Atelier → Aperçu |
| Unités / devises / epoch | Atelier Générer |
| Color picker + palette + historique session | Page Pipette |
| CsvTools fusion / coupe | Atelier → Données |
| Broken **symlinks** + TrashPeek + stats + dupes | Lots |
| Broken **doc links** locaux (MD/HTML, pas HTTP) | Lots → Plus |
| Quasi-doublons images (W×H×octets) | Lots → Plus |
| MimeGuess (magic bytes) | Fichier → Inspect |
| Dossiers récents / favoris + recherches épinglées | FolderBar / Recherche |
| Journal opérations | `core/opslog.py` + Préférences |
| Palette commandes Ctrl+K | Fenêtre principale (saut de page) |

## Hubs frères (ne pas recâbler ici)

| Outil | Hub |
| --- | --- |
| Diff texte (page dédiée) | Hub-Dev — envoi via `core/cross_hub.py` |
| Snippets | Hub-Dev |
| SecretScan (UI) | Hub-Sécurité |

`core/secretscan.py` et `core/snippets.py` restent des libs testées **sans page**.

## Interdit

Cleaner système, find-everything dédié, PortWho, LAN/WOL, overlap Gest, historique presse-papiers (CopyQ), clone outils Windows dédiés hors cas ci-dessus.
