"""Background mode (``sabre-bat --daemon``): watch the battery and suggest plugging
the charging cable in when it runs low, or unplugging it once the mouse is almost
charged.

A low-battery alert is only shown on battery and a charged alert only while the
cable is plugged in, so 20 % while charging or 90 % on battery stay quiet. An alert
is repeated every ``remind`` minutes for as long as its condition holds.
"""

from __future__ import annotations

import sys
import time
from typing import Callable

from .device import Battery, DeviceError, read_battery

DEFAULT_LOW = 20        # percent
DEFAULT_HIGH = 90       # percent
DEFAULT_INTERVAL = 60   # seconds between readings
DEFAULT_REMIND = 10     # minutes between repeated alerts; 0 shows each alert once

LOW = "low"
HIGH = "high"


def alert_for(battery: Battery, low: int, high: int) -> str | None:
    """The alert this reading calls for, ignoring when the last one was shown."""
    if not battery.charging and battery.percent <= low:
        return LOW
    if battery.charging and battery.percent >= high:
        return HIGH
    return None


class Watcher:
    """Decide, reading after reading, when an alert is due."""

    def __init__(self, low: int = DEFAULT_LOW, high: int = DEFAULT_HIGH,
                 remind: float = DEFAULT_REMIND * 60,
                 clock: Callable[[], float] = time.monotonic):
        self.low = low
        self.high = high
        self.remind = remind  # seconds
        self._clock = clock
        self._last: dict[str, float] = {}

    def check(self, battery: Battery) -> str | None:
        """Return the alert to show now, or None."""
        # Plugging the cable in ends a low-battery episode and unplugging it ends a
        # charged one, so the next episode is announced at once. A level that wobbles
        # around a threshold with the cable left as it was only gets the reminders.
        self._last.pop(LOW if battery.charging else HIGH, None)
        kind = alert_for(battery, self.low, self.high)
        if kind is None:
            return None
        now = self._clock()
        last = self._last.get(kind)
        if last is not None and (not self.remind or now - last < self.remind):
            return None
        self._last[kind] = now
        return kind


def log(message: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} sabre-bat: {message}", file=sys.stderr, flush=True)


def run(device: str | None = None, low: int = DEFAULT_LOW, high: int = DEFAULT_HIGH,
        interval: float = DEFAULT_INTERVAL, remind: float = DEFAULT_REMIND, *,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic) -> None:
    """Watch the battery until interrupted.

    Read errors (receiver unplugged, mouse asleep) are only logged: the next reading
    tries again, detecting the receiver anew unless ``device`` is given.
    """
    from .notify import notify_alert

    watcher = Watcher(low, high, remind * 60, clock)
    repeat = f"every {remind:g} min" if remind else "once"
    log(f"checking every {interval:g} s; alerts at {low}% on battery and {high}% while charging, "
        f"shown {repeat}")
    last_state = None
    while True:
        battery = None
        try:
            battery = read_battery(device)
            state = f"{battery.percent}%, {battery.status}"
        except DeviceError as e:
            state = str(e)
        if state != last_state:
            log(state)
            last_state = state
        if battery is not None and (kind := watcher.check(battery)):
            if notify_alert(battery, kind):
                log(f"{kind} battery alert shown")
            else:
                log("could not show the notification (is notify-send installed?)")
        sleep(interval)
