# SabreBat technical guide

How SabreBat reads the battery, what it needs from the system, and how to build it from source.
For installation and everyday use, see the [README](README.md).

## The receiver protocol

The Sabre v2 Pro talks to the computer through its USB receiver (`1b1c:2b2a`, "Sabre v2 Pro
Ultralight Wireless Receiver"). The receiver has three HID interfaces:

| Interface | Role |
|:----------|:-----|
| `input0` | Boot mouse |
| `input1` | Vendor reports, media keys and system control: **the one SabreBat uses** |
| `input2` | Boot keyboard |

On `input1`, report ID `0x08` carries 16 bytes in each direction. The protocol is not Corsair's
"Bragi" protocol used by its other wireless mice: SabreBat's knowledge of it comes from
observing the receiver's answers. Every packet, sent or received, has this layout:

| Byte | Content |
|:-----|:--------|
| 0 | Report ID `0x08` |
| 1 | Command (answers echo it) |
| 2 | Status in answers: `0x00` OK, `0x01` rejected (e.g. bad checksum) |
| 3–15 | Command data |
| 16 | Checksum: `(0x55 - sum of bytes 0–15) & 0xFF` |

### Battery: command `0x04`

Request: `08 04 00 … 00 49`. Answer, for example:

```
08 04 00 00 00 02 5f 01 10 54 00 00 00 00 00 00 83
               │  │  │  └──┴─ voltage, big endian: 0x1054 = 4180 mV
               │  │  └─ flag: 1 with the charging cable plugged in, 0 on battery
               │  └─ level: 0x5f = 95 %
               └─ data length
```

The flag was checked on the mouse by reading it with the cable in and out, at the same level:

| Cable | Level | Voltage | Flag |
|:------|:------|:--------|:-----|
| Unplugged | 95 % | 4088 mV | 0 |
| Plugged in | 95 % | 4214 mV | 1 |

The receiver keeps answering while the cable is plugged in, and the mouse doesn't show up as a
USB device of its own. Whether the flag stays at 1 once the battery is full is not known yet.
`Battery.charging` is `flag == 1`, and `sabre-bat` prints it as `charging` or `on battery`.

When the mouse is asleep or off, the receiver doesn't answer, and SabreBat reports that after
waiting one second (`device.READ_TIMEOUT`).

### Commands to avoid

Command `0x03` returns a connection status (`08 03 00 00 00 01 01 …`). In the protocol family
this receiver seems to belong to, other commands write the mouse's settings memory (`0x07`)
or restore its factory settings (`0x09`). **SabreBat only ever sends `0x04`.** If you
experiment, keep to commands you know are read-only.

## Permissions

hidraw nodes belong to root. The udev rule in [`data/70-sabrebat.rules`](data/70-sabrebat.rules)
tags the receiver's hidraw nodes with `uaccess`, so systemd-logind or elogind add an ACL for
the user logged in at the seat:

```
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="1b1c", ATTRS{idProduct}=="2b2a", TAG+="uaccess"
```

The file name must sort before `73-seat-late.rules`, which applies the tag. After installing
it, replug the receiver (or run `sudo udevadm trigger`). `getfacl /dev/hidrawN` then lists your
user. `sabre-bat` reports a missing permission as such.

To find the node by hand:

```bash
grep -l '1B1C:00002B2A' /sys/class/hidraw/hidraw*/device/uevent
```

The one whose `HID_PHYS` ends in `input1` is the right one; pass it with `--device` to skip the
detection.

## Notifications

`sabre-bat --notify` runs `notify-send` with:

- `int:value:<percent>`, which dunst draws as a progress bar;
- `string:x-dunst-stack-tag:sabrebat`, so a new notification replaces the previous one;
- `string:hlcolor` and `string:frcolor`, the level colour for the bar and the frame;
- urgency `low` above 50 %, `normal` down to 11 % and `critical` at 10 % or less.

The icon is an SVG written once per level to `$XDG_CACHE_HOME/sabrebat/` (default
`~/.cache/sabrebat/`). Other notification daemons ignore the dunst hints and show the text and
icon.

The daemon's alerts use the same hints and stack tag, so a reminder replaces the notification
before it. The low-battery alert has `critical` urgency and the charged alert `normal`.

## Daemon

`sabre-bat --daemon` reads the battery every `--interval` seconds (default 60) and decides from
the level and the charging flag:

| Alert | Shown when | Suggests |
|:------|:-----------|:---------|
| Low battery | level ≤ `--low` (default 20 %) **and** on battery | plugging the cable in |
| Almost charged | level ≥ `--high` (default 90 %) **and** charging | unplugging the cable |

So 20 % while charging and 90 % on battery stay quiet. While its condition holds, an alert is
repeated every `--remind` minutes (default 10; `0` shows it once). Plugging the cable in ends a
low-battery episode and unplugging it ends a charged one, so unplugging again below the
threshold alerts at once. A level that wobbles around a threshold, with the cable left as it
was, only gets the reminders. The decision lives in `daemon.Watcher`, which the tests drive with
a fake clock.

Read errors are not notified: the receiver may be unplugged or the mouse asleep, and the next
reading tries again. Without `--device`, the receiver is detected anew at each reading, so the
daemon survives replugging it.

The daemon logs to stderr, with a timestamp, when it starts, when the level, the charging state
or the error changes, and when it shows an alert. It stops on Ctrl+C (exit status 0) or on
`SIGTERM`.

## Installing from source

### Building and installing the wheel

```bash
git clone https://github.com/Evilchuck666/SabreBat.git
cd SabreBat
make install        # builds the wheel into PKGs/ and installs it with pip
```

`make build` only builds the wheel. Remove it with `make uninstall`. A pip installation leaves
out the udev rule, the desktop entry and the icon: install them from `data/` as the README
explains.

### Arch package from this checkout

```bash
make arch           # makepkg -si on arch/PKGBUILD
```

`arch/PKGBUILD` clones the repository from GitHub, so it builds the pushed `main` branch, not
uncommitted changes.

### Running the tests

The tests use the standard library's `unittest` and mock hidraw and `notify-send`, so they
need neither the receiver nor a desktop session:

```bash
make test           # PYTHONPATH=src python -m unittest discover -s tests -v
```

### Running from the checkout

```bash
PYTHONPATH=src python -m sabrebat --notify
PYTHONPATH=src python -m sabrebat --daemon --interval 5 --remind 1
```
