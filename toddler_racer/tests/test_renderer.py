import tempfile
import unittest
from pathlib import Path

from mlb_led_scoreboard_toddler_racer.config import Config
from mlb_led_scoreboard_toddler_racer.renderer import CAR_WIDTH, OBSTACLE_WIDTH, Renderer


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
    return renderer


class TestRendererGameplay(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.renderer = make_renderer(Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_starts_centered_on_the_road_with_no_score(self):
        self.assertEqual(self.renderer.score, 0)
        self.assertGreaterEqual(self.renderer.car_x, self.renderer.road_left)
        self.assertLessEqual(self.renderer.car_x + CAR_WIDTH, self.renderer.road_right)

    def test_steer_left_moves_car_left_and_clamps_at_road_edge(self):
        start_x = self.renderer.car_x
        self.renderer._game_mode.request_steer("left")
        self.renderer._consume_steer()
        self.assertLess(self.renderer.car_x, start_x)

        for _ in range(50):  # far more than enough presses to hit the edge
            self.renderer._game_mode.request_steer("left")
            self.renderer._consume_steer()
        self.assertEqual(self.renderer.car_x, self.renderer.road_left)

    def test_steer_right_clamps_at_road_edge(self):
        for _ in range(50):
            self.renderer._game_mode.request_steer("right")
            self.renderer._consume_steer()
        self.assertEqual(self.renderer.car_x, self.renderer.road_right - CAR_WIDTH)

    def test_obstacle_spawns_after_configured_interval(self):
        self.assertEqual(len(self.renderer.obstacles), 0)
        for _ in range(self.renderer.config.spawn_interval_frames):
            self.renderer._advance()
        self.assertEqual(len(self.renderer.obstacles), 1)

    def test_catching_an_obstacle_scores_a_point_and_flashes_without_ending_the_game(self):
        # Place an obstacle directly on the car and at car height, then advance once.
        car_y = self.renderer.height - 2 - 3  # CAR_Y_MARGIN=2, CAR_HEIGHT=3
        self.renderer.obstacles = [{"x": self.renderer.car_x, "y": float(car_y), "caught": False}]

        self.renderer._advance()

        self.assertEqual(self.renderer.score, 1)
        self.assertGreater(self.renderer.flash_frames_remaining, 0)
        # No lose/reset condition -- the game keeps going, car position is untouched.
        self.assertGreaterEqual(self.renderer.car_x, self.renderer.road_left)

    def test_missing_an_obstacle_has_no_penalty(self):
        # An obstacle that falls past the bottom without ever overlapping the car.
        # Disable the periodic auto-spawn for this test so it doesn't interfere --
        # the loop below runs long enough that one would otherwise kick in.
        self.renderer.config.spawn_interval_frames = 10_000
        self.renderer.obstacles = [{"x": self.renderer.road_right + 100, "y": 0.0, "caught": False}]
        for _ in range(int(self.renderer.height / self.renderer.config.fall_speed) + 2):
            self.renderer._advance()

        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(len(self.renderer.obstacles), 0)  # fell off screen and was removed

    def test_reset_clears_score_and_obstacles(self):
        self.renderer.score = 5
        self.renderer.obstacles = [{"x": 0, "y": 0.0, "caught": False}]

        self.renderer.reset()

        self.assertEqual(self.renderer.score, 0)
        self.assertEqual(self.renderer.obstacles, [])

    def test_road_is_narrower_than_the_panel_and_centered(self):
        self.assertGreater(self.renderer.road_left, 0)
        self.assertLess(self.renderer.road_right, self.renderer.width)
        self.assertGreaterEqual(self.renderer.road_right - self.renderer.road_left, OBSTACLE_WIDTH)


if __name__ == "__main__":
    unittest.main()
