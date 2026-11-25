import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from sabrebat import notify
from sabrebat.device import Battery


class LevelTests(unittest.TestCase):
    def test_thresholds(self):
        cases = {
            100: ("green", "low"), 51: ("green", "low"),
            50: ("yellow", "normal"), 21: ("yellow", "normal"),
            20: ("orange", "normal"), 11: ("orange", "normal"),
            10: ("red", "critical"), 0: ("red", "critical"),
        }
        for percent, (colour, urgency) in cases.items():
            with self.subTest(percent=percent):
                got_colour, _label, got_urgency = notify.level(percent)
                self.assertEqual(got_colour, notify.NORD[colour])
                self.assertEqual(got_urgency, urgency)


class IconTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"XDG_CACHE_HOME": tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cache = tmp.name

    def test_fill_height(self):
        self.assertEqual(notify.fill_height(0), 0)
        self.assertEqual(notify.fill_height(50), 28)
        self.assertEqual(notify.fill_height(100), 56)
        self.assertEqual(notify.fill_height(150), 56)
        self.assertEqual(notify.fill_height(None), 0)

    def test_icon_written_to_cache(self):
        path = notify.make_icon(95, notify.NORD["green"])
        self.assertEqual(path, os.path.join(self.cache, "sabrebat", "icon-95.svg"))
        svg = Path(path).read_text()
        self.assertIn(notify.NORD["green"], svg)
        self.assertIn(f'height="{notify.fill_height(95)}"', svg)
        self.assertNotIn(">?<", svg)

    def test_unknown_level_icon(self):
        path = notify.make_icon(None, notify.NORD["muted"])
        self.assertTrue(path.endswith("icon-na.svg"))
        self.assertIn(">?<", Path(path).read_text())


class CommandTests(unittest.TestCase):
    def test_battery_notification(self):
        with mock.patch.object(notify, "make_icon", return_value="/tmp/icon.svg"), \
                mock.patch.object(notify.subprocess, "run") as run:
            run.return_value.returncode = 0
            self.assertTrue(notify.notify_battery(Battery(percent=8, millivolts=3600, flag=0)))
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[0], "notify-send")
        self.assertEqual(cmd[cmd.index("-u") + 1], "critical")
        self.assertEqual(cmd[cmd.index("-t") + 1], str(notify.CRITICAL_TIMEOUT_MS))
        self.assertIn("int:value:8", cmd)
        self.assertIn("string:x-dunst-stack-tag:sabrebat", cmd)
        self.assertIn(f"string:hlcolor:{notify.NORD['red']}", cmd)
        self.assertEqual(cmd[-2], notify.TITLE)
        self.assertIn("8%", cmd[-1])
        self.assertIn("3.60 V", cmd[-1])

    def test_missing_notify_send(self):
        with mock.patch.object(notify, "make_icon", return_value="x"), \
                mock.patch.object(notify.subprocess, "run", side_effect=FileNotFoundError):
            self.assertFalse(notify.notify_error("boom"))


if __name__ == "__main__":
    unittest.main()
