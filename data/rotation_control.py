import json
import time
from pathlib import Path
from typing import Optional

from bullpen.logging import LOGGER

STATE_PATH = Path(__file__).parent.parent / "rotation_control.json"
# How often is_paused()/consume_skip() (called every render frame, up to ~20x/sec during
# MLB game scrolling) re-check the file for external changes. stat() is cheap, so this can
# be short -- it directly bounds how long a skip/pause from another process takes to be
# noticed. Write methods (set_paused, request_skip, ...) always force a fresh read before
# mutating regardless of this interval: they're rare, human-triggered actions, not called
# in a tight loop, so there's no throttling benefit -- only a correctness risk, since a
# write based on stale cached state can silently clobber a concurrent change from the
# other process (this was the cause of "pressing skip twice quickly re-shows the same
# screen instead of advancing twice").
RELOAD_CHECK_INTERVAL = 0.1


class RotationControl:
    """Live pause/skip control for the rotation loop, backed by a small JSON file.

    Separate from RotationToggles (which is per-category on/off, persistent) since this
    is transient control state: paused freezes whatever screen is currently showing
    (ignoring its normal timer/scroll-completion entirely), and skip is a one-shot
    "end the current screen right now" signal consumed by the render loop.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or STATE_PATH
        self._paused = False
        self._skip = False
        self._mtime: Optional[float] = None
        self._last_check = 0.0
        self._load(force=True)

    def is_paused(self) -> bool:
        self._maybe_reload()
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._load(force=True)
        self._paused = paused
        self._save()

    def toggle_paused(self) -> bool:
        self._load(force=True)
        self._paused = not self._paused
        self._save()
        return self._paused

    def request_skip(self) -> None:
        self._load(force=True)
        self._skip = True
        self._save()

    def consume_skip(self) -> bool:
        """Return True (once) if a skip was requested, clearing the flag as a side effect."""
        self._maybe_reload()
        if self._skip:
            self._skip = False
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
                self._paused = False
                self._skip = False
            return

        if not force and mtime == self._mtime:
            return

        try:
            with open(self.path) as f:
                data = json.load(f)
            self._paused = data.get("paused", False)
            self._skip = data.get("skip", False)
            self._mtime = mtime
        except (json.JSONDecodeError, OSError) as e:
            LOGGER.warning("Failed to load rotation control state from %s: %s", self.path, e)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump({"paused": self._paused, "skip": self._skip}, f, indent=2)
                f.write("\n")
            self._mtime = self.path.stat().st_mtime
        except OSError as e:
            LOGGER.warning("Failed to save rotation control state to %s: %s", self.path, e)
