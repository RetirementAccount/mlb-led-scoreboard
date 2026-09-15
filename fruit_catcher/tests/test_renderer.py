import tempfile
import unittest
from pathlib import Path

from mlb_led_scoreboard_fruit_catcher.config import Config
from mlb_led_scoreboard_fruit_catcher.renderer import (
    BASKET_TOP_WIDTH,
    OBJECT_WIDTH,
    PLAYFIELD_TOP,
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
    return renderer


def make_object(**overrides) -> dict:
    obj = {"x": 0.0, "y": float(PLAYFIELD_TOP), "type": "fruit", "fruit_index": 0, "pattern": "straight", "dir": 1, "zigzag_timer": 0, "caught": False}
    obj.update(overrides)
    return obj


class TestFruitCatcherGameplay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.renderer = make_renderer(Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_starts_with_full_lives_zero_score_not_game_over(self):
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertEqual(self.renderer.score, 0)
        self.assertFalse(self.renderer.game_over)

    def test_steer_clamps_at_playfield_edges(self):
        for _ in range(50):
            self.renderer._game_mode.request_steer("left")
            self.renderer._consume_input()
        self.assertEqual(self.renderer.catcher_x, 0)

        for _ in range(50):
            self.renderer._game_mode.request_steer("right")
            self.renderer._consume_input()
        self.assertEqual(self.renderer.catcher_x, self.renderer.width - BASKET_TOP_WIDTH)

    def test_straight_object_falls_without_moving_horizontally(self):
        obj = make_object(x=10.0, pattern="straight")
        self.renderer._move_object(obj)
        self.assertEqual(obj["x"], 10.0)
        self.assertGreater(obj["y"], PLAYFIELD_TOP)

    def test_diagonal_object_moves_horizontally_in_its_assigned_direction(self):
        obj = make_object(x=10.0, pattern="diagonal", dir=1)
        self.renderer._move_object(obj)
        self.assertGreater(obj["x"], 10.0)

        obj2 = make_object(x=10.0, pattern="diagonal", dir=-1)
        self.renderer._move_object(obj2)
        self.assertLess(obj2["x"], 10.0)

    def test_zigzag_object_flips_direction_after_its_period(self):
        obj = make_object(x=10.0, pattern="zigzag", dir=1, zigzag_timer=0)
        period = self.renderer.config.zigzag_period_frames
        for _ in range(period):
            self.renderer._move_object(obj)
        self.assertEqual(obj["dir"], -1)

    def test_objects_bounce_off_the_side_walls(self):
        obj = make_object(x=0.0, pattern="diagonal", dir=-1)
        self.renderer._move_object(obj)
        self.assertGreaterEqual(obj["x"], 0)
        self.assertEqual(obj["dir"], 1)

    def test_catching_a_fruit_scores_points_by_pattern(self):
        for pattern, points in (("straight", 50), ("diagonal", 100), ("zigzag", 150)):
            with self.subTest(pattern=pattern):
                self.renderer._reset_game()
                catcher_y = self.renderer.height - 2 - 4  # CATCHER_Y_MARGIN, BASKET_HEIGHT
                self.renderer.objects = [make_object(x=float(self.renderer.catcher_x), y=float(catcher_y), pattern=pattern)]
                self.renderer._advance()
                self.assertEqual(self.renderer.score, points)
                self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)

    def test_catching_the_bomb_costs_a_life_and_starts_the_hit_animation(self):
        catcher_y = self.renderer.height - 2 - 4
        self.renderer.objects = [make_object(x=float(self.renderer.catcher_x), y=float(catcher_y), type="bomb", pattern="straight")]

        self.renderer._advance()

        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives - 1)
        self.assertGreater(self.renderer.hit_animation_frames_remaining, 0)
        self.assertEqual(self.renderer.score, 0)

    def test_gameplay_is_frozen_during_the_hit_animation(self):
        self.renderer.hit_animation_frames_remaining = 5
        self.renderer.lives = 2
        obj = make_object(x=0.0, pattern="straight")
        self.renderer.objects = [obj]

        self.renderer._advance()

        # the object should not have moved, and no new object should have spawned
        self.assertEqual(obj["y"], float(PLAYFIELD_TOP))
        self.assertEqual(self.renderer.hit_animation_frames_remaining, 4)

    def test_steer_is_ignored_during_the_hit_animation(self):
        self.renderer.hit_animation_frames_remaining = 5
        start_x = self.renderer.catcher_x
        self.renderer._game_mode.request_steer("left")
        self.renderer._consume_input()
        self.assertEqual(self.renderer.catcher_x, start_x)

    def test_game_over_triggers_only_after_the_hit_animation_finishes_on_last_life(self):
        # lives is already 0 here because the real flow decrements it *before*
        # starting the hit animation (see _advance()'s bomb-catch branch) -- by the
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
        obj = make_object(x=0.0, pattern="straight")
        self.renderer.objects = [obj]

        self.renderer._advance()

        self.assertEqual(obj["y"], float(PLAYFIELD_TOP))

    def test_caught_fruit_despawns_immediately_instead_of_falling_past_the_catcher(self):
        catcher_y = self.renderer.height - 2 - 4  # CATCHER_Y_MARGIN, BASKET_HEIGHT
        self.renderer.objects = [make_object(x=float(self.renderer.catcher_x), y=float(catcher_y), pattern="straight")]

        self.renderer._advance()

        self.assertEqual(self.renderer.objects, [])

    def test_caught_bomb_despawns_immediately(self):
        catcher_y = self.renderer.height - 2 - 4
        self.renderer.objects = [make_object(x=float(self.renderer.catcher_x), y=float(catcher_y), type="bomb", pattern="straight")]

        self.renderer._advance()

        self.assertEqual(self.renderer.objects, [])

    def test_missing_sprite_falls_back_to_none_for_every_item(self):
        # No PNGs are checked into the repo (that's the point -- Eric supplies his
        # own), so every lookup should resolve to None and drawing should fall back
        # to the built-in color blobs rather than erroring.
        for key, sprite in self.renderer._sprites.items():
            with self.subTest(key=key):
                self.assertIsNone(sprite)

    def test_spawned_object_is_within_playfield_bounds(self):
        obj = self.renderer._spawn_object()
        self.assertGreaterEqual(obj["x"], 0)
        self.assertLessEqual(obj["x"], self.renderer.width - OBJECT_WIDTH)
        self.assertEqual(obj["y"], float(PLAYFIELD_TOP))

    def test_reset_clears_score_lives_objects_and_game_over(self):
        self.renderer.score = 500
        self.renderer.lives = 0
        self.renderer.game_over = True
        self.renderer.objects = [make_object()]

        self.renderer._reset_game()

        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.lives, self.renderer.config.starting_lives)
        self.assertFalse(self.renderer.game_over)
        self.assertEqual(self.renderer.objects, [])


if __name__ == "__main__":
    unittest.main()
