#!/usr/bin/env python3
"""Control the LED scoreboard rotation live: which categories are active, and
pause/skip for whatever's currently showing.

Examples:
    ./toggle_rotation.py                 # show current state of every category
    ./toggle_rotation.py nhl off         # turn NHL off
    ./toggle_rotation.py game on         # turn MLB games back on
    ./toggle_rotation.py --reset         # turn every category back on
    ./toggle_rotation.py --pause         # freeze whatever's currently showing
    ./toggle_rotation.py --resume        # let the rotation advance normally again
    ./toggle_rotation.py --skip          # end the current screen now, advance to the next

A running display picks up changes within a couple of seconds -- no restart needed.
This is the same state a physical keypad listener drives (see keypad_listener.py).
"""
import argparse

from data.rotation_control import RotationControl
from data.rotation_toggles import ALL_KINDS, RotationToggles


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("kind", nargs="?", choices=ALL_KINDS, help="Category to toggle")
    parser.add_argument("state", nargs="?", choices=["on", "off"], help="Desired state")
    parser.add_argument("--reset", action="store_true", help="Turn every category back on")
    parser.add_argument("--pause", action="store_true", help="Freeze whatever's currently showing")
    parser.add_argument("--resume", action="store_true", help="Let the rotation advance normally again")
    parser.add_argument("--skip", action="store_true", help="End the current screen now, advance to the next")
    args = parser.parse_args()

    if args.pause:
        RotationControl().set_paused(True)
        print("Paused")
        return

    if args.resume:
        RotationControl().set_paused(False)
        print("Resumed")
        return

    if args.skip:
        RotationControl().request_skip()
        print("Skip requested")
        return

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
    print(f"paused: {'yes' if RotationControl().is_paused() else 'no'}")


if __name__ == "__main__":
    main()
