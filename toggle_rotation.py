#!/usr/bin/env python3
"""Toggle which categories are active in the LED scoreboard rotation, live.

Examples:
    ./toggle_rotation.py                 # show current state of every category
    ./toggle_rotation.py nhl off         # turn NHL off
    ./toggle_rotation.py game on         # turn MLB games back on
    ./toggle_rotation.py --reset         # turn everything back on

A running display picks up changes within a couple of seconds -- no restart needed.
This is the same state file a physical keypad listener toggles (see keypad_listener.py).
"""
import argparse

from data.rotation_toggles import ALL_KINDS, RotationToggles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", nargs="?", choices=ALL_KINDS, help="Category to toggle")
    parser.add_argument("state", nargs="?", choices=["on", "off"], help="Desired state")
    parser.add_argument("--reset", action="store_true", help="Turn every category back on")
    args = parser.parse_args()

    toggles = RotationToggles()

    if args.reset:
        toggles.reset_all()
        print("All categories re-enabled")
        return

    if args.kind and not args.state:
        parser.error("Provide on/off after the category name")

    if args.kind:
        toggles.set_enabled(args.kind, args.state == "on")
        print(f"{args.kind}: {args.state}")
        return

    for kind in ALL_KINDS:
        print(f"{kind}: {'on' if toggles.is_enabled(kind) else 'off'}")


if __name__ == "__main__":
    main()
