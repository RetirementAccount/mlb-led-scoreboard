from bullpen.api import PluginData, UpdateStatus

from .config import Config


class Data(PluginData):
    """No externally-fetched data -- the menu's selection state lives on the Renderer
    instance (see toddler_racer/data.py for the same pattern and why: this plugin is
    never part of the timed rotation, so update() is never called by the normal
    main-loop refresh path)."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def update(self, force: bool = False) -> UpdateStatus:
        return UpdateStatus.DEFERRED
