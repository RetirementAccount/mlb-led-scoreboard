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

    def test_defaults_to_inactive_no_steer(self):
        game_mode = GameMode(self.path)
        self.assertFalse(game_mode.is_active())
        self.assertIsNone(game_mode.consume_steer())

    def test_set_active_persists(self):
        game_mode = GameMode(self.path)
        game_mode.set_active(True)
        self.assertTrue(game_mode.is_active())

        with open(self.path) as f:
            saved = json.load(f)
        self.assertTrue(saved["active"])

    def test_toggle_active_flips_and_returns_new_state(self):
        game_mode = GameMode(self.path)
        self.assertTrue(game_mode.toggle_active())
        self.assertTrue(game_mode.is_active())
        self.assertFalse(game_mode.toggle_active())
        self.assertFalse(game_mode.is_active())

    def test_steer_is_one_shot(self):
        game_mode = GameMode(self.path)
        game_mode.request_steer("left")

        self.assertEqual(game_mode.consume_steer(), "left")
        self.assertIsNone(game_mode.consume_steer())

    def test_set_active_clears_any_pending_steer(self):
        game_mode = GameMode(self.path)
        game_mode.request_steer("right")
        game_mode.set_active(True)

        self.assertIsNone(game_mode.consume_steer())

    def test_a_second_instance_picks_up_persisted_state(self):
        game_mode = GameMode(self.path)
        game_mode.set_active(True)
        game_mode.request_steer("left")

        other = GameMode(self.path)
        self.assertTrue(other.is_active())
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
        self.assertFalse(game_mode.is_active())

        with open(self.path, "w") as f:
            json.dump({"active": True, "steer": None}, f)
        bumped = (self.path.stat().st_mtime or time.time()) + 5
        os.utime(self.path, (bumped, bumped))

        game_mode._last_check = 0
        self.assertTrue(game_mode.is_active())


if __name__ == "__main__":
    unittest.main()
