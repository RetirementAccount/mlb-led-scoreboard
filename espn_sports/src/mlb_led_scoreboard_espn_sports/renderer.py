from typing import TYPE_CHECKING, Optional

import bullpen.api as api
from bullpen.util import center_text_position

from .colors import readable_team_color
from .config import ConfigBase
from .data import Data

if TYPE_CHECKING:
    from PIL import Image
    from RGBMatrixEmulator.emulation.canvas import Canvas

TITLE_Y = 7
MATCHUP_Y = 17
STATUS_Y = 27

LOGO_TITLE_Y = 7
LOGO_Y = 2
LOGO_SCORE_Y = 17
LOGO_STATUS_Y = 27
LOGO_ALPHA_THRESHOLD = 128

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

        if not data.games:
            self._draw_centered(canvas, graphics, self.title_font, self.config.league_name, TITLE_Y, white)
            self._draw_centered(canvas, graphics, self.status_font, "No games today", STATUS_Y, white)
            return None

        game = data.games[self._game_index % len(data.games)]
        self._game_index += 1

        if self.config.show_logos:
            self._render_with_logos(data, canvas, graphics, game)
        else:
            self._render_text_only(canvas, graphics, game)

        return None

    def reset(self) -> None:
        self._game_index = 0

    def _render_text_only(self, canvas, graphics, game) -> None:
        white = graphics.Color(255, 255, 255)
        live_color = graphics.Color(255, 200, 0)

        self._draw_centered(canvas, graphics, self.title_font, self.config.league_name, TITLE_Y, white)

        away_color = graphics.Color(*readable_team_color(game.away))
        home_color = graphics.Color(*readable_team_color(game.home))

        away_text = f"{game.away.abbreviation} {game.away.score}"
        sep_text = " - "
        home_text = f"{game.home.score} {game.home.abbreviation}"
        full_text = away_text + sep_text + home_text

        start_x = center_text_position(full_text, canvas.width // 2, self.matchup_font["size"]["width"])
        char_width = self.matchup_font["size"]["width"]
        x = start_x
        for text, color in ((away_text, away_color), (sep_text, white), (home_text, home_color)):
            graphics.DrawText(canvas, self.matchup_font["font"], x, MATCHUP_Y, color, text)
            x += char_width * len(text)

        status = game.status_detail or ("FINAL" if game.is_final else "")
        status_color = live_color if game.is_live else white
        self._draw_centered(canvas, graphics, self.status_font, status, STATUS_Y, status_color)

    def _render_with_logos(self, data: Data, canvas, graphics, game) -> None:
        white = graphics.Color(255, 255, 255)
        live_color = graphics.Color(255, 200, 0)
        title_color = live_color if game.is_live else white

        self._draw_centered(canvas, graphics, self.title_font, self.config.league_name, LOGO_TITLE_Y, title_color)

        size = self.config.logo_size
        self._draw_image(canvas, data.logo_for(game.away), 1, LOGO_Y)
        self._draw_image(canvas, data.logo_for(game.home), canvas.width - size - 1, LOGO_Y)

        score_text = f"{game.away.score} - {game.home.score}"
        self._draw_centered(canvas, graphics, self.matchup_font, score_text, LOGO_SCORE_Y, white)

        status = game.status_detail or ("FINAL" if game.is_final else "")
        status_color = live_color if game.is_live else white
        self._draw_centered(canvas, graphics, self.status_font, status, LOGO_STATUS_Y, status_color)

    def _draw_image(self, canvas, image: Optional["Image.Image"], x: int, y: int) -> None:
        if image is None:
            return
        for px in range(image.width):
            for py in range(image.height):
                r, g, b, a = image.getpixel((px, py))
                if a >= LOGO_ALPHA_THRESHOLD:
                    canvas.SetPixel(x + px, y + py, r, g, b)

    def _draw_centered(self, canvas, graphics, font, text: str, y: int, color) -> None:
        x = center_text_position(text, canvas.width // 2, font["size"]["width"])
        graphics.DrawText(canvas, font["font"], x, y, color, text)
