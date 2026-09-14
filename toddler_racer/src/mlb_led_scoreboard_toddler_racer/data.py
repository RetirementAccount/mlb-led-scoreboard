from bullpen.api import PluginData, UpdateStatus

from .config import Config


class Data(PluginData):
    """No externally-fetched data -- all game state lives on the Renderer instance and
    is advanced directly inside render() each frame while game mode is active (see
    renderers/main.py and data/game_mode.py). This plugin is never part of the timed
    rotation, so its update() is never called by the normal main-loop refresh path;
    this class exists only to satisfy the PluginData interface."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def update(self, force: bool = False) -> UpdateStatus:
        return UpdateStatus.DEFERRED
