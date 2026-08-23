# Hub Utilitaires

Boîte d’outils locale Linux (GTK 4 + libadwaita). Recherche, lots, hash, images, PDF, carte disque, atelier (texte, encode, mots de passe). Rien n’est envoyé : pas de compte, pas de télémétrie.

**Version 1.1.0** · GPL-3.0-or-later · © 2026 Mr-Aurevo-X

> Le dépôt source `Mr-Aurevo-X/Hub-Utilitaires-Linux` reste **privé**.  
> Les paquets publics sont sur [linux-flatpak-releases](https://github.com/Mr-Aurevo-X/linux-flatpak-releases) et [linux-releases](https://github.com/Mr-Aurevo-X/linux-releases).

---

## Français

### Installation (publique, sans accès au source)

**Flatpak** (recommandé, toutes distros) :

```bash
curl -fL -o org.mraurevox.HubUtilitaires.flatpak \
  https://github.com/Mr-Aurevo-X/linux-flatpak-releases/releases/download/Hub-Utilitaires-v1.1.0/org.mraurevox.HubUtilitaires.flatpak
flatpak install --user -y ./org.mraurevox.HubUtilitaires.flatpak
flatpak run org.mraurevox.HubUtilitaires
```

**Natif** (paquets de votre distro + `install.sh`) :

```bash
curl -fL -O https://github.com/Mr-Aurevo-X/linux-releases/releases/download/Hub-Utilitaires-v1.1.0/MrAurevoX_Kit-1.1.0.tar.gz
tar -xzf MrAurevoX_Kit-1.1.0.tar.gz
cd MrAurevoX_Kit-1.1.0
bash install.sh
```

Le nom `MrAurevoX_Kit-*.tar.gz` est historique (canal linux-releases). Le produit est **Hub Utilitaires**.

### Dev local (clone privé)

```bash
bash LANCER.sh
```

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

> Source repo `Mr-Aurevo-X/Hub-Utilitaires-Linux` stays **private**.  
> Public packages live on [linux-flatpak-releases](https://github.com/Mr-Aurevo-X/linux-flatpak-releases) and [linux-releases](https://github.com/Mr-Aurevo-X/linux-releases).

### Install (public, no source access)

**Flatpak** (recommended):

```bash
curl -fL -o org.mraurevox.HubUtilitaires.flatpak \
  https://github.com/Mr-Aurevo-X/linux-flatpak-releases/releases/download/Hub-Utilitaires-v1.1.0/org.mraurevox.HubUtilitaires.flatpak
flatpak install --user -y ./org.mraurevox.HubUtilitaires.flatpak
flatpak run org.mraurevox.HubUtilitaires
```

**Native**:

```bash
curl -fL -O https://github.com/Mr-Aurevo-X/linux-releases/releases/download/Hub-Utilitaires-v1.1.0/MrAurevoX_Kit-1.1.0.tar.gz
tar -xzf MrAurevoX_Kit-1.1.0.tar.gz
cd MrAurevoX_Kit-1.1.0
bash install.sh
```

`MrAurevoX_Kit-*.tar.gz` is the historical linux-releases filename. The product is **Hub Utilitaires**.

### Local dev (private clone)

```bash
bash LANCER.sh
```

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
