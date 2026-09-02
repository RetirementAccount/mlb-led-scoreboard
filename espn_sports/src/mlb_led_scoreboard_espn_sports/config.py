import bullpen.api as api

DEFAULT_REFRESH_SECONDS = 60
DEFAULT_LOGO_SIZE = 12


class ConfigBase(api.PluginConfig):
    """Shared config for all ESPN-backed sports plugins.

    Subclasses only need to set the three class attributes below; per-league behavior
    (favorite team filtering, refresh rate) is identical and driven by that league's
    entry under the top-level "plugins" config key, e.g. "plugins": {"nfl": {"teams": ["Bills"]}}.
    """

    SPORT_PATH: str = ""
    LEAGUE_KEY: str = ""
    LEAGUE_NAME: str = ""

    def __init__(self, base: api.MLBConfig) -> None:
        self.sport_path = self.SPORT_PATH
        self.league_key = self.LEAGUE_KEY
        self.league_name = self.LEAGUE_NAME
        self.scrolling_speed = base.scrolling_speed

        plugin_config = base.plugin_config
        teams = plugin_config.get("teams", [])
        if isinstance(teams, str):
            teams = [teams]
        self.favorite_teams_lower = [t.lower() for t in teams]
        self.refresh_seconds = plugin_config.get("refresh_seconds", DEFAULT_REFRESH_SECONDS)
        self.show_logos = bool(plugin_config.get("show_logos", False))
        self.logo_size = plugin_config.get("logo_size", DEFAULT_LOGO_SIZE)


class NFLConfig(ConfigBase):
    SPORT_PATH = "football/nfl"
    LEAGUE_KEY = "nfl"
    LEAGUE_NAME = "NFL"


class NHLConfig(ConfigBase):
    SPORT_PATH = "hockey/nhl"
    LEAGUE_KEY = "nhl"
    LEAGUE_NAME = "NHL"


class NBAConfig(ConfigBase):
    SPORT_PATH = "basketball/nba"
    LEAGUE_KEY = "nba"
    LEAGUE_NAME = "NBA"


class NCAAFConfig(ConfigBase):
    SPORT_PATH = "football/college-football"
    LEAGUE_KEY = "ncaaf"
    LEAGUE_NAME = "NCAAF"


class NCAABConfig(ConfigBase):
    SPORT_PATH = "basketball/mens-college-basketball"
    LEAGUE_KEY = "ncaab"
    LEAGUE_NAME = "NCAAB"


class EPLConfig(ConfigBase):
    SPORT_PATH = "soccer/eng.1"
    LEAGUE_KEY = "epl"
    LEAGUE_NAME = "EPL"
