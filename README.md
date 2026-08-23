# Hub Utilitaires

> **WIP** — encore en développement.  
> **WIP** — still in development.

Boîte d’outils locale Linux (GTK 4 + libadwaita). Recherche, lots, hash, images, PDF, carte disque, atelier (texte, encode, mots de passe). Rien n’est envoyé : pas de compte, pas de télémétrie.

**Version 1.1.0** · GPL-3.0-or-later · © 2026 Mr-Aurevo-X

> Dépôt **privé** : `Mr-Aurevo-X/Hub-Utilitaires-Linux`.  
> Pas de canal public. Pas de Flatpak / tar.gz hors de ce dépôt.

---

## Français

### Lancer (clone)

```bash
bash LANCER.sh
```

Release interne : tag `v1.1.0` sur ce dépôt (assets pour le propriétaire / collaborateurs).

### Fonctions

- **Explorateur** — recherche (contenu, replace, regex), renommer, lots (doublons, liens docs, EOL, fichiers vides), carte disque cliquable
- **Média** — hash (fichier / dossier / SHA256SUMS), images (batch, EXIF), PDF (fusion, inventaire, extraire)
- **Fichier** — inspect, liens symboliques, zip/tar, diff d’archives
- **Studio** — pipette, atelier (texte, JWT décodage local uniquement, générateur, mots de passe PIN / phrase)

### Confidentialité

100 % local. **Pas de télémétrie.** Les outils métier n’ouvrent aucune connexion. La seule option réseau est la vérification GitHub au démarrage (activée par défaut, désactivable). Pas d’installation automatique : uniquement des commandes à copier-coller.

Données : `~/.config/hub-utilitaires/` · `~/.local/share/hub-utilitaires/`

Licence et mentions : [LEGAL.md](LEGAL.md) · [LICENSE](LICENSE)

---

## English

Local Linux toolkit (GTK 4 + libadwaita). Search, batch jobs, hash, images, PDF, disk map, workshop (text, encode, passwords). Nothing is uploaded: no account, no telemetry.

**Version 1.1.0** · GPL-3.0-or-later · © 2026 Mr-Aurevo-X

> **Private** repo: `Mr-Aurevo-X/Hub-Utilitaires-Linux`.  
> No public channel. No Flatpak / tarball outside this repo.

### Run (clone)

```bash
bash LANCER.sh
```

Internal release: tag `v1.1.0` on this repo (assets for the owner / collaborators).

### Features

- **Explorer** — search (content, replace, regex), rename, batches (dupes, doc links, EOL, empty files), clickable disk map
- **Media** — hash (file / folder / SHA256SUMS), images (batch, EXIF), PDF (merge, inventory, extract)
- **File** — inspect, symlinks, zip/tar, archive member diff
- **Studio** — color picker, workshop (text, local JWT decode only, generators, PIN / passphrase)

### Privacy

Local-first. **No telemetry.** Tools stay offline. Optional GitHub update check at startup (on by default, can be disabled). No auto-install: copy-paste commands only.

Data: `~/.config/hub-utilitaires/` · `~/.local/share/hub-utilitaires/`

Legal: [LEGAL.md](LEGAL.md) · [LICENSE](LICENSE)

---

Copyright © 2026 Mr-Aurevo-X
