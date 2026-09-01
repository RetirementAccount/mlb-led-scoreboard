import bullpen.api as api

from .config import EPLConfig, NBAConfig, NCAABConfig, NCAAFConfig, NFLConfig, NHLConfig
from .data import Data
from .renderer import Renderer


def load_nfl() -> api.PLUGIN_DEFINITION:
    return NFLConfig, Data, Renderer


def load_nhl() -> api.PLUGIN_DEFINITION:
    return NHLConfig, Data, Renderer


def load_nba() -> api.PLUGIN_DEFINITION:
    return NBAConfig, Data, Renderer


def load_ncaaf() -> api.PLUGIN_DEFINITION:
    return NCAAFConfig, Data, Renderer


def load_ncaab() -> api.PLUGIN_DEFINITION:
    return NCAABConfig, Data, Renderer


def load_epl() -> api.PLUGIN_DEFINITION:
    return EPLConfig, Data, Renderer
