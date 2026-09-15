import tempfile
import unittest
from pathlib import Path

from mlb_led_scoreboard_space_shooter.config import Config
from mlb_led_scoreboard_space_shooter.renderer import (
    ENEMY_HEIGHT,
    ENEMY_KILL_POINTS,
    ENEMY_WIDTH,
    ENGINE_FLAME_CYCLE_RGB,
    ENGINE_FLAME_FRAMES_PER_COLOR,
    GUN_LANES,
    LIGHT_CHASE_FRAMES_PER_STEP,
    MAX_GUN_LEVEL,
    PICKUP_HEIGHT,
    PICKUP_WIDTH,
    PLAYER_HEIGHT,
    PLAYER_WIDTH,
    PLAYER_X,
    Renderer,
)


class FakeMLBConfig:
    plugin_config = {}


class FakeLayout:
    width = 64
    height = 32

    def font(self, keypath):
        return {"font": None, "size": {"width": 4, "height": 6}}


def make_renderer(tmp_path: Path) -> Renderer:
    renderer = Renderer(Config(FakeMLBConfig()), FakeLayout(), colors=None)
    # Isolate from the real project's game_mode.json -- same reasoning as the other
    # games' tests: never touch production state or race with an actual running
    # display/keypad listener.
    renderer._game_mode.path = tmp_path / "game_mode.json"
    renderer._game_mode._screen = None
    renderer._game_mode._steer = None
    renderer._game_mode._confirm = False
    renderer._game_mode._steer_held_left = False
    renderer._game_mode._steer_held_right = False
    return renderer


class TestSpaceShooterGameplay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.renderer = make_renderer(Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_starts_centered_with_full_lives_gun_level_one_no_score(self):
        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.gun_level, 1)
        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.player_y, (self.renderer.height - PLAYER_HEIGHT) // 2)

    def test_held_up_moves_the_ship_up_and_clamps_at_the_top(self):
        self.renderer._game_mode.set_steer_held("left", True)  # "left" == up
        for _ in range(50):
            self.renderer._consume_input()
        self.assertEqual(self.renderer.player_y, 0)

    def test_held_down_moves_the_ship_down_and_clamps_at_the_bottom(self):
        self.renderer._game_mode.set_steer_held("right", True)  # "right" == down
        for _ in range(50):
            self.renderer._consume_input()
        self.assertEqual(self.renderer.player_y, self.renderer.height - PLAYER_HEIGHT)

    def test_ship_moves_continuously_while_held_without_repeated_taps(self):
        self.renderer._game_mode.set_steer_held("right", True)
        start_y = self.renderer.player_y

        self.renderer._consume_input()
        after_one = self.renderer.player_y
        self.renderer._consume_input()
        after_two = self.renderer.player_y

        self.assertGreater(after_one, start_y)
        self.assertGreater(after_two, after_one)

    def test_enemy_spawns_after_configured_interval(self):
        self.renderer.config.pickup_chance = 0.0  # force an enemy, not a pickup
        self.assertEqual(len(self.renderer.enemies), 0)
        for _ in range(self.renderer.config.spawn_interval_frames):
            self.renderer._advance()
        self.assertEqual(len(self.renderer.enemies), 1)

    def test_auto_fire_spawns_a_bullet_without_any_button(self):
        self.assertEqual(len(self.renderer.bullets), 0)
        for _ in range(self.renderer.config.fire_interval_frames):
            self.renderer._advance()
        self.assertGreater(len(self.renderer.bullets), 0)

    def test_bullet_destroys_an_enemy_and_scores_points(self):
        self.renderer.enemies = [{"x": 10.0, "y": 10.0}]
        self.renderer.bullets = [{"x": 10.0, "y": 10.0, "shape": "dash", "dy": 0.0}]

        self.renderer._resolve_collisions()

        self.assertEqual(self.renderer.enemies, [])
        self.assertEqual(self.renderer.bullets, [])
        self.assertEqual(self.renderer.score, ENEMY_KILL_POINTS)

    def test_enemy_colliding_with_the_player_costs_a_life_and_starts_flicker(self):
        self.renderer.enemies = [{"x": float(PLAYER_X), "y": float(self.renderer.player_y)}]

        self.renderer._advance()

        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives - 1)
        self.assertGreater(self.renderer.hit_flicker_frames_remaining, 0)
        self.assertEqual(self.renderer.enemies, [])  # despawns immediately

    def test_player_is_invulnerable_during_the_flicker(self):
        self.renderer.hit_flicker_frames_remaining = 5
        self.renderer.enemies = [{"x": float(PLAYER_X), "y": float(self.renderer.player_y)}]
        start_lives = self.renderer.lives

        self.renderer._advance()

        self.assertEqual(self.renderer.lives, start_lives)

    def test_flicker_does_not_stop_the_world_from_moving(self):
        self.renderer.hit_flicker_frames_remaining = 5
        enemy = {"x": 30.0, "y": 10.0}
        self.renderer.enemies = [enemy]
        start_x = enemy["x"]

        self.renderer._advance()

        self.assertLess(enemy["x"], start_x)

    def test_game_over_triggers_only_after_the_flicker_finishes_on_last_life(self):
        # lives is already 0 here because the real flow decrements it *before*
        # starting the flicker (see _resolve_collisions) -- by the time the flicker
        # is running on what was the last life, lives is 0.
        self.renderer.lives = 0
        self.renderer.hit_flicker_frames_remaining = 1

        self.renderer._advance()

        self.assertTrue(self.renderer.game_over)

    def test_game_over_does_not_trigger_early_with_lives_remaining(self):
        self.renderer.lives = 2
        self.renderer.hit_flicker_frames_remaining = 1

        self.renderer._advance()

        self.assertFalse(self.renderer.game_over)

    def test_confirm_during_game_over_restarts(self):
        self.renderer.game_over = True
        self.renderer.score = 999
        self.renderer.lives = 0
        self.renderer.gun_level = MAX_GUN_LEVEL

        self.renderer._game_mode.request_confirm()
        self.renderer._consume_input()

        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.gun_level, 1)

    def test_nothing_advances_once_game_over(self):
        self.renderer.game_over = True
        enemy = {"x": 30.0, "y": 10.0}
        self.renderer.enemies = [enemy]

        self.renderer._advance()

        self.assertEqual(enemy["x"], 30.0)

    def test_touching_the_pickup_upgrades_the_gun_without_costing_a_life(self):
        self.renderer.pickups = [{"x": float(PLAYER_X), "y": float(self.renderer.player_y)}]

        self.renderer._advance()

        self.assertEqual(self.renderer.gun_level, 2)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.pickups, [])

    def test_gun_level_is_capped_at_max(self):
        self.renderer.gun_level = MAX_GUN_LEVEL
        self.renderer.pickups = [{"x": float(PLAYER_X), "y": float(self.renderer.player_y)}]

        self.renderer._advance()

        self.assertEqual(self.renderer.gun_level, MAX_GUN_LEVEL)

    def test_bullets_pass_through_the_pickup_without_collecting_it(self):
        self.renderer.pickups = [{"x": 10.0, "y": 10.0}]
        self.renderer.bullets = [{"x": 10.0, "y": 10.0, "shape": "dash", "dy": 0.0}]

        self.renderer._resolve_collisions()

        self.assertEqual(len(self.renderer.pickups), 1)  # untouched
        self.assertEqual(len(self.renderer.bullets), 1)  # untouched
        self.assertEqual(self.renderer.gun_level, 1)

    def test_each_gun_level_has_more_or_equal_lanes_than_the_last(self):
        for level in range(1, MAX_GUN_LEVEL + 1):
            self.assertIn(level, GUN_LANES)
        self.assertEqual(len(GUN_LANES[1]), 1)
        self.assertGreaterEqual(len(GUN_LANES[2]), len(GUN_LANES[1]))
        self.assertGreaterEqual(len(GUN_LANES[3]), len(GUN_LANES[2]))

    def test_max_gun_level_fires_extra_diagonal_bouncing_bullets(self):
        self.renderer.gun_level = MAX_GUN_LEVEL
        self.renderer._fire()
        diagonal = [b for b in self.renderer.bullets if b["dy"] != 0]
        self.assertEqual(len(diagonal), 2)

    def test_diagonal_bullet_bounces_off_the_top_and_bottom_edges(self):
        bullet = {"x": 10.0, "y": 0.0, "shape": "dot", "dy": -1.0}
        self.renderer.bullets = [bullet]

        self.renderer._move_bullets()

        self.assertEqual(bullet["dy"], 1.0)  # flipped after hitting the top edge

    def test_bullet_despawns_past_the_right_edge(self):
        self.renderer.bullets = [{"x": float(self.renderer.width), "y": 10.0, "shape": "dash", "dy": 0.0}]

        self.renderer._move_bullets()

        self.assertEqual(self.renderer.bullets, [])

    def test_enemy_and_pickup_despawn_past_the_left_edge_with_no_penalty(self):
        self.renderer.enemies = [{"x": -float(ENEMY_WIDTH), "y": 5.0}]
        self.renderer.pickups = [{"x": -float(PICKUP_WIDTH), "y": 5.0}]

        self.renderer._move_enemies()
        self.renderer._move_pickups()

        self.assertEqual(self.renderer.enemies, [])
        self.assertEqual(self.renderer.pickups, [])
        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)

    def test_supplied_ship_enemy_and_pickup_sprites_all_load(self):
        # Eric has supplied ship.png, 3 enemy variants (UFO1/2/3.png), and
        # pickup.png -- confirm every lookup resolves to real art now.
        self.assertIsNotNone(self.renderer._ship_sprite)
        self.assertEqual(len(self.renderer._enemy_sprites), 3)
        self.assertIsNotNone(self.renderer._pickup_sprite)

    def test_enemy_sprite_variants_are_discovered_by_glob_not_a_fixed_list(self):
        # Adding UFOn.png later should need zero code changes -- confirm
        # _load_enemy_sprites actually globs the directory (currently 3 files:
        # UFO1/2/3.png) rather than looking for one hardcoded filename.
        sprites = self.renderer._load_enemy_sprites()
        self.assertEqual(len(sprites), 3)

    def test_ufo_landing_lights_are_auto_detected_from_the_supplied_sprite(self):
        # Eric's UFO1.png has 2 yellow pixels, 3px apart, on its bottom row --
        # confirm _find_lights picked that up rather than needing to be told.
        sprite_info = self.renderer._enemy_sprites[0]
        self.assertIsNotNone(sprite_info["light_row"])
        self.assertEqual(len(sprite_info["light_columns"]), 2)
        self.assertEqual(sprite_info["light_columns"][1] - sprite_info["light_columns"][0], 3)

    def test_ufo_landing_lights_chase_across_columns_over_time(self):
        sprite_info = self.renderer._enemy_sprites[0]
        spacing = sprite_info["light_columns"][1] - sprite_info["light_columns"][0]

        seen_phases = set()
        for frame in range(0, spacing * LIGHT_CHASE_FRAMES_PER_STEP * 2, LIGHT_CHASE_FRAMES_PER_STEP):
            self.renderer.frame_count = frame
            phase = (frame // LIGHT_CHASE_FRAMES_PER_STEP) % spacing
            seen_phases.add(phase)
        self.assertEqual(seen_phases, set(range(spacing)))  # every column offset gets a turn

    def test_ship_engine_pixel_is_auto_detected_from_the_supplied_sprite(self):
        # Eric's ship.png has one orange pixel on its back row.
        self.assertIsNotNone(self.renderer._ship_engine_pixel)

    def test_engine_flame_cycles_through_its_colors_over_time(self):
        seen = set()
        for frame in range(0, ENGINE_FLAME_FRAMES_PER_COLOR * len(ENGINE_FLAME_CYCLE_RGB) * 2, ENGINE_FLAME_FRAMES_PER_COLOR):
            self.renderer.frame_count = frame
            seen.add(self.renderer._current_engine_color())
        self.assertEqual(seen, set(ENGINE_FLAME_CYCLE_RGB))

    def test_reset_clears_everything(self):
        self.renderer.score = 500
        self.renderer.lives = 0
        self.renderer.gun_level = MAX_GUN_LEVEL
        self.renderer.game_over = True
        self.renderer.enemies = [{"x": 1.0, "y": 1.0}]
        self.renderer.pickups = [{"x": 1.0, "y": 1.0}]
        self.renderer.bullets = [{"x": 1.0, "y": 1.0, "shape": "dash", "dy": 0.0}]

        self.renderer._reset_game()

        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.gun_level, 1)
        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.enemies, [])
        self.assertEqual(self.renderer.pickups, [])
        self.assertEqual(self.renderer.bullets, [])


if __name__ == "__main__":
    unittest.main()
