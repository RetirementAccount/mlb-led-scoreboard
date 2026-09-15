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
# the top. Two kinds of hazard, both trigger the same spin-out animation (two full
# 4-direction rotations, see _spin_state/_draw_spinning_car) and lock out steering
# for its duration, but differ in how much of the world pauses with the car:
#   - a car: costs a life (3 total, see fruit_catcher for the same mechanism) and
#     fully freezes the world -- no obstacle moves or spawns until the spin ends.
#   - an oil patch: no life lost, and only steering locks -- the road and every
#     other obstacle keep moving normally underneath the spinning car.
# Safely passing a car scores points; an oil patch grants nothing for a safe pass
# but penalizes a hit, same as a car's collision penalty just smaller (no life
# lost). Losing the last life ends the game with a Game Over overlay, restarted via
# the confirm key.
CAR_PASS_POINTS = 10
OIL_HIT_PENALTY = 20
CAR_HIT_PENALTY = 50

ROAD_MARGIN_FRACTION = 0.2  # road spans the middle (1 - 2*margin) of the panel width
CAR_WIDTH = 3  # the car's body -- vertically oriented (taller than wide), tires drawn outside this
TIRE_WIDTH = 1
TIRE_HEIGHT = 2
CAR_Y_MARGIN = 2  # pixels between the car and the bottom edge
OBSTACLE_WIDTH = 3  # same vertical car-body silhouette as the player car, tires included
OBSTACLE_HEIGHT = 6
OIL_WIDTH = 5  # matches the 5x5 oil.png sprite
OIL_HEIGHT = 5
DASH_LENGTH = 2
DASH_PERIOD = 6
# Road dashes previously scrolled at exactly 1px/frame -- the same rate obstacles
# fall at (fall_speed=1.0px/frame default) -- which made the obstacles look
# stationary relative to the road. Scrolling the dashes twice as fast as the
# 1px/frame baseline sells the illusion that everything is moving. An oil patch is
# painted on the road surface itself (unlike a car, which is its own independently
# moving thing), so it falls at this same road-relative speed rather than the
# slower car obstacle speed -- otherwise it would visually drift backwards relative
# to the dashes it's supposedly stuck to.
DASH_SPEED_MULTIPLIER = 2
# The spin-out animation steps the car through 4 orientations -- nose pointing
# north, east, south, west, north -- like a real car spinning out, rather than a
# symmetric width-squash (which reads as a cylinder rolling on its long axis, not a
# car spinning in the plane of the road). One full 4-step rotation is
# SPIN_CYCLE_FRAMES; hit_animation_frames (16) is exactly 2x that, so the car
# completes two full spins per Eric's request before the race unfreezes.
SPIN_CYCLE_FRAMES = 8
SPIN_STATES = 4  # north, east, south, west
SPIN_STATE_FRAMES = SPIN_CYCLE_FRAMES // SPIN_STATES

GRASS_RGB = (20, 90, 20)
ROAD_RGB = (50, 50, 50)
DASH_RGB = (230, 230, 230)
TIRE_RGB = (0, 0, 0)  # was (40,40,40), nearly identical to ROAD_RGB (50,50,50) -- invisible against it
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

# Oil patch hazard: falls down the road like a car obstacle, but colliding with it
# just spins the car out (same freeze-and-spin animation as a crash) rather than
# costing a life. OIL_MASK is the built-in placeholder used whenever no custom
# oil.png is supplied.
OIL_RGB = (25, 20, 15)
OIL_MASK = (
    "01110",
    "11111",
    "11111",
    "11111",
    "01110",
)

# Optional pixel-art overrides, same convention as fruit_catcher: drop a heart.png
# or oil.png into this directory (RGBA, transparent background) to replace the
# built-in placeholder shapes. Only one sprite each is needed -- lost lives simply
# stop drawing a heart rather than needing a separate "empty" variant.
ASSETS_DIR = Path(__file__).parent / "assets"
SPRITE_ALPHA_THRESHOLD = 128

# Eric's toddler requested a rainbow-striped car -- one row per hue, most-primary
# version of each, top to bottom. This also sets CAR_HEIGHT (one row per stripe),
# which now happens to match OBSTACLE_HEIGHT (both 6) now that orange is included --
# not load-bearing, just a coincidence of there being six rainbow colors.
# Also reused for opponent cars: each one is a single solid color, randomly chosen
# from this same list at spawn time (see _spawn_obstacle), rather than striped.
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
        self._heart_sprite = self._load_sprite("heart.png")
        self._oil_sprite = self._load_sprite("oil.png")

        road_width = int(self.width * (1 - 2 * ROAD_MARGIN_FRACTION))
        self.road_left = (self.width - road_width) // 2
        self.road_right = self.road_left + road_width

        self._reset_game()

    @staticmethod
    def _load_sprite(filename: str) -> Optional[Image.Image]:
        path = ASSETS_DIR / filename
        if not path.exists():
            return None
        try:
            return Image.open(path).convert("RGBA")
        except OSError as e:
            LOGGER.warning("[toddler_racer] Failed to load sprite %s: %s", path, e)
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
        self.freeze_world = False
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

        if self.hit_animation_frames_remaining > 0:
            self.hit_animation_frames_remaining -= 1
            if self.hit_animation_frames_remaining == 0 and self.lives <= 0:
                self.game_over = True
            if self.freeze_world:
                # A car crash pauses everything -- obstacles, spawning, and (by not
                # advancing frame_count, which the road dashes scroll off of) the
                # road itself, so the whole scene reads as stopped rather than just
                # the car. An oil spin-out only locks steering (see _consume_input);
                # frame_count keeps advancing below and the road/other obstacles
                # keep moving normally underneath the spinning car.
                return

        self.frame_count += 1
        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        remaining = []
        for obstacle in self.obstacles:
            fall_speed = self.config.fall_speed * DASH_SPEED_MULTIPLIER if obstacle["type"] == "oil" else self.config.fall_speed
            obstacle["y"] += fall_speed
            if self._overlaps(obstacle, car_y):
                if obstacle["type"] == "oil":
                    self.freeze_world = False  # spin-out only -- no life lost, see the module docstring
                    self.score -= OIL_HIT_PENALTY
                else:
                    self.lives -= 1
                    self.freeze_world = True
                    self.score -= CAR_HIT_PENALTY
                self.hit_animation_frames_remaining = self.config.hit_animation_frames
                continue  # despawn immediately, same as fruit_catcher's caught objects

            if obstacle["y"] < self.height:
                remaining.append(obstacle)
            elif obstacle["type"] == "car":
                self.score += CAR_PASS_POINTS  # oil grants nothing for a safe pass, only penalizes a hit
        self.obstacles = remaining

        if self.frame_count % self.config.spawn_interval_frames == 0:
            self.obstacles.append(self._spawn_obstacle())

    def _spawn_obstacle(self) -> dict:
        if random.random() < self.config.oil_chance:
            x = random.randint(self.road_left, self.road_right - OIL_WIDTH)
            return {"x": x, "y": 0.0, "type": "oil", "width": OIL_WIDTH, "height": OIL_HEIGHT}

        x = random.randint(self.road_left, self.road_right - OBSTACLE_WIDTH)
        color = random.choice(CAR_STRIPE_COLORS_RGB)
        return {"x": x, "y": 0.0, "type": "car", "width": OBSTACLE_WIDTH, "height": OBSTACLE_HEIGHT, "color": color}

    def _overlaps(self, obstacle: dict, car_y: int) -> bool:
        obstacle_bottom = obstacle["y"] + obstacle["height"]
        if obstacle_bottom < car_y or obstacle["y"] > car_y + CAR_HEIGHT:
            return False
        return not (obstacle["x"] + obstacle["width"] < self.car_x or obstacle["x"] > self.car_x + CAR_WIDTH)

    def _spin_state(self) -> int:
        # 0=north (normal), 1=east, 2=south, 3=west -- see _draw_spinning_car.
        elapsed = self.config.hit_animation_frames - self.hit_animation_frames_remaining
        return (elapsed // SPIN_STATE_FRAMES) % SPIN_STATES

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

        oil_color = graphics.Color(*OIL_RGB)
        for obstacle in self.obstacles:
            obstacle_x = int(obstacle["x"])
            obstacle_y = int(obstacle["y"])
            if obstacle["type"] == "oil":
                if self._oil_sprite is not None:
                    self._draw_sprite(canvas, self._oil_sprite, obstacle_x, obstacle_y)
                else:
                    self._draw_mask(canvas, graphics, OIL_MASK, obstacle_x, obstacle_y, oil_color)
            else:
                obstacle_color = graphics.Color(*obstacle["color"])
                self._fill_rect(canvas, graphics, obstacle_x, obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT, obstacle_color)
                self._draw_tires(canvas, graphics, obstacle_x, obstacle_y, OBSTACLE_WIDTH, OBSTACLE_HEIGHT)

        car_y = self.height - CAR_Y_MARGIN - CAR_HEIGHT
        if self.hit_animation_frames_remaining > 0:
            cx = self.car_x + CAR_WIDTH / 2
            cy = car_y + CAR_HEIGHT / 2
            self._draw_spinning_car(canvas, graphics, cx, cy, self._spin_state())
        else:
            for row, rgb in enumerate(CAR_STRIPE_COLORS_RGB):
                stripe_color = graphics.Color(*rgb)
                graphics.DrawLine(canvas, self.car_x, car_y + row, self.car_x + CAR_WIDTH - 1, car_y + row, stripe_color)
            self._draw_tires(canvas, graphics, self.car_x, car_y, CAR_WIDTH, CAR_HEIGHT)

        score_color = graphics.Color(*SCORE_RGB)
        graphics.DrawText(canvas, self.status_font["font"], 1, self.status_font["size"]["height"], score_color, str(self.score))

        self._draw_lives(canvas, graphics)

        if self.game_over:
            self._draw_game_over(canvas, graphics)

    def _draw_spinning_car(self, canvas, graphics, cx: float, cy: float, state: int) -> None:
        # A real spin-out: the car's nose (the red end of the stripe order) points
        # north/east/south/west/north in turn, rather than the car merely squashing
        # in place. Since CAR_HEIGHT == len(CAR_STRIPE_COLORS_RGB), rotating 90
        # degrees is just transposing the footprint (width<->height) and picking
        # which end of the stripe order faces the direction the nose points. Tires
        # rotate along with the body via _draw_tires' vertical flag.
        nose_faces_high_index = state in (1, 2)  # east or south -- red end at the higher x/y edge
        colors = list(reversed(CAR_STRIPE_COLORS_RGB)) if nose_faces_high_index else CAR_STRIPE_COLORS_RGB
        vertical = state in (0, 2)  # north/south: same footprint as normal driving

        if vertical:
            width, height = CAR_WIDTH, CAR_HEIGHT
            x = round(cx - width / 2)
            y = round(cy - height / 2)
            for row, rgb in enumerate(colors):
                graphics.DrawLine(canvas, x, y + row, x + width - 1, y + row, graphics.Color(*rgb))
        else:  # east/west: horizontal, footprint rotated 90 degrees
            width, height = CAR_HEIGHT, CAR_WIDTH
            x = round(cx - width / 2)
            y = round(cy - height / 2)
            for col, rgb in enumerate(colors):
                graphics.DrawLine(canvas, x + col, y, x + col, y + height - 1, graphics.Color(*rgb))

        self._draw_tires(canvas, graphics, x, y, width, height, vertical=vertical)

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
                self._draw_mask(canvas, graphics, HEART_MASK, x, y, heart_color)

    def _draw_mask(self, canvas, graphics, mask: tuple, x: int, y: int, color) -> None:
        for row, line in enumerate(mask):
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

    def _draw_tires(self, canvas, graphics, x: int, y: int, width: int, height: int, vertical: bool = True) -> None:
        # Four tire nubs poking out to each side of the car body: one pair near each
        # end of the body's long axis. Shared between the player car (both driving
        # normally and mid-spin, see _draw_spinning_car) and the obstacle "cars" so
        # they all read as the same kind of thing.
        #
        # `vertical` picks which axis is the "long" one: True for a normal
        # top-to-bottom body (tires bulge left/right, one pair near the top, one
        # near the bottom); False for a body rotated 90 degrees into a left-to-right
        # shape (tires bulge top/bottom instead, one pair near the left end, one
        # near the right).
        tire_color = graphics.Color(*TIRE_RGB)
        if vertical:
            near_x = x - TIRE_WIDTH
            far_x = x + width
            far_along = y + height - TIRE_HEIGHT
            for tire_x in (near_x, far_x):
                self._fill_rect(canvas, graphics, tire_x, y, TIRE_WIDTH, TIRE_HEIGHT, tire_color)
                self._fill_rect(canvas, graphics, tire_x, far_along, TIRE_WIDTH, TIRE_HEIGHT, tire_color)
        else:
            near_y = y - TIRE_WIDTH
            far_y = y + height
            far_along = x + width - TIRE_HEIGHT
            for tire_y in (near_y, far_y):
                self._fill_rect(canvas, graphics, x, tire_y, TIRE_HEIGHT, TIRE_WIDTH, tire_color)
                self._fill_rect(canvas, graphics, far_along, tire_y, TIRE_HEIGHT, TIRE_WIDTH, tire_color)

    def _fill_rect(self, canvas, graphics, x: int, y: int, w: int, h: int, color) -> None:
        for row in range(h):
            graphics.DrawLine(canvas, x, y + row, x + w - 1, y + row, color)
