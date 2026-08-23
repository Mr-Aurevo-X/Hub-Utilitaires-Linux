# Compatibilité Hub Utilitaires

## Deux canaux publics

| Canal | Repo | Assets | Garantie |
| --- | --- | --- | --- |
| Flatpak (recommandé) | [linux-flatpak-releases](https://github.com/Mr-Aurevo-X/linux-flatpak-releases) | `org.mraurevox.HubUtilitaires.flatpak` | Même UI sur Mint, Ubuntu, Fedora, Arch, CachyOS, openSUSE (runtime Flathub GNOME 49) ; **MAJ auto** |
| Natif | [linux-releases](https://github.com/Mr-Aurevo-X/linux-releases) | `MrAurevoX_Kit-*.tar.gz` | Paquets de **votre** distro via `install.sh` ; **MAJ auto** (`install.sh --skip-deps`) |

Le dépôt source `Hub-Utilitaires` reste **privé**. Ces hubs hébergent aussi Crypto Tracker et Gest Linux Pro.

## Flatpak — prérequis

- Flatpak + remote Flathub
- Runtime `org.gnome.Platform//49`
- Accès `$HOME` (recherche / carte disque). Pas de `--filesystem=host`.
- Pillow, pypdf, PyYAML, segno bundlés dans le `.flatpak`

## Natif — `install.sh`

| Famille | Détection | Paquets principaux |
| --- | --- | --- |
| Debian / Ubuntu / Mint | `apt-get` | `python3` `python3-gi` `python3-venv` `python3-pip` GTK4 Adw `python3-pil` `python3-yaml` (+ `python3-pypdf` / `python3-segno` si le dépôt les a) |
| Fedora / RHEL | `dnf` | `python3-gobject` `gtk4` `libadwaita` `python3-pillow` `python3-pypdf` `python3-pyyaml` `python3-segno` |
| Arch / CachyOS / Manjaro | `pacman` | `python-gobject` `gtk4` `libadwaita` `python-pillow` `python-pypdf` `python-yaml` `python-segno` |
| openSUSE | `zypper` | `python3-gobject` Adw `python3-Pillow` `python3-pypdf` `python3-PyYAML` `python3-segno` |
| Alpine | `apk` | `py3-gobject3` `py3-pillow` `py3-pypdf` `py3-yaml` `py3-segno` |

Si `python-segno` manque (Arch/CachyOS) ou `python3-pypdf` / `python3-segno` (Mint 21 / Ubuntu 22.04) : `install.sh` crée `~/.local/share/hub-utilitaires/.venv` (`--system-site-packages`) et pip y installe pypdf / PyYAML / segno. Sinon Flatpak (paquet complet). Distro sans GTK4 → Flatpak uniquement.

## Linux Mint 21.3 (Virginia / Jammy) — natif

Profil cible : glibc 2.35, Python 3.10.12, GTK 4.6, libadwaita 1.1, OpenSSL 3.0.2.

| Point | Natif Mint 21.3 | Kit |
| --- | --- | --- |
| Python 3.10 | OK (`list[]`, `X \| Y`) | 3.10 minimum |
| GTK 4.6 | pas de `Gtk.FileDialog` / `ColorDialog` (4.10) | `FileChooserNative` / `ColorChooserNative` |
| libadwaita 1.1 | pas de `NavigationSplitView` / `ToolbarView` / `SwitchRow` / `AlertDialog` / `ViewStack` (1.4) | `Gtk.Box` + `HeaderBar` + `MessageDialog` / `Switch` / `Gtk.Stack` |
| `python3-pypdf` / `python3-segno` | absents | venv pip (`pypdf>=5.1,<7`, `segno>=1.6,<2`) |
| Pillow | `python3-pil` 9.x | suffisant (Flatpak bundle 12) |
| `libEGL warning: DRI2: failed to authenticate` puis `exit=0` | VM / Cinnamon : GSK GL + instance D-Bus unique | cairo + `GDK_BACKEND=x11` + llvmpipe + `NO_AT_BRIDGE` + `NON_UNIQUE` + `hold()` |

**Recommandé sur Mint 21.3 :** Flatpak (`org.gnome.Platform//49`) — même UI que CachyOS, indépendant de GTK 4.6 hôte.

Natif : `bash install.sh` (installe `python3-venv` puis le venv pypdf/segno).

Pins pip (Sonatype MCP indisponible au moment du pin) : `pypdf>=5.1,<7` (BSD), `PyYAML>=6.0.1,<7` (MIT), `segno>=1.6,<2` (BSD), `Pillow>=10,<13` (Flatpak ; natif Jammy = Pillow 9 distro). Arch extra a `python-pypdf` 6.x (`<7` OK).

## Permissions Flatpak (volontairement limitées)

- Réseau : **uniquement** pour les MAJ GitHub allowlistées
- Fichiers : `home` + XDG `hub-utilitaires`
- `flatpak-spawn --host` : terminal de MAJ (Konsole), **pas** de pont sysadmin
