from typing import Optional

from .models import TeamScore

MIN_LUMINANCE = 60.0
WHITE = (255, 255, 255)


def readable_team_color(team: TeamScore, min_luminance: float = MIN_LUMINANCE) -> tuple[int, int, int]:
    """Pick a team's own color for text, falling back when it'd be unreadable on a black background."""
    for hex_str in (team.color, team.alternate_color):
        rgb = _hex_to_rgb(hex_str)
        if rgb is not None and _luminance(rgb) >= min_luminance:
            return rgb
    return WHITE


def _hex_to_rgb(hex_str: Optional[str]) -> Optional[tuple[int, int, int]]:
    if not hex_str or len(hex_str) != 6:
        return None
    try:
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    except ValueError:
        return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b
