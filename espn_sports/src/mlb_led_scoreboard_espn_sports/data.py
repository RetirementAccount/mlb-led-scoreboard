import time
from typing import Optional

from PIL import Image

from bullpen.api import PluginData, UpdateStatus
from bullpen.logging import LOGGER

from . import client, logos
from .config import ConfigBase
from .models import Game, TeamScore, matches_favorite_team, parse_scoreboard


class Data(PluginData):
    def __init__(self, config: ConfigBase) -> None:
        self.config = config
        self.games: list[Game] = []
        self._last_update = 0.0
        self._logo_cache: dict[str, Optional[Image.Image]] = {}
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
        if self.config.show_logos:
            self.__fetch_missing_logos(games)

        LOGGER.debug("[%s] Loaded %d game(s)", self.config.league_name, len(games))
        return UpdateStatus.SUCCESS

    def logo_for(self, team: TeamScore) -> Optional[Image.Image]:
        if team.logo_url is None:
            return None
        return self._logo_cache.get(team.logo_url)

    def __fetch_missing_logos(self, games: list[Game]) -> None:
        for game in games:
            for team in (game.home, game.away):
                if team.logo_url and team.logo_url not in self._logo_cache:
                    self._logo_cache[team.logo_url] = logos.fetch_logo(team.logo_url, self.config.logo_size)

    def __should_update(self) -> bool:
        return (time.time() - self._last_update) >= self.config.refresh_seconds
