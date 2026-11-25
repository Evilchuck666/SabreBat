import contextlib
import io
import unittest
from unittest import mock

from sabrebat import cli
from sabrebat.device import Battery, DeviceError

BATTERY = Battery(percent=95, millivolts=4184, flag=1)


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class CliTests(unittest.TestCase):
    def test_default_line(self):
        with mock.patch.object(cli, "read_battery", return_value=BATTERY):
            self.assertEqual(run(), (0, "Sabre v2 Pro: 95%  (4184 mV, flag=1)\n", ""))

    def test_quiet(self):
        with mock.patch.object(cli, "read_battery", return_value=BATTERY):
            self.assertEqual(run("-q"), (0, "95\n", ""))

    def test_device_option(self):
        with mock.patch.object(cli, "read_battery", return_value=BATTERY) as read:
            run("--device", "/dev/hidraw9")
        read.assert_called_once_with("/dev/hidraw9")

    def test_error(self):
        with mock.patch.object(cli, "read_battery", side_effect=DeviceError("receiver not found")):
            code, out, err = run()
        self.assertEqual((code, out), (1, ""))
        self.assertIn("receiver not found", err)

    def test_notify(self):
        with mock.patch.object(cli, "read_battery", return_value=BATTERY), \
                mock.patch("sabrebat.notify.notify_battery", return_value=True) as shown:
            self.assertEqual(run("-n"), (0, "", ""))
        shown.assert_called_once_with(BATTERY)

    def test_notify_error(self):
        with mock.patch.object(cli, "read_battery", side_effect=DeviceError("asleep")), \
                mock.patch("sabrebat.notify.notify_error") as shown:
            code, _out, _err = run("--notify")
        self.assertEqual(code, 1)
        shown.assert_called_once_with("asleep")

    def test_quiet_and_notify_exclusive(self):
        with self.assertRaises(SystemExit):
            run("-q", "-n")

    def test_version(self):
        code, out, _err = run("--version")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("sabre-bat "))


if __name__ == "__main__":
    unittest.main()
