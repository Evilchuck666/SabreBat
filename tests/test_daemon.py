import contextlib
import io
import unittest
from unittest import mock

from sabrebat import daemon
from sabrebat.device import Battery, DeviceError


def bat(percent, charging=False):
    return Battery(percent=percent, millivolts=3900, flag=int(charging))


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Stop(Exception):
    pass


class AlertForTests(unittest.TestCase):
    def test_rules(self):
        cases = [
            (bat(20), daemon.LOW),
            (bat(5), daemon.LOW),
            (bat(21), None),
            (bat(20, charging=True), None),
            (bat(90, charging=True), daemon.HIGH),
            (bat(100, charging=True), daemon.HIGH),
            (bat(89, charging=True), None),
            (bat(90), None),
            (bat(50), None),
        ]
        for battery, expected in cases:
            with self.subTest(battery=battery):
                self.assertEqual(daemon.alert_for(battery, 20, 90), expected)


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.watcher = daemon.Watcher(20, 90, remind=600, clock=self.clock)

    def at(self, seconds, battery):
        self.clock.now = seconds
        return self.watcher.check(battery)

    def test_low_alert_and_reminder(self):
        self.assertIsNone(self.at(0, bat(21)))
        self.assertEqual(self.at(60, bat(20)), daemon.LOW)
        self.assertIsNone(self.at(120, bat(20)))
        self.assertIsNone(self.at(659, bat(19)))
        self.assertEqual(self.at(660, bat(19)), daemon.LOW)

    def test_high_alert_and_reminder(self):
        self.assertEqual(self.at(0, bat(90, charging=True)), daemon.HIGH)
        self.assertIsNone(self.at(300, bat(92, charging=True)))
        self.assertEqual(self.at(600, bat(93, charging=True)), daemon.HIGH)

    def test_no_alert_in_the_wrong_direction(self):
        self.assertIsNone(self.at(0, bat(15, charging=True)))
        self.assertIsNone(self.at(60, bat(95)))

    def test_unplugging_again_while_low_alerts_at_once(self):
        self.assertEqual(self.at(0, bat(18)), daemon.LOW)
        self.assertIsNone(self.at(60, bat(18, charging=True)))
        self.assertEqual(self.at(120, bat(19)), daemon.LOW)

    def test_plugging_in_again_while_charged_alerts_at_once(self):
        self.assertEqual(self.at(0, bat(95, charging=True)), daemon.HIGH)
        self.assertIsNone(self.at(60, bat(95)))
        self.assertEqual(self.at(120, bat(95, charging=True)), daemon.HIGH)

    def test_wobbling_level_waits_for_the_reminder(self):
        self.assertEqual(self.at(0, bat(20)), daemon.LOW)
        self.assertIsNone(self.at(60, bat(21)))
        self.assertIsNone(self.at(120, bat(20)))

    def test_remind_zero_alerts_once(self):
        watcher = daemon.Watcher(20, 90, remind=0, clock=self.clock)
        self.assertEqual(watcher.check(bat(20)), daemon.LOW)
        self.clock.now = 10_000
        self.assertIsNone(watcher.check(bat(10)))


class RunTests(unittest.TestCase):
    def run_daemon(self, readings, notified=True):
        """Run the loop over these readings (Battery or DeviceError) and stop."""
        clock = FakeClock()
        sleeps = []

        def sleep(seconds):
            sleeps.append(seconds)
            clock.now += seconds
            if len(sleeps) == len(readings):
                raise Stop

        err = io.StringIO()
        with mock.patch.object(daemon, "read_battery", side_effect=readings) as read, \
                mock.patch("sabrebat.notify.notify_alert", return_value=notified) as alert, \
                contextlib.redirect_stderr(err):
            with self.assertRaises(Stop):
                daemon.run("/dev/hidraw9", 20, 90, 60, 10, sleep=sleep, clock=clock)
        read.assert_called_with("/dev/hidraw9")
        self.assertEqual(sleeps, [60] * len(readings))
        return alert, err.getvalue()

    def test_alerts_and_log(self):
        readings = [bat(21), bat(21), bat(20), DeviceError("The mouse is not answering."),
                    DeviceError("The mouse is not answering."), bat(20), bat(20, charging=True)]
        alert, log = self.run_daemon(readings)
        alert.assert_called_once_with(bat(20), daemon.LOW)
        lines = [line.split(" sabre-bat: ", 1)[1] for line in log.splitlines()]
        self.assertEqual(lines, [
            "checking every 60 s; alerts at 20% on battery and 90% while charging, "
            "shown every 10 min",
            "21%, on battery",
            "20%, on battery",
            "low battery alert shown",
            "The mouse is not answering.",
            "20%, on battery",
            "20%, charging",
        ])

    def test_failed_notification_is_logged(self):
        alert, log = self.run_daemon([bat(95, charging=True)], notified=False)
        alert.assert_called_once_with(bat(95, charging=True), daemon.HIGH)
        self.assertIn("could not show the notification", log)


if __name__ == "__main__":
    unittest.main()
