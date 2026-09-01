import time

from bullpen.api import PluginData, UpdateStatus
from bullpen.logging import LOGGER

from . import client
from .config import ConfigBase
from .models import Game, matches_favorite_team, parse_scoreboard


class Data(PluginData):
    def __init__(self, config: ConfigBase) -> None:
        self.config = config
        self.games: list[Game] = []
        self._last_update = 0.0
        self.update(force=True)

    def update(self, force: bool = False) -> UpdateStatus:
        if not force and not self.__should_update():
            return UpdateStatus.DEFERRED

        self._last_update = time.time()
        raw = client.fetch_scoreboard(self.config.sport_path)
        if raw is None:
            return UpdateStatus.FAIL

        games = parse_scoreboard(raw)
        if self.config.favorite_teams_lower:
            games = [g for g in games if matches_favorite_team(g, self.config.favorite_teams_lower)]

        self.games = games
        LOGGER.debug("[%s] Loaded %d game(s)", self.config.league_name, len(games))
        return UpdateStatus.SUCCESS

    def __should_update(self) -> bool:
        return (time.time() - self._last_update) >= self.config.refresh_seconds
