import unittest

from renderers.main import with_pause_and_skip


class FakeControl:
    def __init__(self, paused=False, skip=False):
        self._paused = paused
        self._skip = skip

    def is_paused(self):
        return self._paused

    def consume_skip(self):
        if self._skip:
            self._skip = False
            return True
        return False


class FakeGameMode:
    def __init__(self, active=False):
        self._active = active

    def is_active(self):
        return self._active


class FakeData:
    def __init__(self, paused=False, skip=False, game_mode_active=False):
        self.rotation_control = FakeControl(paused=paused, skip=skip)
        self.game_mode = FakeGameMode(active=game_mode_active)


class TestWithPauseAndSkip(unittest.TestCase):
    def test_defers_to_base_cond_when_not_paused_and_no_skip(self):
        data = FakeData(paused=False, skip=False)
        cond = with_pause_and_skip(data, lambda: True)
        self.assertTrue(cond())

        cond = with_pause_and_skip(data, lambda: False)
        self.assertFalse(cond())

    def test_paused_holds_regardless_of_base_cond(self):
        data = FakeData(paused=True, skip=False)
        cond = with_pause_and_skip(data, lambda: False)
        self.assertTrue(cond())

    def test_skip_wins_even_while_paused(self):
        data = FakeData(paused=True, skip=True)
        cond = with_pause_and_skip(data, lambda: True)
        self.assertFalse(cond())

    def test_skip_is_one_shot_through_the_wrapper(self):
        data = FakeData(paused=True, skip=True)
        cond = with_pause_and_skip(data, lambda: True)

        self.assertFalse(cond())  # skip consumed here
        self.assertTrue(cond())  # now just paused, holding

    def test_game_mode_active_wins_over_everything(self):
        # Confirms the actual bug this fixed: without this check, flipping game mode
        # on wouldn't interrupt whatever screen is currently showing.
        data = FakeData(paused=True, skip=False, game_mode_active=True)
        cond = with_pause_and_skip(data, lambda: True)
        self.assertFalse(cond())

    def test_game_mode_active_wins_even_with_a_pending_skip(self):
        data = FakeData(paused=False, skip=True, game_mode_active=True)
        cond = with_pause_and_skip(data, lambda: True)
        self.assertFalse(cond())
        # game mode being active doesn't consume the pending skip -- it's checked first
        # and returns immediately, so the skip is still sitting there afterward.
        self.assertTrue(data.rotation_control.consume_skip())


if __name__ == "__main__":
    unittest.main()
