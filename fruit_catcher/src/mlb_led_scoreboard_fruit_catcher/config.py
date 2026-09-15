import bullpen.api as api

DEFAULT_STEER_STEP = 3  # pixels the catcher moves per L/R click
DEFAULT_FALL_SPEED = 1.0  # pixels per frame every object falls
DEFAULT_DIAGONAL_SPEED = 0.5  # horizontal pixels per frame for "diagonal" objects
DEFAULT_ZIGZAG_SPEED = 0.7  # horizontal pixels per frame for "zigzag" objects
DEFAULT_ZIGZAG_PERIOD_FRAMES = 10  # frames between zigzag direction flips
DEFAULT_SPAWN_INTERVAL_FRAMES = 20
DEFAULT_BOMB_CHANCE = 0.15  # fraction of spawns that are the bomb instead of a fruit
DEFAULT_FRAME_SECONDS = 0.1  # ~10fps
DEFAULT_STARTING_LIVES = 3
DEFAULT_HIT_ANIMATION_FRAMES = 20  # ~2s at 0.1s/frame -- catcher "spins", gameplay paused


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        plugin_config = base.plugin_config
        self.steer_step = plugin_config.get("steer_step", DEFAULT_STEER_STEP)
        self.fall_speed = plugin_config.get("fall_speed", DEFAULT_FALL_SPEED)
        self.diagonal_speed = plugin_config.get("diagonal_speed", DEFAULT_DIAGONAL_SPEED)
        self.zigzag_speed = plugin_config.get("zigzag_speed", DEFAULT_ZIGZAG_SPEED)
        self.zigzag_period_frames = plugin_config.get("zigzag_period_frames", DEFAULT_ZIGZAG_PERIOD_FRAMES)
        self.spawn_interval_frames = plugin_config.get("spawn_interval_frames", DEFAULT_SPAWN_INTERVAL_FRAMES)
        self.bomb_chance = plugin_config.get("bomb_chance", DEFAULT_BOMB_CHANCE)
        self.frame_seconds = plugin_config.get("frame_seconds", DEFAULT_FRAME_SECONDS)
        self.starting_lives = plugin_config.get("starting_lives", DEFAULT_STARTING_LIVES)
        self.hit_animation_frames = plugin_config.get("hit_animation_frames", DEFAULT_HIT_ANIMATION_FRAMES)
