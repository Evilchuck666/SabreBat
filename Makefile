.PHONY: help build install uninstall clean clean-pkgs aur arch test

help:
	@echo "Available targets:"
	@echo "  arch         Build and install the pacman package from arch/PKGBUILD"
	@echo "  aur          Build and install the AUR package from AUR/"
	@echo "  build        Build the SabreBat wheel into PKGs/"
	@echo "  clean        Remove build artifacts"
	@echo "  clean-pkgs   Remove all generated wheel files from PKGs/"
	@echo "  install      Build and install the SabreBat wheel"
	@echo "  test         Run the unit tests against src/"
	@echo "  uninstall    Uninstall the SabreBat package"

arch:
	cd arch && makepkg -si
	rm -rf arch/src arch/pkg arch/SabreBat arch/*.pkg.tar*

aur:
	cd AUR && makepkg -si
	rm -rf AUR/src AUR/pkg AUR/*.pkg.tar.zst AUR/SabreBat

build:
	python -m build --wheel
	mkdir -p PKGs
	mv dist/*.whl PKGs/
	$(MAKE) clean

clean:
	rm -rf dist/ build/ src/SabreBat.egg-info/

clean-pkgs:
	rm -rf PKGs/

install:
	$(MAKE) build
	pip install --break-system-packages PKGs/sabrebat-*.whl

test:
	PYTHONPATH=src python -m unittest discover -s tests -v

uninstall:
	pip uninstall -y SabreBat --break-system-packages
