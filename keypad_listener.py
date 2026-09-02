#!/usr/bin/env python3
"""Listens for keypresses from a USB HID keypad (e.g. Rii i4) and toggles
LED scoreboard rotation categories live. Run as its own systemd service,
independent of the display process -- see systemd/mlb-led-keypad.service.

Key mapping (number row):
  1 MLB   2 NFL   3 NHL   4 NBA   5 NCAAF   6 NCAAB   7 EPL   8 News   9 Standings
  0 reset everything back on

Requires the `evdev` package (Linux only -- see requirements.rpi.txt) and read access
to /dev/input/event*, which is why this runs as root in its systemd unit.
"""
import sys

from evdev import InputDevice, categorize, ecodes, list_devices

from bullpen.logging import LOGGER
from data.rotation_toggles import RotationToggles

DEVICE_NAME_HINT = "Rii"

KEY_MAP = {
    ecodes.KEY_1: "game",
    ecodes.KEY_2: "nfl",
    ecodes.KEY_3: "nhl",
    ecodes.KEY_4: "nba",
    ecodes.KEY_5: "ncaaf",
    ecodes.KEY_6: "ncaab",
    ecodes.KEY_7: "epl",
    ecodes.KEY_8: "news",
    ecodes.KEY_9: "standings",
}
RESET_KEY = ecodes.KEY_0


def find_keyboard_device() -> "InputDevice | None":
    for path in list_devices():
        device = InputDevice(path)
        if DEVICE_NAME_HINT.lower() in device.name.lower() and ecodes.EV_KEY in device.capabilities():
            return device
    return None


def main() -> None:
    device = find_keyboard_device()
    if device is None:
        LOGGER.error("Could not find a keyboard device matching '%s'. Available devices:", DEVICE_NAME_HINT)
        for path in list_devices():
            LOGGER.error("  %s: %s", path, InputDevice(path).name)
        sys.exit(1)

    LOGGER.info("Listening for toggle keys on %s (%s)", device.name, device.path)
    toggles = RotationToggles()

    for event in device.read_loop():
        if event.type != ecodes.EV_KEY:
            continue

        key_event = categorize(event)
        if key_event.keystate != key_event.key_down:
            continue

        if event.code == RESET_KEY:
            toggles.reset_all()
            LOGGER.info("Rotation toggles reset: everything enabled")
        elif event.code in KEY_MAP:
            kind = KEY_MAP[event.code]
            new_state = not toggles.is_enabled(kind)
            toggles.set_enabled(kind, new_state)
            LOGGER.info("Toggled %s -> %s", kind, "on" if new_state else "off")


if __name__ == "__main__":
    main()
