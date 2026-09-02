import json
import time
from pathlib import Path
from typing import Optional

from bullpen.logging import LOGGER

STATE_PATH = Path(__file__).parent.parent / "rotation_toggles.json"
RELOAD_CHECK_INTERVAL = 2.0  # seconds between checking the state file for external changes

ALL_KINDS = ["game", "news", "standings", "nfl", "nhl", "nba", "ncaaf", "ncaab", "epl"]


class RotationToggles:
    """Live, on/off state per rotation category (MLB games + each plugin screen).

    Backed by a small JSON file separate from config.json, since this is meant to be
    flipped frequently at runtime (by a keypad listener or an ad-hoc CLI command) rather
    than edited by hand. A running display process picks up external changes to the file
    within RELOAD_CHECK_INTERVAL seconds, without needing a restart.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or STATE_PATH
        self._enabled: dict[str, bool] = {}
        self._mtime: Optional[float] = None
        self._last_check = 0.0
        self._load(force=True)

    def is_enabled(self, kind: str) -> bool:
        self._maybe_reload()
        return self._enabled.get(kind, True)

    def set_enabled(self, kind: str, enabled: bool) -> None:
        # Always read fresh before mutating (not the throttled check used by is_enabled(),
        # which is called from the display's tight render loop) -- this is a rare,
        # human-triggered write, so there's no throttling benefit, only a correctness risk:
        # writing from a stale cached read can clobber a concurrent change from the other
        # process (keypad listener vs. display, or two quick keypresses).
        self._load(force=True)
        self._enabled[kind] = enabled
        self._save()

    def reset_all(self, kinds: list[str] = ALL_KINDS) -> None:
        self._enabled = {kind: True for kind in kinds}
        self._save()

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
                self._enabled = {}
            return

        if not force and mtime == self._mtime:
            return

        try:
            with open(self.path) as f:
                self._enabled = json.load(f)
            self._mtime = mtime
        except (json.JSONDecodeError, OSError) as e:
            LOGGER.warning("Failed to load rotation toggle state from %s: %s", self.path, e)

    def _save(self) -> None:
        try:
            with open(self.path, "w") as f:
                json.dump(self._enabled, f, indent=2)
                f.write("\n")
            self._mtime = self.path.stat().st_mtime
        except OSError as e:
            LOGGER.warning("Failed to save rotation toggle state to %s: %s", self.path, e)
