"""Command line entry point: ``sabre-bat``."""

from __future__ import annotations

import argparse
import sys

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
    parser.add_argument("-d", "--device", metavar="PATH",
                        help="hidraw node to use instead of detecting the receiver")
    parser.add_argument("-V", "--version", action="store_true", help="show the version and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.version:
        from . import __version__
        print(f"sabre-bat {__version__}")
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
        print(f"Sabre v2 Pro: {battery.percent}%  ({battery.millivolts} mV, flag={battery.flag})")
    return 0
