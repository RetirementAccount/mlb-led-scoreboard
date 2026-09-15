import random
from typing import TYPE_CHECKING, Optional

import bullpen.api as api

from .config import Config
from .data import Data

if TYPE_CHECKING:
    from RGBMatrixEmulator.emulation.canvas import Canvas

# A very simple, never-fail toddler racing game: a road down the middle of the panel,
# the car steered left/right by the keypad's L/R mouse-click buttons, and obstacles
# that fall from the top. Catching one is a small celebration (score + screen flash);
# missing one has zero penalty -- there is no lose condition by design.
ROAD_MARGIN_FRACTION = 0.2  # road spans the middle (1 - 2*margin) of the panel width
CAR_WIDTH = 3  # the car's body -- vertically oriented (taller than wide), tires drawn outside this
TIRE_WIDTH = 1
TIRE_HEIGHT = 2
CAR_Y_MARGIN = 2  # pixels between the car and the bottom edge
OBSTACLE_WIDTH = 3  # same vertical car-body silhouette as the player car, tires included
OBSTACLE_HEIGHT = 6
FLASH_FRAMES = 4
DASH_LENGTH = 2
DASH_PERIOD = 6

GRASS_RGB = (20, 90, 20)
ROAD_RGB = (50, 50, 50)
DASH_RGB = (230, 230, 230)
TIRE_RGB = (0, 0, 0)  # was (40,40,40), nearly identical to ROAD_RGB (50,50,50) -- invisible against it
OBSTACLE_RGB = (240, 200, 20)
FLASH_RGB = (255, 255, 255)
SCORE_RGB = (255, 255, 255)

# Eric's toddler requested a rainbow-striped car -- one row per hue, most-primary
# version of each, top to bottom. This also sets CAR_HEIGHT (one row per stripe),
# replacing the old flat CAR_RGB fill; obstacles keep their own solid OBSTACLE_RGB
# and OBSTACLE_HEIGHT unchanged.
CAR_STRIPE_COLORS_RGB = [
    (255, 0, 0),  # red
    (255, 255, 0),  # yellow
    (0, 200, 0),  # green
    (0, 0, 255),  # blue
    (148, 0, 211),  # violet
]
CAR_HEIGHT = len(CAR_STRIPE_COLORS_RGB)


class Renderer(api.PluginRenderer[Data]):
    def __init__(self, config: Config, layout: api.Layout, colors: api.Color) -> None:
        # This plugin is only ever shown via the game-mode override in
        # renderers/main.py, never through the normal timed rotation -- so, unlike
        # every other plugin, it reaches directly into data/game_mode.py for its
        # input (L/R steer clicks) rather than getting it through PluginData/Data.
        # A fresh GameMode() instance here reads the same shared state file the
        # keypad listener writes to; the file is the source of truth, not the object.
        from data.game_mode import GameMode

        self.config = config
        self.status_font = layout.font("racer.status")
        self.width = layout.width
        self.height = layout.height
        self._game_mode = GameMode()

        road_width = int(self.width * (1 - 2 * ROAD_MARGIN_FRACTION))
        self.road_left = (self.width - road_width) // 2
        self.road_right = self.road_left + road_width

        self._reset_game()

    def wait_time(self) -> float:
        return self.config.frame_seconds

    def reset(self) -> None:
        self._reset_game()

    def render(self, data: Data, canvas: "Canvas", graphics: api.renderer.graphics, scrolling_text_pos: int) -> Optional[int]:
        self._consume_steer()
        self._advance()
        self._draw(canvas, graphics)
        return None

    def _reset_game(self) -> None:
        self.car_x = (self.road_left + self.road_right - CAR_WIDTH) // 2
        self.obstacles: list[dict] = []
        self.score = 0
        self.frame_count = 0
        self.flash_frames_remaining = 0

    def _consume_steer(self) -> None:
        # consume_steer() is drained unconditionally even though the car now moves
        # from held_direction() instead -- it's a one-shot flag shared with the menu
        # (see fruit_catcher's identical reasoning), and leaving it unread here would
        # make it appear (falsely) still pending the next time the menu is opened.
        self._game_mode.consume_steer()
        direction = self._game_mode.held_direction()
        if direction == "left":
            self.car_x = max(self.road_left, self.car_x - self.config.steer_step)
        elif direction == "right":
            self.car_x = min(self.road_right - CAR_WIDTH, self.car_x + self.config.steer_step)

    def _advance(self) -> None:
        self.frame_count += 1
        if self.flash_frames_remaining > 0:
            self.flash_frames_remaining -= 1

        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        remaining = []
        for obstacle in self.obstacles:
            obstacle["y"] += self.config.fall_speed
            if not obstacle["caught"] and self._overlaps(obstacle, car_y):
                obstacle["caught"] = True
                self.score += 1
                self.flash_frames_remaining = FLASH_FRAMES
            if obstacle["y"] < self.height:
                remaining.append(obstacle)
        self.obstacles = remaining

        if self.frame_count % self.config.spawn_interval_frames == 0:
            x = random.randint(self.road_left, self.road_right - OBSTACLE_WIDTH)
            self.obstacles.append({"x": x, "y": 0.0, "caught": False})

    def _overlaps(self, obstacle: dict, car_y: int) -> bool:
        obstacle_bottom = obstacle["y"] + OBSTACLE_HEIGHT
        if obstacle_bottom < car_y or obstacle["y"] > car_y + CAR_HEIGHT:
            return False
        return not (obstacle["x"] + OBSTACLE_WIDTH < self.car_x or obstacle["x"] > self.car_x + CAR_WIDTH)

    def _draw(self, canvas, graphics) -> None:
        if self.flash_frames_remaining > 0:
            # A clean, unmistakable full-panel flash is the celebration for a toddler
            # catching an obstacle -- draw nothing else this frame, since the road
            # rectangle below would otherwise cover most of the flash and make it
            # barely visible (confirmed with a rendered preview before this fix).
            canvas.Fill(*FLASH_RGB)
            return

        canvas.Fill(*GRASS_RGB)

        road_color = graphics.Color(*ROAD_RGB)
        for x in range(self.road_left, self.road_right):
            graphics.DrawLine(canvas, x, 0, x, self.height - 1, road_color)

        dash_color = graphics.Color(*DASH_RGB)
        center_x = (self.road_left + self.road_right) // 2
        for y in range(self.height):
            if (y - self.frame_count) % DASH_PERIOD < DASH_LENGTH:
                graphics.DrawLine(canvas, center_x, y, center_x, y, dash_color)

        obstacle_color = graphics.Color(*OBSTACLE_RGB)
        for obstacle in self.obstacles:
            obstacle_y = int(obstacle["y"])
            self._fill_rect(canvas, graphics, obstacle["x"], obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT, obstacle_color)
            self._draw_tires(canvas, graphics, obstacle["x"], obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT)

        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        for row, rgb in enumerate(CAR_STRIPE_COLORS_RGB):
            stripe_color = graphics.Color(*rgb)
            graphics.DrawLine(canvas, self.car_x, car_y + row, self.car_x + CAR_WIDTH - 1, car_y + row, stripe_color)
        self._draw_tires(canvas, graphics, self.car_x, car_y, CAR_WIDTH, CAR_HEIGHT)

        score_color = graphics.Color(*SCORE_RGB)
        graphics.DrawText(canvas, self.status_font["font"], 1, self.status_font["size"]["height"], score_color, str(self.score))

    def _draw_tires(self, canvas, graphics, x: int, y: int, width: int, height: int) -> None:
        # Four tire nubs poking out to each side of a (narrower) vertical car body: one
        # pair near the front (top), one pair near the rear (bottom). Shared between
        # the player car and the obstacle "cars" so they read as the same kind of thing.
        tire_color = graphics.Color(*TIRE_RGB)
        left_x = x - TIRE_WIDTH
        right_x = x + width
        rear_y = y + height - TIRE_HEIGHT
        for tire_x in (left_x, right_x):
            self._fill_rect(canvas, graphics, tire_x, y, TIRE_WIDTH, TIRE_HEIGHT, tire_color)
            self._fill_rect(canvas, graphics, tire_x, rear_y, TIRE_WIDTH, TIRE_HEIGHT, tire_color)

    def _fill_rect(self, canvas, graphics, x: int, y: int, w: int, h: int, color) -> None:
        for row in range(h):
            graphics.DrawLine(canvas, x, y + row, x + w - 1, y + row, color)
