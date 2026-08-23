# Hub Utilitaires — empaquetage
APP_NAME := MrAurevoX_Kit
VERSION  := $(shell tr -d '[:space:]' < VERSION 2>/dev/null || echo 1.0.0)
DIST_DIR := dist
TARBALL  := $(DIST_DIR)/$(APP_NAME)-$(VERSION).tar.gz

.PHONY: help dist flatpak clean version test

help:
	@echo "Cibles :"
	@echo "  make test     -> pytest"
	@echo "  make dist     -> $(TARBALL)"
	@echo "  make flatpak  -> dist/org.mraurevox.HubUtilitaires-$(VERSION).flatpak + asset public"
	@echo "  make clean    -> nettoie dist/"
	@echo "  make version  -> affiche la version"

version:
	@echo $(VERSION)

test:
	python3 -m pytest -q

dist:
	@mkdir -p $(DIST_DIR)
	@rm -f $(TARBALL)
	tar -czf $(TARBALL) \
		--exclude='.git' \
		--exclude='.cursor' \
		--exclude='venv' \
		--exclude='.venv' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='dist' \
		--exclude='.pytest_cache' \
		--exclude='graphify-out' \
		--transform 's,^\./,$(APP_NAME)-$(VERSION)/,' \
		./VERSION ./LICENSE ./COPYRIGHT ./LEGAL.md ./README.md ./MODULES.md ./requirements.txt ./main.py \
		./install.sh ./uninstall.sh ./LANCER.sh ./INSTALLER-RACCOURCI.sh \
		./Hub-Utilitaires.desktop ./Makefile ./MANIFEST \
		./core ./ui ./ui_kit ./packaging
	@echo "OK -> $(TARBALL)"
	@ls -lh $(TARBALL)

flatpak:
	bash packaging/build-flatpak.sh

clean:
	rm -rf $(DIST_DIR)/flatpak-build $(DIST_DIR)/flatpak-repo
	rm -f $(DIST_DIR)/$(APP_NAME)-*.tar.gz $(DIST_DIR)/$(APP_NAME)-*.tar.gz.sha256
	rm -f $(DIST_DIR)/org.mraurevox.HubUtilitaires-*.flatpak
	rm -f $(DIST_DIR)/org.mraurevox.HubUtilitaires.flatpak
