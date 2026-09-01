from typing import TYPE_CHECKING, Optional

import bullpen.api as api
from bullpen.util import center_text_position

from .config import ConfigBase
from .data import Data

if TYPE_CHECKING:
    from RGBMatrixEmulator.emulation.canvas import Canvas

TITLE_Y = 7
MATCHUP_Y = 17
STATUS_Y = 27
GAME_DISPLAY_SECONDS = 4.0


class Renderer(api.PluginRenderer[Data]):
    def __init__(self, config: ConfigBase, layout: api.Layout, colors: api.Color) -> None:
        self.config = config
        self.title_font = layout.font(f"{config.league_key}.title")
        self.matchup_font = layout.font(f"{config.league_key}.matchup")
        self.status_font = layout.font(f"{config.league_key}.status")
        self.bg = colors.color("default.background")
        self._game_index = 0

    def wait_time(self) -> float:
        return GAME_DISPLAY_SECONDS

    def render(self, data: Data, canvas: "Canvas", graphics: api.renderer.graphics, scrolling_text_pos: int) -> Optional[int]:
        canvas.Fill(self.bg["r"], self.bg["g"], self.bg["b"])

        white = graphics.Color(255, 255, 255)
        live_color = graphics.Color(255, 200, 0)

        self._draw_centered(canvas, graphics, self.title_font, self.config.league_name, TITLE_Y, white)

        if not data.games:
            self._draw_centered(canvas, graphics, self.status_font, "No games today", STATUS_Y, white)
            return None

        game = data.games[self._game_index % len(data.games)]
        self._game_index += 1

        matchup = f"{game.away.abbreviation} {game.away.score}-{game.home.score} {game.home.abbreviation}"
        self._draw_centered(canvas, graphics, self.matchup_font, matchup, MATCHUP_Y, white)

        status = game.status_detail or ("FINAL" if game.is_final else "")
        status_color = live_color if game.is_live else white
        self._draw_centered(canvas, graphics, self.status_font, status, STATUS_Y, status_color)

        return None

    def reset(self) -> None:
        self._game_index = 0

    def _draw_centered(self, canvas, graphics, font, text: str, y: int, color) -> None:
        x = center_text_position(text, canvas.width // 2, font["size"]["width"])
        graphics.DrawText(canvas, font["font"], x, y, color, text)
