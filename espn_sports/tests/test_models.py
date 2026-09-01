import unittest

from mlb_led_scoreboard_espn_sports.models import matches_favorite_team, parse_scoreboard


def make_event(state, short_detail, away_abbr, away_score, home_abbr, home_score, completed=False):
    return {
        "competitions": [
            {
                "status": {"type": {"state": state, "shortDetail": short_detail, "completed": completed}},
                "competitors": [
                    {
                        "homeAway": "home",
                        "team": {"abbreviation": home_abbr, "displayName": f"{home_abbr} Team"},
                        "score": str(home_score),
                    },
                    {
                        "homeAway": "away",
                        "team": {"abbreviation": away_abbr, "displayName": f"{away_abbr} Team"},
                        "score": str(away_score),
                    },
                ],
            }
        ]
    }


class TestParseScoreboard(unittest.TestCase):
    def test_parses_live_game(self):
        raw = {"events": [make_event("in", "Q3 5:23", "NYJ", 10, "BUF", 21)]}
        games = parse_scoreboard(raw)

        self.assertEqual(len(games), 1)
        game = games[0]
        self.assertEqual(game.away.abbreviation, "NYJ")
        self.assertEqual(game.away.score, "10")
        self.assertEqual(game.home.abbreviation, "BUF")
        self.assertEqual(game.home.score, "21")
        self.assertEqual(game.status_detail, "Q3 5:23")
        self.assertTrue(game.is_live)
        self.assertFalse(game.is_final)

    def test_parses_final_game(self):
        raw = {"events": [make_event("post", "Final", "LAL", 101, "BOS", 99, completed=True)]}
        games = parse_scoreboard(raw)

        self.assertEqual(len(games), 1)
        self.assertTrue(games[0].is_final)
        self.assertFalse(games[0].is_live)

    def test_skips_events_missing_competitors(self):
        raw = {"events": [{"competitions": [{"status": {"type": {}}, "competitors": []}]}]}
        self.assertEqual(parse_scoreboard(raw), [])

    def test_no_events_returns_empty_list(self):
        self.assertEqual(parse_scoreboard({}), [])
        self.assertEqual(parse_scoreboard({"events": []}), [])

    def test_matches_favorite_team_by_abbreviation(self):
        raw = {"events": [make_event("pre", "7:00 PM ET", "NYJ", 0, "BUF", 0)]}
        game = parse_scoreboard(raw)[0]

        self.assertTrue(matches_favorite_team(game, ["buf"]))
        self.assertTrue(matches_favorite_team(game, ["nyj team"]))
        self.assertFalse(matches_favorite_team(game, ["mia"]))


if __name__ == "__main__":
    unittest.main()
