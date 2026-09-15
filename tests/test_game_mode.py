import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from data.game_mode import GameMode


class TestGameMode(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "game_mode.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_defaults_to_normal_no_steer_no_confirm(self):
        game_mode = GameMode(self.path)
        self.assertIsNone(game_mode.current_screen())
        self.assertFalse(game_mode.is_in_game_area())
        self.assertIsNone(game_mode.consume_steer())
        self.assertFalse(game_mode.consume_confirm())

    def test_open_menu_shows_the_menu_plugin(self):
        game_mode = GameMode(self.path)
        game_mode.open_menu()
        self.assertEqual(game_mode.current_screen(), GameMode.MENU_PLUGIN)
        self.assertTrue(game_mode.is_in_game_area())

    def test_launch_shows_the_named_game(self):
        game_mode = GameMode(self.path)
        game_mode.launch("racer")
        self.assertEqual(game_mode.current_screen(), "racer")
        self.assertTrue(game_mode.is_in_game_area())

    def test_exit_to_normal_clears_the_screen(self):
        game_mode = GameMode(self.path)
        game_mode.launch("racer")
        game_mode.exit_to_normal()
        self.assertIsNone(game_mode.current_screen())
        self.assertFalse(game_mode.is_in_game_area())

    def test_changing_screen_clears_any_pending_steer_and_confirm(self):
        game_mode = GameMode(self.path)
        game_mode.open_menu()
        game_mode.request_steer("right")
        game_mode.request_confirm()

        game_mode.launch("racer")

        self.assertIsNone(game_mode.consume_steer())
        self.assertFalse(game_mode.consume_confirm())

    def test_steer_is_one_shot(self):
        game_mode = GameMode(self.path)
        game_mode.request_steer("left")

        self.assertEqual(game_mode.consume_steer(), "left")
        self.assertIsNone(game_mode.consume_steer())

    def test_confirm_is_one_shot(self):
        game_mode = GameMode(self.path)
        game_mode.request_confirm()

        self.assertTrue(game_mode.consume_confirm())
        self.assertFalse(game_mode.consume_confirm())

    def test_held_direction_defaults_to_none(self):
        game_mode = GameMode(self.path)
        self.assertIsNone(game_mode.held_direction())

    def test_held_direction_reflects_the_button_currently_down(self):
        game_mode = GameMode(self.path)
        game_mode.set_steer_held("left", True)
        self.assertEqual(game_mode.held_direction(), "left")

        game_mode.set_steer_held("left", False)
        self.assertIsNone(game_mode.held_direction())

    def test_held_direction_is_none_if_both_buttons_are_down(self):
        # An unusual physical state (both buttons pressed at once), but should
        # resolve to "no clear direction" rather than picking one arbitrarily.
        game_mode = GameMode(self.path)
        game_mode.set_steer_held("left", True)
        game_mode.set_steer_held("right", True)
        self.assertIsNone(game_mode.held_direction())

    def test_held_state_is_shared_across_instances(self):
        listener = GameMode(self.path)
        display = GameMode(self.path)

        listener.set_steer_held("right", True)
        display._last_check = 0
        self.assertEqual(display.held_direction(), "right")

    def test_a_second_instance_picks_up_persisted_state(self):
        game_mode = GameMode(self.path)
        game_mode.launch("racer")
        game_mode.request_steer("left")

        other = GameMode(self.path)
        self.assertEqual(other.current_screen(), "racer")
        self.assertEqual(other.consume_steer(), "left")

    def test_rapid_steer_requests_from_separate_instances_are_not_lost(self):
        # Same class of race as RotationControl's skip -- the keypad listener and the
        # display are separate processes coordinating only through the state file.
        listener = GameMode(self.path)
        display = GameMode(self.path)

        listener.request_steer("left")
        display._last_check = 0
        self.assertEqual(display.consume_steer(), "left")

        listener.request_steer("right")
        display._last_check = 0
        self.assertEqual(display.consume_steer(), "right")

    def test_external_file_change_is_picked_up_after_reload_interval(self):
        game_mode = GameMode(self.path)
        self.assertIsNone(game_mode.current_screen())

        with open(self.path, "w") as f:
            json.dump({"screen": "racer", "steer": None, "confirm": False}, f)
        bumped = (self.path.stat().st_mtime or time.time()) + 5
        os.utime(self.path, (bumped, bumped))

        game_mode._last_check = 0
        self.assertEqual(game_mode.current_screen(), "racer")


if __name__ == "__main__":
    unittest.main()
