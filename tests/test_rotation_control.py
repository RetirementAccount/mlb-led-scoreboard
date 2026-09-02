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
