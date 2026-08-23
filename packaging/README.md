# Packaging Hub Utilitaires

- `make dist` → `dist/MrAurevoX_Kit-<version>.tar.gz` (nom de fichier historique du canal linux-releases ; produit = Hub Utilitaires)
- `make flatpak` → `dist/org.mraurevox.HubUtilitaires.flatpak`
- `bash packaging/publish-to-linux-releases.sh` — **nouveau** tag `Hub-Utilitaires-v*` uniquement
- `bash packaging/publish-to-linux-flatpak-releases.sh` — idem, canal Flatpak
- `bash packaging/sync-public-readmes.sh` — README hubs (Crypto Tracker + Gest + Hub Utilitaires)

Ne jamais `gh release delete` sur Gest / Crypto Tracker.
