# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SabreBat reads the battery level of the Corsair Sabre v2 Pro wireless mouse from its USB receiver (`1b1c:2b2a`) over hidraw, because neither the kernel nor UPower expose it. The `sabre-bat` CLI prints it, prints just the percentage (`-q`) or shows a dunst-styled notification (`-n`). It started as a single script in `~/.local/bin/sabre-bat`.

## Commands

```bash
# Run from the checkout (needs the receiver and the udev rule)
PYTHONPATH=src python -m sabrebat [-q | -n] [-d /dev/hidrawN]

# Unit tests (stdlib unittest, no receiver or desktop needed)
make test        # PYTHONPATH=src python -m unittest discover -s tests -v

# Build wheel and sdist
python -m build

# Arch: build and install arch/PKGBUILD (from the pushed main branch)
make arch
```

No linter is configured. CI builds, runs `twine check`, smoke-tests the CLI without a receiver (`--help`, `--version`, module imports) and runs the unit tests against the installed wheel.

**Dependencies:** none in Python. `notify-send` (libnotify) is called through `subprocess` for `--notify`. The udev rule in `data/70-sabrebat.rules` is what lets a normal user open the hidraw node.

## Architecture

All code lives in `src/sabrebat/`. `__init__.py` re-exports `cli.main` and reads `__version__` from the installed metadata on first use.

| Module      | Role |
|-------------|------|
| `device.py` | The receiver protocol. `find_device()` scans `/sys/class/hidraw/*/device/uevent` for `HID_ID` 1B1C:2B2A with `HID_PHYS` ending in `input1` (takes a `sysfs_root` for tests). `build_packet()` makes the 17-byte report (ID `0x08`, command, checksum `(0x55 - sum) & 0xFF`); `_query()` drains stale reports, writes and waits up to `READ_TIMEOUT` for the answer that echoes the command; `parse_battery()` turns it into `Battery(percent, millivolts, flag)`; `read_battery()` raises `DeviceError` with a user-facing message (not found, no permission, no answer). |
| `notify.py` | `level()` maps a percentage to Nord colour, label and urgency (`LEVELS`); `icon_svg()`/`make_icon()` draw a mouse filled to the level, cached per level in `$XDG_CACHE_HOME/sabrebat/`; `notify_command()` builds the `notify-send` argv (dunst stack tag, `int:value` progress bar, `hlcolor`/`frcolor`); `notify_battery()` and `notify_error()` send it. |
| `cli.py`    | argparse; `-q` and `-n` are mutually exclusive. Imports `notify` only when notifying. Exit 1 on `DeviceError` (also shown as a notification with `-n`) or when `notify-send` fails. |

Packaging data lives in `data/`: the udev rule, `sabre-bat.desktop` (`Exec=sabre-bat --notify`, `Icon=sabrebat`) and `sabrebat.svg`. Only `arch/PKGBUILD` installs them; the wheel ships just the Python package.

**Gotchas:**
- **Only send command `0x04`.** In this protocol family other commands write the settings memory (`0x07`) or factory-reset the mouse (`0x09`); packets with a wrong checksum are rejected with status `0x01`, which is how the format was worked out. See TECHNICAL_GUIDE.md.
- Byte 7 of the battery answer (`flag`) is shown raw: it has been seen as 0 and 1 but its meaning (charging?) is unconfirmed. Don't label it until it is checked with the cable plugged in and out.
- A sleeping mouse doesn't answer: that is a normal error, not a bug.
- The udev rule must sort before `73-seat-late.rules` for `uaccess` to apply.

## Release

Versions live in `pyproject.toml` (`version`) and `arch/PKGBUILD` (`pkgver`) and must match.

**Bumping the version also means updating `README.md` and the project page (`site/index.html`), in the same commit.** Both link the files of a specific release (`releases/download/vX.Y.Z/sabrebat-X.Y.Z-py3-none-any.whl`, `sabrebat-X.Y.Z.tar.gz`): in `README.md` the "GitHub release" row of the Download table; in `site/index.html` the download list's `aria-label`, the wheel and source buttons with their `<small>` labels and `SHA256SUMS.txt`. The release workflow refuses to publish if `README.md` or `site/index.html` don't link the wheel of the version being released. `.github/workflows/release.yaml` builds, smoke-tests and runs the unit tests on every run; on pushes and pull requests it only runs when the repository variable `SABREBAT_CI` is `true`. Running it manually with a version publishes the GitHub release, uploads to PyPI with Trusted Publishing (environment `pypi`) and copies `arch/PKGBUILD` to the `sabrebat` AUR package with `pkgrel=1` and a regenerated `.SRCINFO` (secret `AUR_SSH_PRIVATE_KEY`):

```bash
gh workflow run release.yaml -R Evilchuck666/SabreBat -f version=X.Y.Z --ref main
```

`site/` is deployed to GitHub Pages by `.github/workflows/pages.yaml`, which also checks the exact list of public files: update its count when adding or removing one.
