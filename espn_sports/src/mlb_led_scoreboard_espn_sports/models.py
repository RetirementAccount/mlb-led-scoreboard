from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class TeamScore:
    abbreviation: str
    display_name: str
    score: str
    color: Optional[str] = None
    alternate_color: Optional[str] = None
    logo_url: Optional[str] = None


@dataclass(frozen=True)
class Game:
    home: TeamScore
    away: TeamScore
    status_detail: str
    is_live: bool
    is_final: bool


def parse_scoreboard(raw: dict[str, Any]) -> list[Game]:
    games = []
    for event in raw.get("events", []):
        competitions = event.get("competitions") or []
        if not competitions:
            continue

        competition = competitions[0]
        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type", {})
        state = status_type.get("state", "")
        detail = status_type.get("shortDetail", "")

        competitors = competition.get("competitors", [])
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if home is None or away is None:
            continue

        games.append(
            Game(
                home=_team_score(home),
                away=_team_score(away),
                status_detail=detail,
                is_live=state == "in",
                is_final=state == "post",
            )
        )

    return games


def matches_favorite_team(game: Game, favorite_teams_lower: list[str]) -> bool:
    for team in (game.home, game.away):
        for candidate in (team.abbreviation, team.display_name):
            if candidate.lower() in favorite_teams_lower:
                return True
    return False


def _team_score(competitor: dict[str, Any]) -> TeamScore:
    team = competitor.get("team", {})
    return TeamScore(
        abbreviation=team.get("abbreviation", "???"),
        display_name=team.get("displayName", team.get("shortDisplayName", "")),
        score=competitor.get("score", "0"),
        color=team.get("color"),
        alternate_color=team.get("alternateColor"),
        logo_url=team.get("logo"),
    )
