# Hub Utilitaires

> **WIP** — encore en développement.  
> **WIP** — still in development.

Boîte d’outils locale Linux (GTK 4 + libadwaita). Recherche, lots, hash, images, PDF, carte disque, atelier (texte, encode, mots de passe). Rien n’est envoyé : pas de compte, pas de télémétrie.

**1.1.2** — [releases](https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux/releases) · GPL-3.0-or-later · © 2026 Mr-Aurevo-X

---

## Français

### Installer (Flatpak)

Prérequis : [Flatpak](https://flatpak.org/setup/) + runtime GNOME 49 (installé automatiquement depuis Flathub au premier `flatpak install`).

```bash
wget -O org.mraurevox.HubUtilitaires.flatpak \
  https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux/releases/download/v1.1.2/org.mraurevox.HubUtilitaires.flatpak
flatpak install --user -y --reinstall ./org.mraurevox.HubUtilitaires.flatpak
wget -O INSTALLER-RACCOURCI-FLATPAK.sh \
  https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux/releases/download/v1.1.2/INSTALLER-RACCOURCI-FLATPAK.sh
bash ./INSTALLER-RACCOURCI-FLATPAK.sh
flatpak run org.mraurevox.HubUtilitaires
```

Dev sans installer : `bash LANCER.sh`

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

### Install (Flatpak)

```bash
wget -O org.mraurevox.HubUtilitaires.flatpak \
  https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux/releases/download/v1.1.2/org.mraurevox.HubUtilitaires.flatpak
flatpak install --user -y --reinstall ./org.mraurevox.HubUtilitaires.flatpak
wget -O INSTALLER-RACCOURCI-FLATPAK.sh \
  https://github.com/Mr-Aurevo-X/Hub-Utilitaires-Linux/releases/download/v1.1.2/INSTALLER-RACCOURCI-FLATPAK.sh
bash ./INSTALLER-RACCOURCI-FLATPAK.sh
flatpak run org.mraurevox.HubUtilitaires
```

Dev without install: `bash LANCER.sh`

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

## Soutien (optionnel) / Support (optional)

Si le boulot te plaît, un café — sinon profite.  
If you like the work, a coffee — otherwise just enjoy it.

[![Discord](https://img.shields.io/badge/Discord-Mr--Aurevo--X-5865F2?style=for-the-badge&logo=discord&logoColor=white&labelColor=050807)](https://discord.com/users/406891052516114442)
[![PayPal](https://img.shields.io/badge/PayPal-Donate-39ff14?style=for-the-badge&logo=paypal&logoColor=00f0ff&labelColor=050807)](https://www.paypal.com/paypalme/aurevo1)
[![Revolut](https://img.shields.io/badge/Revolut-mr__aurevo__x-00f0ff?style=for-the-badge&logo=revolut&logoColor=39ff14&labelColor=050807)](https://revolut.me/mr_aurevo_x)

---

Copyright © 2026 Mr-Aurevo-X — GPL-3.0-or-later
