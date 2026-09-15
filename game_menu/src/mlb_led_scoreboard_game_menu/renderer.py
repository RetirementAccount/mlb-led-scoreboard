from typing import Optional

import bullpen.api as api
from bullpen.util import center_text_position

from .config import Config
from .data import Data

# The list of games shown in the menu, in order. Add a new game here (its bullpen
# entry-point name, and a short display label) once it exists -- nothing else needs
# to change for it to show up and be launchable.
AVAILABLE_GAMES = [
    ("racer", "Racer"),
    ("fruit_catcher", "Fruit Catch"),
]
EXIT_SENTINEL = "__exit__"
EXIT_LABEL = "Exit"

TITLE_Y = 6
OPTION_START_Y = 14
OPTION_LINE_HEIGHT = 7  # tight enough that 3+ options (now: Racer, Fruit Catch, Exit) still fit within 32px tall

BG_RGB = (0, 0, 0)
TITLE_RGB = (255, 255, 255)
OPTION_RGB = (180, 180, 180)
SELECTED_RGB = (255, 200, 0)


class Renderer(api.PluginRenderer[Data]):
    def __init__(self, config: Config, layout: api.Layout, colors: api.Color) -> None:
        # Same reasoning as toddler_racer's Renderer: this plugin is only ever shown
        # via the game-area override in renderers/main.py, never through the normal
        # timed rotation, so it reaches directly into data/game_mode.py for its input
        # (steer + confirm) rather than getting it through PluginData/Data. A fresh
        # GameMode() instance here reads the same shared state file the keypad
        # listener writes to; the file is the source of truth, not the object.
        from data.game_mode import GameMode

        self.config = config
        self.title_font = layout.font("game_menu.title")
        self.option_font = layout.font("game_menu.option")
        self._game_mode = GameMode()
        self.options = AVAILABLE_GAMES + [(EXIT_SENTINEL, EXIT_LABEL)]
        self.selected = 0

    def wait_time(self) -> float:
        return 0.1

    def reset(self) -> None:
        self.selected = 0

    def render(self, data: Data, canvas, graphics: api.renderer.graphics, scrolling_text_pos: int) -> Optional[int]:
        self._consume_input()
        self._draw(canvas, graphics)
        return None

    def _consume_input(self) -> None:
        direction = self._game_mode.consume_steer()
        if direction == "left":
            self.selected = (self.selected - 1) % len(self.options)
        elif direction == "right":
            self.selected = (self.selected + 1) % len(self.options)

        if self._game_mode.consume_confirm():
            name, _ = self.options[self.selected]
            if name == EXIT_SENTINEL:
                self._game_mode.exit_to_normal()
            else:
                self._game_mode.launch(name)

    def _draw(self, canvas, graphics) -> None:
        canvas.Fill(*BG_RGB)

        title_color = graphics.Color(*TITLE_RGB)
        self._draw_centered(canvas, graphics, self.title_font, "SELECT GAME", TITLE_Y, title_color)

        y = OPTION_START_Y
        for i, (_, label) in enumerate(self.options):
            is_selected = i == self.selected
            color = graphics.Color(*SELECTED_RGB) if is_selected else graphics.Color(*OPTION_RGB)
            text = f"> {label}" if is_selected else f"  {label}"
            self._draw_centered(canvas, graphics, self.option_font, text, y, color)
            y += OPTION_LINE_HEIGHT

    def _draw_centered(self, canvas, graphics, font, text: str, y: int, color) -> None:
        x = center_text_position(text, canvas.width // 2, font["size"]["width"])
        graphics.DrawText(canvas, font["font"], x, y, color, text)
