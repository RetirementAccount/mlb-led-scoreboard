import unittest

from mlb_led_scoreboard_espn_sports.colors import readable_team_color
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


if __name__ == "__main__":
    unittest.main()
