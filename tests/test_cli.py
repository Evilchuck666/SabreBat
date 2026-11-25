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
            self.assertEqual(run(), (0, "Sabre v2 Pro: 95%  (4184 mV, charging)\n", ""))

    def test_default_line_on_battery(self):
        on_battery = Battery(percent=40, millivolts=3850, flag=0)
        with mock.patch.object(cli, "read_battery", return_value=on_battery):
            self.assertEqual(run(), (0, "Sabre v2 Pro: 40%  (3850 mV, on battery)\n", ""))

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

    def test_daemon_defaults(self):
        with mock.patch("sabrebat.daemon.run") as daemon_run:
            self.assertEqual(run("--daemon"), (0, "", ""))
        daemon_run.assert_called_once_with(None, 20, 90, 60, 10)

    def test_daemon_options(self):
        with mock.patch("sabrebat.daemon.run") as daemon_run:
            run("-D", "-d", "/dev/hidraw9", "--low", "15", "--high", "80",
                "--interval", "30", "--remind", "0")
        daemon_run.assert_called_once_with("/dev/hidraw9", 15, 80, 30, 0)

    def test_daemon_stops_quietly_on_ctrl_c(self):
        with mock.patch("sabrebat.daemon.run", side_effect=KeyboardInterrupt):
            self.assertEqual(run("-D"), (0, "", ""))

    def test_daemon_rejects_bad_options(self):
        for argv in (["--low", "95", "--high", "90"], ["--low", "-1"], ["--high", "101"],
                     ["--interval", "0"], ["--remind", "-5"]):
            with self.subTest(argv=argv), mock.patch("sabrebat.daemon.run") as daemon_run, \
                    self.assertRaises(SystemExit):
                run("-D", *argv)
            daemon_run.assert_not_called()

    def test_daemon_and_quiet_exclusive(self):
        with self.assertRaises(SystemExit):
            run("-q", "-D")

    def test_version(self):
        code, out, _err = run("--version")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("sabre-bat "))


if __name__ == "__main__":
    unittest.main()
