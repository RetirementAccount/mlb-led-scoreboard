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


class TestWithPauseAndSkip(unittest.TestCase):
    def test_defers_to_base_cond_when_not_paused_and_no_skip(self):
        control = FakeControl(paused=False, skip=False)
        cond = with_pause_and_skip(control, lambda: True)
        self.assertTrue(cond())

        cond = with_pause_and_skip(control, lambda: False)
        self.assertFalse(cond())

    def test_paused_holds_regardless_of_base_cond(self):
        control = FakeControl(paused=True, skip=False)
        cond = with_pause_and_skip(control, lambda: False)
        self.assertTrue(cond())

    def test_skip_wins_even_while_paused(self):
        control = FakeControl(paused=True, skip=True)
        cond = with_pause_and_skip(control, lambda: True)
        self.assertFalse(cond())

    def test_skip_is_one_shot_through_the_wrapper(self):
        control = FakeControl(paused=True, skip=True)
        cond = with_pause_and_skip(control, lambda: True)

        self.assertFalse(cond())  # skip consumed here
        self.assertTrue(cond())  # now just paused, holding


if __name__ == "__main__":
    unittest.main()
