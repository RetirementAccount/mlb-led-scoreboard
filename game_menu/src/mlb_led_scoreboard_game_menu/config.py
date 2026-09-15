import bullpen.api as api


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        self.config = base
