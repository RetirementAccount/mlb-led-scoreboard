import tempfile
import unittest
from pathlib import Path

from mlb_led_scoreboard_toddler_racer.config import Config
from mlb_led_scoreboard_toddler_racer.renderer import (
    CAR_HEIGHT,
    CAR_STRIPE_COLORS_RGB,
    CAR_WIDTH,
    CAR_Y_MARGIN,
    HEART_MASK,
    OBSTACLE_WIDTH,
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
    # Isolate from the real project's game_mode.json -- point this instance's
    # GameMode at a throwaway file instead, so tests never touch production state
    # or race with an actual running display/keypad listener.
    renderer._game_mode.path = tmp_path / "game_mode.json"
    renderer._game_mode._screen = None
    renderer._game_mode._steer = None
    renderer._game_mode._confirm = False
    renderer._game_mode._steer_held_left = False
    renderer._game_mode._steer_held_right = False
    return renderer


def car_y(renderer: Renderer) -> int:
    return renderer.height - CAR_Y_MARGIN - CAR_HEIGHT


class TestRendererGameplay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.renderer = make_renderer(Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_starts_centered_on_the_road_with_full_lives_and_no_score(self):
        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertFalse(self.renderer.game_over)
        self.assertGreaterEqual(self.renderer.car_x, self.renderer.road_left)
        self.assertLessEqual(self.renderer.car_x + CAR_WIDTH, self.renderer.road_right)

    def test_steer_left_moves_car_left_and_clamps_at_road_edge(self):
        # The car moves continuously while the button is held (see
        # data/game_mode.py's held_direction()), so one set_steer_held call covers
        # every frame below -- no repeated taps needed.
        start_x = self.renderer.car_x
        self.renderer._game_mode.set_steer_held("left", True)
        self.renderer._consume_input()
        self.assertLess(self.renderer.car_x, start_x)

        for _ in range(50):  # far more than enough frames to hit the edge
            self.renderer._consume_input()
        self.assertEqual(self.renderer.car_x, self.renderer.road_left)

    def test_steer_right_clamps_at_road_edge(self):
        self.renderer._game_mode.set_steer_held("right", True)
        for _ in range(50):
            self.renderer._consume_input()
        self.assertEqual(self.renderer.car_x, self.renderer.road_right - CAR_WIDTH)

    def test_car_moves_continuously_while_held_without_repeated_taps(self):
        self.renderer._game_mode.set_steer_held("right", True)
        start_x = self.renderer.car_x

        self.renderer._consume_input()
        after_one_frame = self.renderer.car_x
        self.renderer._consume_input()
        after_two_frames = self.renderer.car_x

        self.assertGreater(after_one_frame, start_x)
        self.assertGreater(after_two_frames, after_one_frame)

    def test_steer_is_ignored_during_the_hit_animation(self):
        self.renderer.hit_animation_frames_remaining = 5
        start_x = self.renderer.car_x
        self.renderer._game_mode.set_steer_held("left", True)
        self.renderer._consume_input()
        self.assertEqual(self.renderer.car_x, start_x)

    def test_obstacle_spawns_after_configured_interval(self):
        self.assertEqual(len(self.renderer.obstacles), 0)
        for _ in range(self.renderer.config.spawn_interval_frames):
            self.renderer._advance()
        self.assertEqual(len(self.renderer.obstacles), 1)

    def test_colliding_with_an_obstacle_costs_a_life_and_starts_the_hit_animation(self):
        self.renderer.obstacles = [{"x": float(self.renderer.car_x), "y": float(car_y(self.renderer))}]

        self.renderer._advance()

        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives - 1)
        self.assertGreater(self.renderer.hit_animation_frames_remaining, 0)
        self.assertEqual(self.renderer.score, 0)

    def test_colliding_obstacle_despawns_immediately(self):
        self.renderer.obstacles = [{"x": float(self.renderer.car_x), "y": float(car_y(self.renderer))}]

        self.renderer._advance()

        self.assertEqual(self.renderer.obstacles, [])

    def test_gameplay_is_frozen_during_the_hit_animation(self):
        self.renderer.hit_animation_frames_remaining = 5
        self.renderer.lives = 2
        obstacle = {"x": 0.0, "y": 0.0}
        self.renderer.obstacles = [obstacle]

        self.renderer._advance()

        self.assertEqual(obstacle["y"], 0.0)  # nothing moved
        self.assertEqual(self.renderer.hit_animation_frames_remaining, 4)

    def test_passing_an_obstacle_without_hitting_it_scores_a_point(self):
        # An obstacle that falls past the bottom without ever overlapping the car --
        # unlike the old never-fail design, this is now the only way to score.
        self.renderer.config.spawn_interval_frames = 10_000  # disable auto-spawn for this test
        self.renderer.obstacles = [{"x": float(self.renderer.road_right + 100), "y": 0.0}]
        for _ in range(int(self.renderer.height / self.renderer.config.fall_speed) + 2):
            self.renderer._advance()

        self.assertEqual(self.renderer.score, 1)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.obstacles, [])  # fell off screen and was removed

    def test_game_over_triggers_only_after_the_hit_animation_finishes_on_last_life(self):
        # lives is already 0 here because the real flow decrements it *before*
        # starting the hit animation (see _advance()'s collision branch) -- by the
        # time the animation is running on what was the last life, lives is 0.
        self.renderer.lives = 0
        self.renderer.hit_animation_frames_remaining = 1

        self.renderer._advance()  # this tick brings the animation counter to 0

        self.assertTrue(self.renderer.game_over)

    def test_game_over_does_not_trigger_early_with_lives_remaining(self):
        self.renderer.lives = 2
        self.renderer.hit_animation_frames_remaining = 1

        self.renderer._advance()

        self.assertFalse(self.renderer.game_over)

    def test_confirm_during_game_over_restarts(self):
        self.renderer.game_over = True
        self.renderer.score = 999
        self.renderer.lives = 0

        self.renderer._game_mode.request_confirm()
        self.renderer._consume_input()

        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)

    def test_nothing_advances_once_game_over(self):
        self.renderer.game_over = True
        obstacle = {"x": 0.0, "y": 0.0}
        self.renderer.obstacles = [obstacle]

        self.renderer._advance()

        self.assertEqual(obstacle["y"], 0.0)

    def test_reset_clears_score_lives_obstacles_and_game_over(self):
        self.renderer.score = 5
        self.renderer.lives = 0
        self.renderer.game_over = True
        self.renderer.obstacles = [{"x": 0.0, "y": 0.0}]

        self.renderer.reset()

        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.obstacles, [])

    def test_car_height_matches_the_number_of_rainbow_stripes(self):
        # One row per hue (red/orange/yellow/green/blue/violet) top to bottom, per
        # Eric's toddler's request -- CAR_HEIGHT is derived from the stripe list so
        # they can never silently drift apart.
        self.assertEqual(CAR_HEIGHT, len(CAR_STRIPE_COLORS_RGB))
        self.assertEqual(CAR_STRIPE_COLORS_RGB[0], (255, 0, 0))  # red on top
        self.assertEqual(CAR_STRIPE_COLORS_RGB[-1], (148, 0, 211))  # violet on the bottom

    def test_no_heart_sprite_by_default(self):
        # No heart.png is checked into the repo (Eric supplies his own) -- confirm
        # the fallback mask path is what's active by default.
        self.assertIsNone(self.renderer._heart_sprite)
        self.assertEqual(len(HEART_MASK), 5)
        self.assertTrue(all(len(row) == 5 for row in HEART_MASK))

    def test_road_is_narrower_than_the_panel_and_centered(self):
        self.assertGreater(self.renderer.road_left, 0)
        self.assertLess(self.renderer.road_right, self.renderer.width)
        self.assertGreaterEqual(self.renderer.road_right - self.renderer.road_left, OBSTACLE_WIDTH)


if __name__ == "__main__":
    unittest.main()
