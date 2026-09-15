import json
import time
from pathlib import Path
from typing import Optional

from bullpen.logging import LOGGER

STATE_PATH = Path(__file__).parent.parent / "game_mode.json"
RELOAD_CHECK_INTERVAL = 0.05  # short: steer nudges need to feel immediate during gameplay


class GameMode:
    """Live on/off + steering state for the toddler racer game, backed by a small JSON
    file (same pattern as RotationControl). When active, renderers/main.py's render()
    loop shows the racer plugin exclusively, bypassing the normal MLB/plugin rotation
    entirely, until game mode is turned off again.

    Write paths (set_active, toggle_active, request_steer) always force a fresh read
    before mutating -- same fix RotationControl needed for the same reason: the keypad
    listener and the display are separate processes, and a write built on a stale
    cached read can silently clobber a concurrent change from the other process.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or STATE_PATH
        self._active = False
        self._steer: Optional[str] = None
        self._mtime: Optional[float] = None
        self._last_check = 0.0
        self._load(force=True)

    def is_active(self) -> bool:
        self._maybe_reload()
        return self._active

    def set_active(self, active: bool) -> None:
        self._load(force=True)
        self._active = active
        self._steer = None
        self._save()

    def toggle_active(self) -> bool:
        self._load(force=True)
        self._active = not self._active
        self._steer = None
        self._save()
        return self._active

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
                self._active = False
                self._steer = None
            return

        if not force and mtime == self._mtime:
            return

        try:
            with open(self.path) as f:
                data = json.load(f)
            self._active = data.get("active", False)
            self._steer = data.get("steer")
            self._mtime = mtime
        except (json.JSONDecodeError, OSError) as e:
            LOGGER.warning("Failed to load game mode state from %s: %s", self.path, e)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump({"active": self._active, "steer": self._steer}, f, indent=2)
                f.write("\n")
            # Both the display and keypad listener write this file as root (systemd
            # User=root), but manual SSH/CLI use (toggle_rotation.py) runs as program27
            # -- without this, whichever process creates the file first locks the other
            # user out with a silent "Permission denied" on every subsequent write.
            self.path.chmod(0o666)
            self._mtime = self.path.stat().st_mtime
        except OSError as e:
            LOGGER.warning("Failed to save game mode state to %s: %s", self.path, e)
