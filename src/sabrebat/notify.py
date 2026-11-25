"""Desktop notification with a battery-gauge icon (notify-send, tuned for dunst)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .device import Battery

APP_NAME = "SabreBat"
TITLE = "Corsair Sabre v2 Pro"
STACK_TAG = "sabrebat"

# Nord palette
NORD = {
    "bg": "#2E3440",
    "fg": "#ECEFF4",
    "dim": "#D8DEE9",
    "muted": "#4C566A",
    "green": "#A3BE8C",
    "yellow": "#EBCB8B",
    "orange": "#D08770",
    "red": "#BF616A",
}

# (lowest percent, colour, label, urgency), checked from the top.
LEVELS = (
    (51, NORD["green"], "High battery", "low"),
    (21, NORD["yellow"], "Medium battery", "normal"),
    (11, NORD["orange"], "Low battery", "normal"),
    (0, NORD["red"], "Critical battery, charge it!", "critical"),
)

# Daemon alerts: kind -> (label, hint, urgency).
ALERTS = {
    "low": ("Low battery", "Connect the cable to charge the mouse.", "critical"),
    "high": ("Almost charged", "You can unplug the cable.", "normal"),
}

TIMEOUT_MS = 6000
CRITICAL_TIMEOUT_MS = 10000

_TOP, _BOTTOM = 4, 60


def level(percent: int) -> tuple[str, str, str]:
    """Return (colour, label, urgency) for a battery percentage."""
    for lowest, colour, label, urgency in LEVELS:
        if percent >= lowest:
            return colour, label, urgency
    return LEVELS[-1][1:]


def icon_dir() -> Path:
    cache = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return Path(cache) / "sabrebat"


def fill_height(percent: int | None) -> int:
    if percent is None:
        return 0
    return round((_BOTTOM - _TOP) * max(0, min(percent, 100)) / 100)


def icon_svg(percent: int | None, colour: str) -> str:
    """A mouse outline whose body fills up with the battery level; ``None`` draws a "?"."""
    fill = fill_height(percent)
    height = _BOTTOM - _TOP
    mark = ""
    if percent is None:
        mark = (f'<text x="32" y="47" text-anchor="middle" font-family="sans-serif" '
                f'font-weight="bold" font-size="20" fill="{NORD["dim"]}">?</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 64 64">
  <defs><clipPath id="body"><rect x="14" y="{_TOP}" width="36" height="{height}" rx="18"/></clipPath></defs>
  <rect x="14" y="{_TOP}" width="36" height="{height}" rx="18" fill="{NORD["bg"]}"/>
  <g clip-path="url(#body)"><rect x="14" y="{_BOTTOM - fill}" width="36" height="{fill}" fill="{colour}"/></g>
  <line x1="32" y1="{_TOP}" x2="32" y2="26" stroke="{NORD["muted"]}" stroke-width="2"/>
  <line x1="14" y1="26" x2="50" y2="26" stroke="{NORD["muted"]}" stroke-width="2"/>
  <rect x="29" y="11" width="6" height="10" rx="3" fill="{NORD["fg"]}"/>
  <rect x="14" y="{_TOP}" width="36" height="{height}" rx="18" fill="none" stroke="{NORD["fg"]}" stroke-width="3"/>
  {mark}
</svg>
'''


def make_icon(percent: int | None, colour: str) -> str:
    """Write the icon for this level to the cache (once) and return its path."""
    path = icon_dir() / f"icon-{'na' if percent is None else percent}.svg"
    svg = icon_svg(percent, colour)
    try:
        if not path.exists() or path.read_text() != svg:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(svg)
    except OSError:
        return "input-mouse"  # Fall back to the icon theme.
    return str(path)


def notify_command(summary: str, body: str, icon: str, urgency: str = "normal",
                   value: int | None = None, colour: str | None = None,
                   timeout: int = TIMEOUT_MS) -> list[str]:
    cmd = ["notify-send", "-a", APP_NAME, "-u", urgency, "-t", str(timeout), "-i", icon,
           "-h", f"string:x-dunst-stack-tag:{STACK_TAG}"]
    if value is not None:
        cmd += ["-h", f"int:value:{value}"]
    if colour:
        cmd += ["-h", f"string:hlcolor:{colour}", "-h", f"string:frcolor:{colour}"]
    return cmd + [summary, body]


def _send(cmd: list[str]) -> bool:
    try:
        return subprocess.run(cmd, check=False).returncode == 0
    except FileNotFoundError:
        return False


def battery_body(battery: Battery, label: str | None = None, hint: str | None = None) -> str:
    """Notification text: the level, a label (by default the level's), an optional hint
    line and the voltage."""
    colour, level_label, _ = level(battery.percent)
    if label is None:
        label = f"{level_label} · charging" if battery.charging else level_label
    hint_line = f"<span foreground='{NORD['fg']}'>{hint}</span>\n" if hint else ""
    return (f"<span size='xx-large' weight='bold' foreground='{colour}'>{battery.percent}%</span>"
            f"  <span foreground='{NORD['dim']}'>{label}</span>\n"
            f"{hint_line}"
            f"<span size='small' foreground='{NORD['dim']}' fgalpha='65%'>{battery.volts:.2f} V</span>")


def _notify_level(battery: Battery, body: str, urgency: str) -> bool:
    colour = level(battery.percent)[0]
    timeout = CRITICAL_TIMEOUT_MS if urgency == "critical" else TIMEOUT_MS
    return _send(notify_command(TITLE, body, make_icon(battery.percent, colour),
                                urgency=urgency, value=battery.percent, colour=colour, timeout=timeout))


def notify_battery(battery: Battery) -> bool:
    return _notify_level(battery, battery_body(battery), level(battery.percent)[2])


def notify_alert(battery: Battery, kind: str) -> bool:
    """Suggest plugging the cable in (``"low"``) or unplugging it (``"high"``)."""
    label, hint, urgency = ALERTS[kind]
    return _notify_level(battery, battery_body(battery, label, hint), urgency)


def notify_error(message: str) -> bool:
    body = f"<span foreground='{NORD['dim']}'>{message}</span>"
    return _send(notify_command(TITLE, body, make_icon(None, NORD["muted"]), colour=NORD["muted"]))
