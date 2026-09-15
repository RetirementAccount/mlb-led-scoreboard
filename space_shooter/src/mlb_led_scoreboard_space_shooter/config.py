import bullpen.api as api

DEFAULT_STEER_STEP = 2  # pixels the ship moves per frame while a direction is held
DEFAULT_ENEMY_SPEED = 1.0  # pixels per frame enemies (and the pickup) drift leftward
DEFAULT_BULLET_SPEED = 2.0  # pixels per frame player bullets travel rightward
DEFAULT_SPAWN_INTERVAL_FRAMES = 25  # roughly how often a new enemy/pickup appears
DEFAULT_PICKUP_CHANCE = 0.15  # fraction of spawns that are the gun upgrade instead of an enemy
DEFAULT_FIRE_INTERVAL_FRAMES = 5  # ~2 volleys/sec at 10fps -- auto-fire, no button needed
DEFAULT_FRAME_SECONDS = 0.1  # ~10fps, matches the other games in the suite
DEFAULT_STARTING_LIVES = 3
DEFAULT_HIT_FLICKER_FRAMES = 10  # brief invulnerability + visual flicker after taking a hit
# Hits an enemy survives before being destroyed -- each non-fatal hit chips another
# 2x2 corner off its sprite (Centipede-style) instead of instantly destroying it.
# With a wide/rapid-fire upgraded gun, one-shot kills made the game trivial once
# the player had the gun for a while; more HP re-introduces friction without
# nerfing the gun itself.
DEFAULT_ENEMY_MAX_HITS = 4


class Config(api.PluginConfig):
    def __init__(self, base: api.MLBConfig) -> None:
        plugin_config = base.plugin_config
        self.steer_step = plugin_config.get("steer_step", DEFAULT_STEER_STEP)
        self.enemy_speed = plugin_config.get("enemy_speed", DEFAULT_ENEMY_SPEED)
        self.bullet_speed = plugin_config.get("bullet_speed", DEFAULT_BULLET_SPEED)
        self.spawn_interval_frames = plugin_config.get("spawn_interval_frames", DEFAULT_SPAWN_INTERVAL_FRAMES)
        self.pickup_chance = plugin_config.get("pickup_chance", DEFAULT_PICKUP_CHANCE)
        self.fire_interval_frames = plugin_config.get("fire_interval_frames", DEFAULT_FIRE_INTERVAL_FRAMES)
        self.frame_seconds = plugin_config.get("frame_seconds", DEFAULT_FRAME_SECONDS)
        self.starting_lives = plugin_config.get("starting_lives", DEFAULT_STARTING_LIVES)
        self.hit_flicker_frames = plugin_config.get("hit_flicker_frames", DEFAULT_HIT_FLICKER_FRAMES)
        self.enemy_max_hits = plugin_config.get("enemy_max_hits", DEFAULT_ENEMY_MAX_HITS)
