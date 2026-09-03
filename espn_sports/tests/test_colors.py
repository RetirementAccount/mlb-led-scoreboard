import unittest

from mlb_led_scoreboard_espn_sports.colors import (
    bar_accent_color,
    bar_fill_color,
    contrasting_text_color,
    readable_team_color,
)
from mlb_led_scoreboard_espn_sports.models import TeamScore


def make_team(color=None, alternate_color=None):
    return TeamScore(
        abbreviation="ABC", display_name="ABC Team", score="0", color=color, alternate_color=alternate_color
    )


class TestReadableTeamColor(unittest.TestCase):
    def test_uses_primary_color_when_bright_enough(self):
        team = make_team(color="69be28")
        self.assertEqual(readable_team_color(team), (0x69, 0xBE, 0x28))

    def test_falls_back_to_alternate_when_primary_too_dark(self):
        team = make_team(color="000000", alternate_color="69be28")
        self.assertEqual(readable_team_color(team), (0x69, 0xBE, 0x28))

    def test_falls_back_to_white_when_both_missing(self):
        team = make_team()
        self.assertEqual(readable_team_color(team), (255, 255, 255))

    def test_falls_back_to_white_when_both_too_dark(self):
        team = make_team(color="000000", alternate_color="010101")
        self.assertEqual(readable_team_color(team), (255, 255, 255))

    def test_ignores_malformed_hex(self):
        team = make_team(color="not-a-color", alternate_color="69be28")
        self.assertEqual(readable_team_color(team), (0x69, 0xBE, 0x28))


class TestBarFillColor(unittest.TestCase):
    def test_uses_primary_color_even_if_dark(self):
        # Unlike readable_team_color, a bar fill has no luminance floor -- a dark navy
        # fill is fine, since text drawn on top just needs contrasting_text_color().
        team = make_team(color="002a5c")
        self.assertEqual(bar_fill_color(team), (0x00, 0x2A, 0x5C))

    def test_falls_back_to_dark_gray_when_missing(self):
        team = make_team()
        self.assertEqual(bar_fill_color(team), (40, 40, 40))


class TestBarAccentColor(unittest.TestCase):
    def test_uses_alternate_color(self):
        team = make_team(color="002a5c", alternate_color="c60c30")
        self.assertEqual(bar_accent_color(team), (0xC6, 0x0C, 0x30))

    def test_falls_back_to_white_when_missing(self):
        team = make_team(color="002a5c")
        self.assertEqual(bar_accent_color(team), (255, 255, 255))


class TestContrastingTextColor(unittest.TestCase):
    def test_white_on_dark_background(self):
        self.assertEqual(contrasting_text_color((0, 0, 0)), (255, 255, 255))
        self.assertEqual(contrasting_text_color((0x00, 0x2A, 0x5C)), (255, 255, 255))

    def test_black_on_light_background(self):
        self.assertEqual(contrasting_text_color((255, 255, 255)), (0, 0, 0))

    def test_black_on_bright_green(self):
        # 69be28: real ESPN primary color for a team like Seattle -- bright enough that
        # black reads better than white against it.
        self.assertEqual(contrasting_text_color((0x69, 0xBE, 0x28)), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
