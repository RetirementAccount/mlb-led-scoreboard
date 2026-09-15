import tempfile
import unittest
from pathlib import Path

from mlb_led_scoreboard_game_menu.config import Config
from mlb_led_scoreboard_game_menu.renderer import EXIT_SENTINEL, Renderer


class FakeMLBConfig:
    plugin_config = {}


class FakeLayout:
    width = 64
    height = 32

    def font(self, keypath):
        return {"font": None, "size": {"width": 4, "height": 6}}


def make_renderer(tmp_path: Path) -> Renderer:
    renderer = Renderer(Config(FakeMLBConfig()), FakeLayout(), colors=None)
    # Isolate from the real project's game_mode.json -- same reasoning as
    # toddler_racer's tests: never touch production state or race with an actual
    # running display/keypad listener.
    renderer._game_mode.path = tmp_path / "game_mode.json"
    renderer._game_mode._screen = None
    renderer._game_mode._steer = None
    renderer._game_mode._confirm = False
    return renderer


class TestGameMenuRenderer(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.renderer = make_renderer(Path(self.tmpdir.name))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_starts_on_the_first_option(self):
        self.assertEqual(self.renderer.selected, 0)

    def test_last_option_is_always_exit(self):
        self.assertEqual(self.renderer.options[-1][0], EXIT_SENTINEL)

    def test_steer_right_moves_selection_forward_and_wraps(self):
        count = len(self.renderer.options)
        for i in range(1, count):
            self.renderer._game_mode.request_steer("right")
            self.renderer._consume_input()
            self.assertEqual(self.renderer.selected, i)

        # one more should wrap back to the first option
        self.renderer._game_mode.request_steer("right")
        self.renderer._consume_input()
        self.assertEqual(self.renderer.selected, 0)

    def test_steer_left_moves_selection_backward_and_wraps(self):
        self.renderer._game_mode.request_steer("left")
        self.renderer._consume_input()
        self.assertEqual(self.renderer.selected, len(self.renderer.options) - 1)

    def test_confirm_on_a_game_launches_it(self):
        self.renderer.selected = 0  # "racer" is always the first entry today
        game_name = self.renderer.options[0][0]

        self.renderer._game_mode.request_confirm()
        self.renderer._consume_input()

        self.assertEqual(self.renderer._game_mode.current_screen(), game_name)

    def test_confirm_on_exit_leaves_the_game_area(self):
        self.renderer.selected = len(self.renderer.options) - 1  # Exit is always last
        self.renderer._game_mode.launch("racer")  # simulate already being in the game area

        self.renderer._game_mode.request_confirm()
        self.renderer._consume_input()

        self.assertIsNone(self.renderer._game_mode.current_screen())

    def test_reset_returns_to_the_first_option(self):
        self.renderer.selected = 1
        self.renderer.reset()
        self.assertEqual(self.renderer.selected, 0)


if __name__ == "__main__":
    unittest.main()
