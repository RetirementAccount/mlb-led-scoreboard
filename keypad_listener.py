#!/usr/bin/env python3
"""Listens for keypresses from a USB HID keypad (tested against a Rii i4, whose RF
dongle identifies to Linux only as "Telink Wireless Receiver" -- device detection
below is capability-based, not name-based, so it isn't tied to that specific string)
and toggles LED scoreboard rotation categories live. Run as its own systemd service,
independent of the display process -- see systemd/mlb-led-keypad.service.

Key mapping (number row):
  1 MLB   2 NFL   3 NHL   4 NBA   5 NCAAF   6 NCAAB   7 EPL   8 News   9 Standings
  0 reset everything back on

Requires the `evdev` package (Linux only -- see requirements.rpi.txt) and read access
to /dev/input/event*, which is why this runs as root in its systemd unit.
"""
import logging
import sys

from evdev import InputDevice, categorize, ecodes, list_devices

from bullpen.logging import LOGGER
from data.rotation_toggles import RotationToggles

# Unlike main.py, nothing here constructs a Config (which is what normally sets the
# bullpen logger's level based on config.json's "debug" flag), so without this the
# logger stays at its default level and every LOGGER.info() call below is silently dropped.
LOGGER.setLevel(logging.INFO)

# A cheap wireless keypad's RF dongle commonly exposes several separate event
# nodes under its chipset vendor's name (e.g. "Telink Wireless Receiver") rather
# than the keypad's own brand name -- one for the keyboard, one for the
# mouse/touchpad, one for consumer-control media keys, one for system-control
# power keys. Matching by name is unreliable across different keypads, so
# instead require the specific keys this script binds to actually be present
# on the candidate device -- that's the one node that's really the keyboard.
REQUIRED_KEYS = {
    ecodes.KEY_1,
    ecodes.KEY_2,
    ecodes.KEY_3,
    ecodes.KEY_4,
    ecodes.KEY_5,
    ecodes.KEY_6,
    ecodes.KEY_7,
    ecodes.KEY_8,
    ecodes.KEY_9,
    ecodes.KEY_0,
}

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
        keys = set(device.capabilities().get(ecodes.EV_KEY, []))
        if REQUIRED_KEYS.issubset(keys):
            return device
    return None


def main() -> None:
    device = find_keyboard_device()
    if device is None:
        LOGGER.error("Could not find a keyboard device exposing keys 0-9. Available devices:")
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
