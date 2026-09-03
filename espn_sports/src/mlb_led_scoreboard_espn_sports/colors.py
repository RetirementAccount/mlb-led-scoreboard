from typing import Optional

from .models import TeamScore

MIN_LUMINANCE = 60.0
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
FALLBACK_BAR_COLOR = (40, 40, 40)


def readable_team_color(team: TeamScore, min_luminance: float = MIN_LUMINANCE) -> tuple[int, int, int]:
    """Pick a team's own color for text on a black background, falling back when it'd be unreadable."""
    for hex_str in (team.color, team.alternate_color):
        rgb = hex_to_rgb(hex_str)
        if rgb is not None and _luminance(rgb) >= min_luminance:
            return rgb
    return WHITE


def bar_fill_color(team: TeamScore) -> tuple[int, int, int]:
    """The team's primary color, for filling a solid banner bar (unlike readable_team_color, no
    luminance floor -- a dark navy fill is fine, the text drawn on top just needs contrast())."""
    return hex_to_rgb(team.color) or FALLBACK_BAR_COLOR


def bar_accent_color(team: TeamScore) -> tuple[int, int, int]:
    """The team's secondary color, for a thin accent stripe on a banner bar."""
    return hex_to_rgb(team.alternate_color) or WHITE


def contrasting_text_color(background_rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    """Black or white, whichever reads better against a given fill color."""
    return BLACK if _luminance(background_rgb) >= 140 else WHITE


def hex_to_rgb(hex_str: Optional[str]) -> Optional[tuple[int, int, int]]:
    if not hex_str or len(hex_str) != 6:
        return None
    try:
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    except ValueError:
        return None


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b
