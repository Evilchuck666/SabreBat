import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from sabrebat import device
from sabrebat.device import Battery, DeviceError

# Real answer of the receiver to command 0x04 (95 %, 4180 mV, flag 1).
REAL_ANSWER = bytes.fromhex("08 04 00 00 00 02 5f 01 10 54 00 00 00 00 00 00 83")


class PacketTests(unittest.TestCase):
    def test_battery_packet(self):
        packet = device.build_packet(device.CMD_BATTERY)
        self.assertEqual(len(packet), device.REPORT_SIZE)
        self.assertEqual(packet[:2], b"\x08\x04")
        self.assertEqual(packet[-1], 0x49)  # 0x55 - (0x08 + 0x04)

    def test_checksum_matches_real_answers(self):
        # The receiver signs its answers the same way.
        self.assertEqual(device.checksum(REAL_ANSWER[:16]), REAL_ANSWER[16])
        rejected = bytes.fromhex("08 02 01 00 00 00 00 00 00 00 00 00 00 00 00 00 4a")
        self.assertEqual(device.checksum(rejected[:16]), rejected[16])

    def test_checksum_wraps(self):
        self.assertEqual(device.checksum([0xFF, 0xFF]), (0x55 - 0x1FE) & 0xFF)


class ParseTests(unittest.TestCase):
    def test_real_answer(self):
        battery = device.parse_battery(REAL_ANSWER)
        self.assertEqual(battery, Battery(percent=95, millivolts=0x1054, flag=1))
        self.assertAlmostEqual(battery.volts, 4.18)

    def test_rejected_answer(self):
        with self.assertRaises(DeviceError):
            device.parse_battery(bytes.fromhex("08 04 01") + bytes(14))

    def test_other_command_or_short_answer(self):
        with self.assertRaises(DeviceError):
            device.parse_battery(bytes.fromhex("08 03 00 00 00 01 01 6e be cc") + bytes(7))
        with self.assertRaises(DeviceError):
            device.parse_battery(b"\x08\x04")


class FindDeviceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def add_node(self, name, hid_id, phys):
        node = self.root / name / "device"
        node.mkdir(parents=True)
        (node / "uevent").write_text(f"DRIVER=hid-generic\nHID_ID={hid_id}\nHID_NAME=x\nHID_PHYS={phys}\n")

    def test_picks_the_vendor_interface(self):
        self.add_node("hidraw2", "0003:00002E3C:0000C365", "usb-0000:02:00.0-3/input1")
        self.add_node("hidraw5", "0003:00001B1C:00002B2A", "usb-0000:02:00.0-8/input0")
        self.add_node("hidraw6", "0003:00001B1C:00002B2A", "usb-0000:02:00.0-8/input1")
        self.add_node("hidraw7", "0003:00001B1C:00002B2A", "usb-0000:02:00.0-8/input2")
        self.assertEqual(device.find_device(self.root), "/dev/hidraw6")

    def test_not_plugged_in(self):
        self.add_node("hidraw0", "0003:0000046D:0000C52B", "usb-0000:02:00.0-1/input1")
        (self.root / "hidraw1").mkdir()  # No uevent: skipped.
        self.assertIsNone(device.find_device(self.root))

    def test_read_battery_without_receiver(self):
        with mock.patch.object(device, "find_device", return_value=None):
            with self.assertRaisesRegex(DeviceError, "not found"):
                device.read_battery()


class QueryTests(unittest.TestCase):
    """_query() with select/read/write mocked: no hidraw node needed."""

    def test_query_skips_unrelated_reports(self):
        unrelated = bytes.fromhex("08 09 01") + bytes(14)
        ready, idle = ([3], [], []), ([], [], [])
        with mock.patch.object(device.os, "write", return_value=17) as write, \
                mock.patch.object(device.os, "read", side_effect=[unrelated, REAL_ANSWER]), \
                mock.patch.object(device.select, "select", side_effect=[idle, ready, ready]):
            resp = device._query(3, device.CMD_BATTERY)
        write.assert_called_once_with(3, device.build_packet(device.CMD_BATTERY))
        self.assertEqual(resp, REAL_ANSWER)

    def test_query_stops_on_eof(self):
        # A wrong --device such as /dev/null is always readable and always empty.
        fd = os.open(os.devnull, os.O_RDWR)
        self.addCleanup(os.close, fd)
        start = time.monotonic()
        self.assertIsNone(device._query(fd, device.CMD_BATTERY, timeout=5))
        self.assertLess(time.monotonic() - start, 1)

    def test_query_times_out(self):
        with mock.patch.object(device.os, "write", return_value=17), \
                mock.patch.object(device.select, "select", return_value=([], [], [])):
            self.assertIsNone(device._query(3, device.CMD_BATTERY, timeout=0))


if __name__ == "__main__":
    unittest.main()
