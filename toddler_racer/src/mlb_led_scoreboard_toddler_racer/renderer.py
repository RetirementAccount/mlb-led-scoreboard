import random
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PIL import Image

import bullpen.api as api
from bullpen.logging import LOGGER
from bullpen.util import center_text_position

from .config import Config
from .data import Data

if TYPE_CHECKING:
    from RGBMatrixEmulator.emulation.canvas import Canvas

# A toddler racing game: a road down the middle of the panel, the car steered
# left/right by the keypad's L/R mouse-click buttons, and obstacles that fall from
# the top. Colliding with one costs a life (3 total, see fruit_catcher for the same
# mechanism); safely passing one scores a point. Losing the last life ends the game
# with a Game Over overlay, restarted via the confirm key.
ROAD_MARGIN_FRACTION = 0.2  # road spans the middle (1 - 2*margin) of the panel width
CAR_WIDTH = 3  # the car's body -- vertically oriented (taller than wide), tires drawn outside this
TIRE_WIDTH = 1
TIRE_HEIGHT = 2
CAR_Y_MARGIN = 2  # pixels between the car and the bottom edge
OBSTACLE_WIDTH = 3  # same vertical car-body silhouette as the player car, tires included
OBSTACLE_HEIGHT = 6
DASH_LENGTH = 2
DASH_PERIOD = 6
# Road dashes previously scrolled at exactly 1px/frame -- the same rate obstacles
# fall at (fall_speed=1.0px/frame default) -- which made the obstacles look
# stationary relative to the road. Scrolling the dashes twice as fast as the
# 1px/frame baseline sells the illusion that everything is moving.
DASH_SPEED_MULTIPLIER = 2
SPIN_CYCLE_FRAMES = 8  # see _spin_scale() -- same squash-cycle trick as fruit_catcher's basket

GRASS_RGB = (20, 90, 20)
ROAD_RGB = (50, 50, 50)
DASH_RGB = (230, 230, 230)
TIRE_RGB = (0, 0, 0)  # was (40,40,40), nearly identical to ROAD_RGB (50,50,50) -- invisible against it
OBSTACLE_RGB = (240, 200, 20)
SCORE_RGB = (255, 255, 255)
GAME_OVER_RGB = (255, 60, 60)

# Life indicator: pink hearts, bottom-left. HEART_MASK is the built-in placeholder
# used whenever no custom heart.png is supplied (see assets/README.md) -- a small
# 5x5 pixel heart, "1" = filled.
HEART_ICON_SIZE = 5
HEART_ICON_GAP = 1
HEART_ICON_MARGIN = 1
HEART_RGB = (255, 105, 180)
HEART_MASK = (
    "01010",
    "11111",
    "11111",
    "01110",
    "00100",
)

# Optional pixel-art override, same convention as fruit_catcher: drop a heart.png
# into this directory (RGBA, transparent background) to replace the built-in
# HEART_MASK shape. Only one sprite is needed -- lost lives simply stop drawing a
# heart rather than needing a separate "empty" variant.
ASSETS_DIR = Path(__file__).parent / "assets"
SPRITE_ALPHA_THRESHOLD = 128

# Eric's toddler requested a rainbow-striped car -- one row per hue, most-primary
# version of each, top to bottom. This also sets CAR_HEIGHT (one row per stripe),
# which now happens to match OBSTACLE_HEIGHT (both 6) now that orange is included --
# not load-bearing, just a coincidence of there being six rainbow colors.
CAR_STRIPE_COLORS_RGB = [
    (255, 0, 0),  # red
    (255, 140, 0),  # orange
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
        self.title_font = layout.font("racer.title")
        self.width = layout.width
        self.height = layout.height
        self._game_mode = GameMode()
        self._heart_sprite = self._load_heart_sprite()

        road_width = int(self.width * (1 - 2 * ROAD_MARGIN_FRACTION))
        self.road_left = (self.width - road_width) // 2
        self.road_right = self.road_left + road_width

        self._reset_game()

    @staticmethod
    def _load_heart_sprite() -> Optional[Image.Image]:
        path = ASSETS_DIR / "heart.png"
        if not path.exists():
            return None
        try:
            return Image.open(path).convert("RGBA")
        except OSError as e:
            LOGGER.warning("[toddler_racer] Failed to load heart sprite %s: %s", path, e)
            return None

    def wait_time(self) -> float:
        return self.config.frame_seconds

    def reset(self) -> None:
        self._reset_game()

    def render(self, data: Data, canvas: "Canvas", graphics: api.renderer.graphics, scrolling_text_pos: int) -> Optional[int]:
        self._consume_input()
        self._advance()
        self._draw(canvas, graphics)
        return None

    def _reset_game(self) -> None:
        self.car_x = (self.road_left + self.road_right - CAR_WIDTH) // 2
        self.obstacles: list[dict] = []
        self.score = 0
        self.lives = self.config.starting_lives
        self.frame_count = 0
        self.hit_animation_frames_remaining = 0
        self.game_over = False

    def _consume_input(self) -> None:
        # consume_steer() is drained unconditionally even though the car moves from
        # held_direction() instead -- it's a one-shot flag shared with the menu (see
        # fruit_catcher's identical reasoning), and leaving it unread here would make
        # it appear (falsely) still pending the next time the menu is opened.
        self._game_mode.consume_steer()
        confirmed = self._game_mode.consume_confirm()
        direction = self._game_mode.held_direction()

        if self.game_over:
            if confirmed:
                self._reset_game()
            return

        if self.hit_animation_frames_remaining > 0:
            return  # frozen during the hit animation -- input is drained above but ignored

        if direction == "left":
            self.car_x = max(self.road_left, self.car_x - self.config.steer_step)
        elif direction == "right":
            self.car_x = min(self.road_right - CAR_WIDTH, self.car_x + self.config.steer_step)

    def _advance(self) -> None:
        if self.game_over:
            return
        self.frame_count += 1

        if self.hit_animation_frames_remaining > 0:
            self.hit_animation_frames_remaining -= 1
            if self.hit_animation_frames_remaining == 0 and self.lives <= 0:
                self.game_over = True
            return

        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        remaining = []
        for obstacle in self.obstacles:
            obstacle["y"] += self.config.fall_speed
            if self._overlaps(obstacle, car_y):
                self.lives -= 1
                self.hit_animation_frames_remaining = self.config.hit_animation_frames
                continue  # despawn immediately, same as fruit_catcher's caught objects

            if obstacle["y"] < self.height:
                remaining.append(obstacle)
            else:
                self.score += 1  # passed the bottom edge without ever hitting the car
        self.obstacles = remaining

        if self.frame_count % self.config.spawn_interval_frames == 0:
            x = random.randint(self.road_left, self.road_right - OBSTACLE_WIDTH)
            self.obstacles.append({"x": x, "y": 0.0})

    def _overlaps(self, obstacle: dict, car_y: int) -> bool:
        obstacle_bottom = obstacle["y"] + OBSTACLE_HEIGHT
        if obstacle_bottom < car_y or obstacle["y"] > car_y + CAR_HEIGHT:
            return False
        return not (obstacle["x"] + OBSTACLE_WIDTH < self.car_x or obstacle["x"] > self.car_x + CAR_WIDTH)

    def _spin_scale(self) -> float:
        # Same squash-cycle trick as fruit_catcher's basket -- true rotation isn't
        # feasible at this pixel budget, but a horizontal squash (full width -> thin
        # sliver -> full width, repeating) reads clearly enough as "dazed" for a car
        # that's only 3px wide to begin with.
        elapsed = self.config.hit_animation_frames - self.hit_animation_frames_remaining
        pos = elapsed % SPIN_CYCLE_FRAMES
        half = SPIN_CYCLE_FRAMES // 2
        triangle = pos if pos <= half else SPIN_CYCLE_FRAMES - pos
        return max(0.15, triangle / half)

    def _draw(self, canvas, graphics) -> None:
        canvas.Fill(*GRASS_RGB)

        road_color = graphics.Color(*ROAD_RGB)
        for x in range(self.road_left, self.road_right):
            graphics.DrawLine(canvas, x, 0, x, self.height - 1, road_color)

        dash_color = graphics.Color(*DASH_RGB)
        center_x = (self.road_left + self.road_right) // 2
        dash_scroll = self.frame_count * DASH_SPEED_MULTIPLIER
        for y in range(self.height):
            if (y - dash_scroll) % DASH_PERIOD < DASH_LENGTH:
                graphics.DrawLine(canvas, center_x, y, center_x, y, dash_color)

        obstacle_color = graphics.Color(*OBSTACLE_RGB)
        for obstacle in self.obstacles:
            obstacle_y = int(obstacle["y"])
            self._fill_rect(canvas, graphics, obstacle["x"], obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT, obstacle_color)
            self._draw_tires(canvas, graphics, obstacle["x"], obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT)

        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        width_scale = self._spin_scale() if self.hit_animation_frames_remaining > 0 else 1.0
        center = self.car_x + CAR_WIDTH / 2
        for row, rgb in enumerate(CAR_STRIPE_COLORS_RGB):
            width = max(1, round(CAR_WIDTH * width_scale))
            row_x = round(center - width / 2)
            stripe_color = graphics.Color(*rgb)
            graphics.DrawLine(canvas, row_x, car_y + row, row_x + width - 1, car_y + row, stripe_color)
        self._draw_tires(canvas, graphics, self.car_x, car_y, CAR_WIDTH, CAR_HEIGHT)

        score_color = graphics.Color(*SCORE_RGB)
        graphics.DrawText(canvas, self.status_font["font"], 1, self.status_font["size"]["height"], score_color, str(self.score))

        self._draw_lives(canvas, graphics)

        if self.game_over:
            self._draw_game_over(canvas, graphics)

    def _draw_lives(self, canvas, graphics) -> None:
        # Hearts represent lives in reserve, not the one currently in play -- with
        # starting_lives=3 that's 2 hearts to start, one disappearing each time the
        # active life is lost and the next one takes over. The last life (0 hearts
        # showing) has no reserve backing it up.
        size = HEART_ICON_SIZE
        spacing = size + HEART_ICON_GAP
        y = self.height - HEART_ICON_MARGIN - size
        heart_color = graphics.Color(*HEART_RGB)
        for i in range(max(0, self.lives - 1)):
            x = HEART_ICON_MARGIN + i * spacing
            if self._heart_sprite is not None:
                self._draw_sprite(canvas, self._heart_sprite, x, y)
            else:
                self._draw_heart_mask(canvas, graphics, x, y, heart_color)

    def _draw_heart_mask(self, canvas, graphics, x: int, y: int, color) -> None:
        for row, line in enumerate(HEART_MASK):
            for col, pixel in enumerate(line):
                if pixel == "1":
                    graphics.DrawLine(canvas, x + col, y + row, x + col, y + row, color)

    def _draw_sprite(self, canvas, sprite: "Image.Image", x: int, y: int) -> None:
        # Same per-pixel alpha-composited blit as fruit_catcher/espn_sports use for
        # their own optional sprite overrides.
        for px in range(sprite.width):
            for py in range(sprite.height):
                r, g, b, a = sprite.getpixel((px, py))
                if a >= SPRITE_ALPHA_THRESHOLD:
                    canvas.SetPixel(x + px, y + py, r, g, b)

    def _draw_game_over(self, canvas, graphics) -> None:
        color = graphics.Color(*GAME_OVER_RGB)
        text = "GAME OVER"
        x = center_text_position(text, canvas.width // 2, self.title_font["size"]["width"])
        graphics.DrawText(canvas, self.title_font["font"], x, self.height // 2, color, text)

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
