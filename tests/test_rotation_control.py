import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from data.rotation_control import RotationControl


class TestRotationControl(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "rotation_control.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_defaults_to_not_paused_no_skip(self):
        control = RotationControl(self.path)
        self.assertFalse(control.is_paused())
        self.assertFalse(control.consume_skip())

    def test_set_paused_persists(self):
        control = RotationControl(self.path)
        control.set_paused(True)
        self.assertTrue(control.is_paused())

        with open(self.path) as f:
            saved = json.load(f)
        self.assertTrue(saved["paused"])

    def test_toggle_paused_flips_and_returns_new_state(self):
        control = RotationControl(self.path)
        self.assertTrue(control.toggle_paused())
        self.assertTrue(control.is_paused())
        self.assertFalse(control.toggle_paused())
        self.assertFalse(control.is_paused())

    def test_skip_is_one_shot(self):
        control = RotationControl(self.path)
        control.request_skip()

        self.assertTrue(control.consume_skip())
        self.assertFalse(control.consume_skip())

    def test_a_second_instance_picks_up_persisted_state(self):
        control = RotationControl(self.path)
        control.set_paused(True)
        control.request_skip()

        other = RotationControl(self.path)
        self.assertTrue(other.is_paused())
        self.assertTrue(other.consume_skip())

    def test_rapid_skip_requests_from_separate_instances_are_not_lost(self):
        # Reproduces the reported bug: pressing skip on the keypad twice in quick
        # succession re-showed the same screen instead of advancing twice, because a
        # write (from the keypad listener's separate process) could be based on a
        # stale cached read if it happened within the previous throttle window.
        # listener and display are separate RotationControl instances (separate
        # processes in reality), sharing only the state file on disk.
        listener = RotationControl(self.path)
        display = RotationControl(self.path)

        listener.request_skip()
        # consume_skip()'s own reload is throttled (intentional, for the display's tight
        # render loop) -- forcing the throttle window open here simulates the loop
        # checking again on its next frame, which in reality happens well within 0.1s.
        display._last_check = 0
        self.assertTrue(display.consume_skip())  # display processes skip #1, advances one screen

        # Immediately (no delay -- this is the case that used to be lost) request again.
        listener.request_skip()
        display._last_check = 0
        self.assertTrue(display.consume_skip())  # must also be seen, advancing a second screen

    def test_external_file_change_is_picked_up_after_reload_interval(self):
        control = RotationControl(self.path)
        self.assertFalse(control.is_paused())

        with open(self.path, "w") as f:
            json.dump({"paused": True, "skip": False}, f)
        bumped = (self.path.stat().st_mtime or time.time()) + 5
        os.utime(self.path, (bumped, bumped))

        control._last_check = 0
        self.assertTrue(control.is_paused())


if __name__ == "__main__":
    unittest.main()
