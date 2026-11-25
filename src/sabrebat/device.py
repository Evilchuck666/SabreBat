"""Talk to the Sabre v2 Pro receiver over hidraw.

The receiver (USB 1b1c:2b2a) exposes a vendor HID interface (input1) that takes
17-byte reports: report ID 0x08, a command byte, 14 data bytes and a checksum
equal to ``(0x55 - sum of the first 16 bytes) & 0xFF``. Answers use the same
layout and echo the command. Command 0x04 returns the battery state:

    byte 2      status (0 = OK, 1 = rejected, e.g. bad checksum)
    byte 6      battery level, percent
    byte 7      flag (meaning not confirmed yet; possibly charging)
    bytes 8-9   battery voltage in millivolts, big endian

Only command 0x04 is ever sent: other commands of this protocol write settings
or reset the mouse (see TECHNICAL_GUIDE.md).
"""

from __future__ import annotations

import os
import select
import time
from dataclasses import dataclass
from pathlib import Path

VENDOR_ID = 0x1B1C
PRODUCT_ID = 0x2B2A
HID_ID = f"0003:{VENDOR_ID:08X}:{PRODUCT_ID:08X}"
INTERFACE = "input1"

REPORT_ID = 0x08
REPORT_SIZE = 17
CHECKSUM_BASE = 0x55
CMD_BATTERY = 0x04

READ_TIMEOUT = 1.0
SYSFS_HIDRAW = "/sys/class/hidraw"


class DeviceError(Exception):
    """The battery could not be read; the message is meant for the user."""


@dataclass(frozen=True)
class Battery:
    percent: int
    millivolts: int
    flag: int

    @property
    def volts(self) -> float:
        return self.millivolts / 1000


def checksum(data: bytes | list[int]) -> int:
    return (CHECKSUM_BASE - sum(data)) & 0xFF


def build_packet(cmd: int) -> bytes:
    body = [REPORT_ID, cmd] + [0] * (REPORT_SIZE - 3)
    return bytes(body + [checksum(body)])


def parse_battery(resp: bytes) -> Battery:
    if len(resp) < 10 or resp[0] != REPORT_ID or resp[1] != CMD_BATTERY:
        raise DeviceError("Unexpected answer from the receiver.")
    if resp[2] != 0:
        raise DeviceError("The mouse is not answering: move it to wake it up and try again.")
    return Battery(percent=resp[6], millivolts=(resp[8] << 8) | resp[9], flag=resp[7])


def find_device(sysfs_root: str | os.PathLike = SYSFS_HIDRAW) -> str | None:
    """Return the /dev/hidrawN node of the receiver's vendor interface, if plugged in."""
    for node in sorted(Path(sysfs_root).glob("hidraw*")):
        try:
            uevent = (node / "device" / "uevent").read_text()
        except OSError:
            continue
        fields = dict(line.split("=", 1) for line in uevent.splitlines() if "=" in line)
        if fields.get("HID_ID", "").upper() == HID_ID and fields.get("HID_PHYS", "").endswith(INTERFACE):
            return f"/dev/{node.name}"
    return None


def _query(fd: int, cmd: int, timeout: float = READ_TIMEOUT) -> bytes | None:
    # Drop stale reports, send the command and wait for the answer that echoes it.
    # The deadline and the EOF checks keep a wrong node (e.g. --device /dev/null,
    # always readable and always empty) from looping forever.
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and select.select([fd], [], [], 0)[0]:
        if not os.read(fd, 64):
            return None
    os.write(fd, build_packet(cmd))
    while (left := deadline - time.monotonic()) > 0 and select.select([fd], [], [], left)[0]:
        resp = os.read(fd, 64)
        if not resp:
            return None
        if len(resp) >= 3 and resp[0] == REPORT_ID and resp[1] == cmd:
            return resp
    return None


def read_battery(device: str | None = None) -> Battery:
    device = device or find_device()
    if not device:
        raise DeviceError("Sabre v2 Pro receiver not found: is it plugged in?")
    try:
        fd = os.open(device, os.O_RDWR)
    except PermissionError:
        raise DeviceError(f"No permission to open {device}: install the udev rule (see README).") from None
    except OSError as e:
        raise DeviceError(f"Cannot open {device}: {e.strerror}.") from None
    try:
        resp = _query(fd, CMD_BATTERY)
    finally:
        os.close(fd)
    if resp is None:
        raise DeviceError("The mouse is not answering: move it to wake it up and try again.")
    return parse_battery(resp)
