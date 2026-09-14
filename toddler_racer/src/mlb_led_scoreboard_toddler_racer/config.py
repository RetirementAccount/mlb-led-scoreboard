import bullpen.api as api

DEFAULT_STEER_STEP = 3  # pixels the car moves per L/R click
DEFAULT_FALL_SPEED = 1.0  # pixels per frame the obstacles fall
DEFAULT_SPAWN_INTERVAL_FRAMES = 25  # roughly how often a new obstacle appears
DEFAULT_FRAME_SECONDS = 0.1  # ~10fps -- smooth enough on an LED matrix, gentle enough for a toddler


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        plugin_config = base.plugin_config
        self.steer_step = plugin_config.get("steer_step", DEFAULT_STEER_STEP)
        self.fall_speed = plugin_config.get("fall_speed", DEFAULT_FALL_SPEED)
        self.spawn_interval_frames = plugin_config.get("spawn_interval_frames", DEFAULT_SPAWN_INTERVAL_FRAMES)
        self.frame_seconds = plugin_config.get("frame_seconds", DEFAULT_FRAME_SECONDS)
