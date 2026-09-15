import bullpen.api as api

from .config import Config
from .data import Data
from .renderer import Renderer


def load() -> api.PLUGIN_DEFINITION:
    return Config, Data, Renderer
