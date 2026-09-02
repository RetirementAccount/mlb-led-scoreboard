import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from data.rotation_toggles import ALL_KINDS, RotationToggles


class TestRotationToggles(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tmpdir.name) / "rotation_toggles.json"

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_defaults_to_enabled_when_no_file_exists(self):
        toggles = RotationToggles(self.path)
        for kind in ALL_KINDS:
            self.assertTrue(toggles.is_enabled(kind))

    def test_set_enabled_persists_to_disk(self):
        toggles = RotationToggles(self.path)
        toggles.set_enabled("nhl", False)

        self.assertFalse(toggles.is_enabled("nhl"))
        self.assertTrue(toggles.is_enabled("nba"))

        with open(self.path) as f:
            saved = json.load(f)
        self.assertEqual(saved["nhl"], False)

    def test_unknown_kind_defaults_to_enabled(self):
        toggles = RotationToggles(self.path)
        self.assertTrue(toggles.is_enabled("some_future_plugin"))

    def test_reset_all_re_enables_everything(self):
        toggles = RotationToggles(self.path)
        toggles.set_enabled("nhl", False)
        toggles.set_enabled("game", False)

        toggles.reset_all()

        for kind in ALL_KINDS:
            self.assertTrue(toggles.is_enabled(kind))

    def test_a_second_instance_picks_up_persisted_state(self):
        toggles = RotationToggles(self.path)
        toggles.set_enabled("epl", False)

        other_toggles = RotationToggles(self.path)
        self.assertFalse(other_toggles.is_enabled("epl"))

    def test_external_file_change_is_picked_up_after_reload_interval(self):
        toggles = RotationToggles(self.path)
        self.assertTrue(toggles.is_enabled("ncaaf"))

        with open(self.path, "w") as f:
            json.dump({"ncaaf": False}, f)
        # Bump mtime forward explicitly so this doesn't flake on filesystems with
        # coarse mtime resolution where two quick writes could look simultaneous.
        bumped = (self.path.stat().st_mtime or time.time()) + 5
        os.utime(self.path, (bumped, bumped))

        # Force the reload window open rather than sleeping in a test.
        toggles._last_check = 0
        self.assertFalse(toggles.is_enabled("ncaaf"))


if __name__ == "__main__":
    unittest.main()
