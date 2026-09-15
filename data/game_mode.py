import json
import time
from pathlib import Path
from typing import Optional

from bullpen.logging import LOGGER

STATE_PATH = Path(__file__).parent.parent / "game_mode.json"
RELOAD_CHECK_INTERVAL = 0.05  # short: steer/confirm need to feel immediate during gameplay


class GameMode:
    """Live control for the "game area" -- a menu screen plus any number of simple
    games, all just bullpen plugins dispatched exclusively (bypassing the normal
    ticker rotation), the same way the original single-game override worked. Backed
    by a small JSON file (same pattern as RotationControl).

    `screen` is None (normal ticker) or a plugin name -- either "game_menu" or an
    actual game's entry-point name. There's no separate "menu" concept in the data
    model: the menu is just another plugin, dispatched by renderers/main.py exactly
    like a game is.

    Write paths (open_menu, launch, exit_to_normal, request_steer, request_confirm)
    always force a fresh read before mutating -- same fix RotationControl needed for
    the same reason: the keypad listener and the display are separate processes, and
    a write built on a stale cached read can silently clobber a concurrent change
    from the other process.
    """

    MENU_PLUGIN = "game_menu"

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or STATE_PATH
        self._screen: Optional[str] = None
        self._steer: Optional[str] = None
        self._confirm = False
        self._steer_held_left = False
        self._steer_held_right = False
        self._mtime: Optional[float] = None
        self._last_check = 0.0
        self._load(force=True)

    def current_screen(self) -> Optional[str]:
        self._maybe_reload()
        return self._screen

    def is_in_game_area(self) -> bool:
        return self.current_screen() is not None

    def open_menu(self) -> None:
        self._set_screen(self.MENU_PLUGIN)

    def launch(self, game_plugin_name: str) -> None:
        self._set_screen(game_plugin_name)

    def exit_to_normal(self) -> None:
        self._set_screen(None)

    def _set_screen(self, screen: Optional[str]) -> None:
        self._load(force=True)
        self._screen = screen
        self._steer = None
        self._confirm = False
        self._save()

    def request_steer(self, direction: str) -> None:
        assert direction in ("left", "right")
        self._load(force=True)
        self._steer = direction
        self._save()

    def consume_steer(self) -> Optional[str]:
        """Return the pending steer direction (once), clearing it as a side effect."""
        self._maybe_reload()
        if self._steer is not None:
            direction = self._steer
            self._steer = None
            self._save()
            return direction
        return None

    def set_steer_held(self, direction: str, held: bool) -> None:
        """Level-triggered companion to request_steer/consume_steer: tracks whether
        the L/R button is currently physically down, for games that want smooth
        continuous movement while held rather than one bump per tap. The menu still
        uses the one-shot request_steer/consume_steer pair -- one move per click."""
        assert direction in ("left", "right")
        self._load(force=True)
        if direction == "left":
            self._steer_held_left = held
        else:
            self._steer_held_right = held
        self._save()

    def held_direction(self) -> Optional[str]:
        """The currently-held direction, or None if neither/both buttons are down."""
        self._maybe_reload()
        if self._steer_held_left and not self._steer_held_right:
            return "left"
        if self._steer_held_right and not self._steer_held_left:
            return "right"
        return None

    def request_confirm(self) -> None:
        self._load(force=True)
        self._confirm = True
        self._save()

    def consume_confirm(self) -> bool:
        """Return True (once) if confirm was requested, clearing it as a side effect."""
        self._maybe_reload()
        if self._confirm:
            self._confirm = False
            self._save()
            return True
        return False

    def _maybe_reload(self) -> None:
        now = time.time()
        if now - self._last_check < RELOAD_CHECK_INTERVAL:
            return
        self._last_check = now
        self._load()

    def _load(self, force: bool = False) -> None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            if force:
                self._screen = None
                self._steer = None
                self._confirm = False
                self._steer_held_left = False
                self._steer_held_right = False
            return

        if not force and mtime == self._mtime:
            return

        try:
            with open(self.path) as f:
                data = json.load(f)
            self._screen = data.get("screen")
            self._steer = data.get("steer")
            self._confirm = data.get("confirm", False)
            self._steer_held_left = data.get("steer_held_left", False)
            self._steer_held_right = data.get("steer_held_right", False)
            self._mtime = mtime
        except (json.JSONDecodeError, OSError) as e:
            LOGGER.warning("Failed to load game mode state from %s: %s", self.path, e)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(
                    {
                        "screen": self._screen,
                        "steer": self._steer,
                        "confirm": self._confirm,
                        "steer_held_left": self._steer_held_left,
                        "steer_held_right": self._steer_held_right,
                    },
                    f,
                    indent=2,
                )
                f.write("\n")
            # Both the display and keypad listener write this file as root (systemd
            # User=root), but manual SSH/CLI use (toggle_rotation.py) runs as program27
            # -- without this, whichever process creates the file first locks the other
            # user out with a silent "Permission denied" on every subsequent write.
            self.path.chmod(0o666)
            self._mtime = self.path.stat().st_mtime
        except OSError as e:
            LOGGER.warning("Failed to save game mode state to %s: %s", self.path, e)
