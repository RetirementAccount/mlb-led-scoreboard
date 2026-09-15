import bullpen.api as api

DEFAULT_STEER_STEP = 3  # pixels the car moves per L/R click
DEFAULT_FALL_SPEED = 1.0  # pixels per frame the obstacles fall
DEFAULT_SPAWN_INTERVAL_FRAMES = 25  # roughly how often a new obstacle appears
DEFAULT_FRAME_SECONDS = 0.1  # ~10fps -- smooth enough on an LED matrix, gentle enough for a toddler
DEFAULT_STARTING_LIVES = 3
# 2 full spins (renderer.py's SPIN_CYCLE_FRAMES=8 is one squash-cycle "spin") --
# ~1.6s at 0.1s/frame. Race is fully frozen for this whole duration (see
# Renderer._advance): no obstacles move or spawn, so the one that hit the car can't
# immediately hit it again once play resumes -- it's already been removed by then.
DEFAULT_HIT_ANIMATION_FRAMES = 16


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        plugin_config = base.plugin_config
        self.steer_step = plugin_config.get("steer_step", DEFAULT_STEER_STEP)
        self.fall_speed = plugin_config.get("fall_speed", DEFAULT_FALL_SPEED)
        self.spawn_interval_frames = plugin_config.get("spawn_interval_frames", DEFAULT_SPAWN_INTERVAL_FRAMES)
        self.frame_seconds = plugin_config.get("frame_seconds", DEFAULT_FRAME_SECONDS)
        self.starting_lives = plugin_config.get("starting_lives", DEFAULT_STARTING_LIVES)
        self.hit_animation_frames = plugin_config.get("hit_animation_frames", DEFAULT_HIT_ANIMATION_FRAMES)
