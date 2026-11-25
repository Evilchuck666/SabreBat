"""Command line entry point: ``sabre-bat``."""

from __future__ import annotations

import argparse
import sys

from . import daemon
from .device import DeviceError, read_battery


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sabre-bat",
        description="Show the battery level of the Corsair Sabre v2 Pro wireless mouse.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("-q", "--quiet", action="store_true",
                      help="print only the percentage (for status bars and scripts)")
    mode.add_argument("-n", "--notify", action="store_true",
                      help="show the level in a desktop notification instead of printing it")
    mode.add_argument("-D", "--daemon", action="store_true",
                      help="keep running and notify when the cable should be plugged in "
                           "(--low, on battery) or unplugged (--high, while charging)")
    parser.add_argument("-d", "--device", metavar="PATH",
                        help="hidraw node to use instead of detecting the receiver")
    parser.add_argument("-V", "--version", action="store_true", help="show the version and exit")

    alerts = parser.add_argument_group("daemon options")
    alerts.add_argument("--low", type=int, default=daemon.DEFAULT_LOW, metavar="PERCENT",
                        help="suggest charging at or below this level on battery "
                             "(default: %(default)s)")
    alerts.add_argument("--high", type=int, default=daemon.DEFAULT_HIGH, metavar="PERCENT",
                        help="suggest unplugging at or above this level while charging "
                             "(default: %(default)s)")
    alerts.add_argument("--interval", type=int, default=daemon.DEFAULT_INTERVAL, metavar="SECONDS",
                        help="time between readings (default: %(default)s)")
    alerts.add_argument("--remind", type=int, default=daemon.DEFAULT_REMIND, metavar="MINUTES",
                        help="repeat an alert this often while it applies, 0 to show it once "
                             "(default: %(default)s)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from . import __version__
        print(f"sabre-bat {__version__}")
        return 0

    if args.daemon:
        if not 0 <= args.low < args.high <= 100:
            parser.error("--low and --high must be percentages with --low below --high")
        if args.interval < 1:
            parser.error("--interval must be at least 1 second")
        if args.remind < 0:
            parser.error("--remind cannot be negative")
        try:
            daemon.run(args.device, args.low, args.high, args.interval, args.remind)
        except KeyboardInterrupt:
            pass
        return 0

    try:
        battery = read_battery(args.device)
    except DeviceError as e:
        if args.notify:
            from .notify import notify_error
            notify_error(str(e))
        print(f"sabre-bat: {e}", file=sys.stderr)
        return 1

    if args.notify:
        from .notify import notify_battery
        if not notify_battery(battery):
            print("sabre-bat: could not show the notification (is notify-send installed?)",
                  file=sys.stderr)
            return 1
    elif args.quiet:
        print(battery.percent)
    else:
        print(f"Sabre v2 Pro: {battery.percent}%  ({battery.millivolts} mV, {battery.status})")
    return 0
