#!/usr/bin/env python3
"""Listens for input from a USB HID keypad (tested against a Rii i4, whose RF dongle
identifies to Linux only as "Telink Wireless Receiver" -- device detection below is
capability-based, not name-based, so it isn't tied to that specific string) and
controls LED scoreboard rotation live. Run as its own systemd service, independent
of the display process -- see systemd/mlb-led-keypad.service.

Key mapping (keyboard side):
  1 MLB   2 NFL   3 NHL   4 NBA   5 NCAAF   6 NCAAB   7 EPL   8 News   9 Standings
  0 reset every category back on
  Up arrow    toggle pause (freezes whatever's currently showing, ignoring its timer)
  Right arrow skip: end the current screen now, advance to the next -- works even while paused
  G           open the game menu (or, if already in the game area, exit back to the ticker)
  Enter       confirm a menu selection (see data/game_mode.py, game_menu plugin)

Mouse-button side (the keypad's touchpad click buttons, labeled L/R on this unit):
  Left click  in the menu: move the selection left one slot per click
  Right click same, other direction
  Holding either button down also updates a live "held" state (data/game_mode.py's
  set_steer_held/held_direction) that a game can poll every frame for continuous
  movement while held, instead of needing repeated taps -- see fruit_catcher.

Requires the `evdev` package (Linux only -- see requirements.rpi.txt) and read access
to /dev/input/event*, which is why this runs as root in its systemd unit.
"""
import logging
import selectors
import sys

from evdev import InputDevice, categorize, ecodes, list_devices

from bullpen.logging import LOGGER
from data.game_mode import GameMode
from data.rotation_control import RotationControl
from data.rotation_toggles import RotationToggles

# Unlike main.py, nothing here constructs a Config (which is what normally sets the
# bullpen logger's level based on config.json's "debug" flag), so without this the
# logger stays at its default level and every LOGGER.info() call below is silently dropped.
LOGGER.setLevel(logging.INFO)

# A cheap wireless keypad's RF dongle commonly exposes several separate event
# nodes under its chipset vendor's name (e.g. "Telink Wireless Receiver") rather
# than the keypad's own brand name -- one for the keyboard, one for the
# mouse/touchpad, one for consumer-control media keys, one for system-control
# power keys. Matching by name is unreliable across different keypads (and the
# node each one lands on isn't even stable across reboots on the same keypad), so
# instead require the specific keys/buttons this script binds to actually be
# present on the candidate device.
REQUIRED_KEYBOARD_KEYS = {
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
    ecodes.KEY_UP,
    ecodes.KEY_RIGHT,
    ecodes.KEY_G,
    ecodes.KEY_ENTER,
}
REQUIRED_MOUSE_BUTTONS = {ecodes.BTN_LEFT, ecodes.BTN_RIGHT}

TOGGLE_KEY_MAP = {
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
PAUSE_KEY = ecodes.KEY_UP
SKIP_KEY = ecodes.KEY_RIGHT
GAME_AREA_KEY = ecodes.KEY_G
CONFIRM_KEY = ecodes.KEY_ENTER


def find_keyboard_device() -> "InputDevice | None":
    for path in list_devices():
        device = InputDevice(path)
        keys = set(device.capabilities().get(ecodes.EV_KEY, []))
        if REQUIRED_KEYBOARD_KEYS.issubset(keys):
            return device
    return None


def find_mouse_device() -> "InputDevice | None":
    for path in list_devices():
        device = InputDevice(path)
        keys = set(device.capabilities().get(ecodes.EV_KEY, []))
        if REQUIRED_MOUSE_BUTTONS.issubset(keys):
            return device
    return None


def handle_keyboard_event(event, toggles: RotationToggles, control: RotationControl, game_mode: GameMode) -> None:
    key_event = categorize(event)
    if key_event.keystate != key_event.key_down:
        return

    if event.code == RESET_KEY:
        toggles.reset_all()
        LOGGER.info("Rotation toggles reset: everything enabled")
    elif event.code == PAUSE_KEY:
        paused = control.toggle_paused()
        LOGGER.info("Rotation %s", "paused" if paused else "resumed")
    elif event.code == SKIP_KEY:
        control.request_skip()
        LOGGER.info("Skip requested")
    elif event.code == GAME_AREA_KEY:
        if game_mode.is_in_game_area():
            game_mode.exit_to_normal()
            LOGGER.info("Exited game area")
        else:
            game_mode.open_menu()
            LOGGER.info("Game menu opened")
    elif event.code == CONFIRM_KEY:
        game_mode.request_confirm()
    elif event.code in TOGGLE_KEY_MAP:
        kind = TOGGLE_KEY_MAP[event.code]
        new_state = not toggles.is_enabled(kind)
        toggles.set_enabled(kind, new_state)
        LOGGER.info("Toggled %s -> %s", kind, "on" if new_state else "off")


def handle_mouse_event(event, game_mode: GameMode) -> None:
    if event.code == ecodes.BTN_LEFT:
        direction = "left"
    elif event.code == ecodes.BTN_RIGHT:
        direction = "right"
    else:
        return

    if event.value == 1:  # button down
        game_mode.request_steer(direction)  # one-shot: the menu moves one slot per click
        game_mode.set_steer_held(direction, True)  # level: games can move continuously while held
    elif event.value == 0:  # button up
        game_mode.set_steer_held(direction, False)


def main() -> None:
    keyboard = find_keyboard_device()
    mouse = find_mouse_device()
    if keyboard is None or mouse is None:
        LOGGER.error("Could not find required device(s). keyboard=%s mouse=%s. Available devices:", keyboard, mouse)
        for path in list_devices():
            LOGGER.error("  %s: %s", path, InputDevice(path).name)
        sys.exit(1)

    LOGGER.info("Listening for keys on %s (%s)", keyboard.name, keyboard.path)
    LOGGER.info("Listening for L/R clicks on %s (%s)", mouse.name, mouse.path)

    toggles = RotationToggles()
    control = RotationControl()
    game_mode = GameMode()

    sel = selectors.DefaultSelector()
    sel.register(keyboard, selectors.EVENT_READ, data="keyboard")
    sel.register(mouse, selectors.EVENT_READ, data="mouse")

    while True:
        for key, _ in sel.select():
            device = key.fileobj
            for event in device.read():
                if event.type != ecodes.EV_KEY:
                    continue
                if key.data == "keyboard":
                    handle_keyboard_event(event, toggles, control, game_mode)
                else:
                    handle_mouse_event(event, game_mode)


if __name__ == "__main__":
    main()
