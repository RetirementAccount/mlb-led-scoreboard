import random
from pathlib import Path
from typing import Optional

from PIL import Image

import bullpen.api as api
from bullpen.logging import LOGGER
from bullpen.util import center_text_position

from .config import Config
from .data import Data

# A falling-fruit catcher with lives and a bomb to avoid. Objects fall straight,
# diagonally, or zigzagging, worth 50/100/150 points respectively; catching the bomb
# costs a life. Unlike toddler_racer, this one *can* end (a deliberate contrast in
# the game suite) -- 3 lives, Game Over overlay, restart via confirm.

PLAYFIELD_TOP = 7  # reserve the top rows for the score/lives HUD, objects fall below this
CATCHER_Y_MARGIN = 2

BASKET_ROW_WIDTHS = (7, 7, 5, 3)  # top to bottom -- a simple tapered "basket" silhouette
BASKET_TOP_WIDTH = BASKET_ROW_WIDTHS[0]
BASKET_HEIGHT = len(BASKET_ROW_WIDTHS)
SPIN_CYCLE_FRAMES = 8  # see _spin_scale()

OBJECT_WIDTH = 3
OBJECT_HEIGHT = 4  # 1px accent row (stem/leaf/fuse) on top of a 3x3 body

PIP_SIZE = 2
PIP_SPACING = 3

POINTS = {"straight": 50, "diagonal": 100, "zigzag": 150}
PATTERN_WEIGHTS = {"straight": 50, "diagonal": 30, "zigzag": 20}

# Simplified color-coded fruit representations (body + one accent pixel) rather than
# detailed icons -- the same "keep it simple, it's a handful of pixels" approach as
# the racer's cars, since real iconography doesn't survive at this resolution any
# better than the auto-downloaded team logos did.
FRUITS = [
    {"name": "cherry", "body": (200, 30, 30), "accent": (40, 120, 40)},
    {"name": "orange", "body": (240, 130, 20), "accent": (60, 140, 60)},
    {"name": "apple", "body": (60, 160, 60), "accent": (110, 70, 30)},
    {"name": "banana", "body": (230, 210, 40), "accent": (110, 70, 30)},
]

BG_RGB = (10, 10, 40)
BASKET_WEAVE_A_RGB = (139, 90, 43)
BASKET_WEAVE_B_RGB = (101, 67, 33)
# Steel gray rather than near-black: the original near-black body was too close in
# luminance to the dark navy background to read as an object at a glance. Gray also
# keeps the bomb visually distinct from every fruit (none of which are gray).
BOMB_BODY_RGB = (90, 90, 95)
BOMB_HIGHLIGHT_RGB = (200, 200, 210)
BOMB_FUSE_A_RGB = (255, 200, 0)
BOMB_FUSE_B_RGB = (255, 80, 0)
SCORE_RGB = (255, 255, 255)
LIFE_PIP_RGB = (220, 160, 40)
LIFE_PIP_EMPTY_RGB = (50, 50, 50)
GAME_OVER_RGB = (255, 60, 60)

# Optional per-item pixel-art overrides: drop a same-named PNG (RGBA, transparent
# background) into this directory and it replaces that item's built-in color blob --
# see _load_sprites() below. Keys match FRUITS' "name" fields, plus "bomb".
ASSETS_DIR = Path(__file__).parent / "assets"
SPRITE_ALPHA_THRESHOLD = 128


class Renderer(api.PluginRenderer[Data]):
    def __init__(self, config: Config, layout: api.Layout, colors: api.Color) -> None:
        # Same reasoning as toddler_racer and game_menu: never part of the timed
        # rotation, so it reaches directly into data/game_mode.py for its input.
        from data.game_mode import GameMode

        self.config = config
        self.status_font = layout.font("fruit_catcher.status")
        self.title_font = layout.font("fruit_catcher.title")
        self.width = layout.width
        self.height = layout.height
        self._game_mode = GameMode()
        self._sprites = self._load_sprites()

        self._reset_game()

    @staticmethod
    def _load_sprites() -> dict:
        names = [fruit["name"] for fruit in FRUITS] + ["bomb"]
        sprites = {}
        for name in names:
            path = ASSETS_DIR / f"{name}.png"
            if path.exists():
                try:
                    sprites[name] = Image.open(path).convert("RGBA")
                except OSError as e:
                    LOGGER.warning("[fruit_catcher] Failed to load sprite %s: %s", path, e)
                    sprites[name] = None
            else:
                sprites[name] = None
        return sprites

    def wait_time(self) -> float:
        return self.config.frame_seconds

    def reset(self) -> None:
        self._reset_game()

    def render(self, data: Data, canvas, graphics: api.renderer.graphics, scrolling_text_pos: int) -> Optional[int]:
        self._consume_input()
        self._advance()
        self._draw(canvas, graphics)
        return None

    def _reset_game(self) -> None:
        self.catcher_x = (self.width - BASKET_TOP_WIDTH) // 2
        self.objects: list[dict] = []
        self.score = 0
        self.lives = self.config.starting_lives
        self.frame_count = 0
        self.hit_animation_frames_remaining = 0
        self.game_over = False

    def _consume_input(self) -> None:
        direction = self._game_mode.consume_steer()
        confirmed = self._game_mode.consume_confirm()

        if self.game_over:
            if confirmed:
                self._reset_game()
            return

        if self.hit_animation_frames_remaining > 0:
            return  # frozen during the hit animation -- input is drained above but ignored

        if direction == "left":
            self.catcher_x = max(0, self.catcher_x - self.config.steer_step)
        elif direction == "right":
            self.catcher_x = min(self.width - BASKET_TOP_WIDTH, self.catcher_x + self.config.steer_step)

    def _advance(self) -> None:
        if self.game_over:
            return
        self.frame_count += 1

        if self.hit_animation_frames_remaining > 0:
            self.hit_animation_frames_remaining -= 1
            if self.hit_animation_frames_remaining == 0 and self.lives <= 0:
                self.game_over = True
            return

        catcher_y = self.height - CATCHER_Y_MARGIN - BASKET_HEIGHT
        remaining = []
        for obj in self.objects:
            self._move_object(obj)
            if not obj["caught"] and self._overlaps_catcher(obj, catcher_y):
                obj["caught"] = True
                if obj["type"] == "bomb":
                    self.lives -= 1
                    self.hit_animation_frames_remaining = self.config.hit_animation_frames
                else:
                    self.score += POINTS[obj["pattern"]]
            if not obj["caught"] and obj["y"] < self.height:
                remaining.append(obj)
        self.objects = remaining

        if self.frame_count % self.config.spawn_interval_frames == 0:
            self.objects.append(self._spawn_object())

    def _move_object(self, obj: dict) -> None:
        obj["y"] += self.config.fall_speed

        if obj["pattern"] == "diagonal":
            obj["x"] += self.config.diagonal_speed * obj["dir"]
        elif obj["pattern"] == "zigzag":
            obj["zigzag_timer"] += 1
            if obj["zigzag_timer"] >= self.config.zigzag_period_frames:
                obj["zigzag_timer"] = 0
                obj["dir"] *= -1
            obj["x"] += self.config.zigzag_speed * obj["dir"]

        # Bounce off the side walls so horizontally-moving objects stay in the
        # playfield instead of drifting off-screen before reaching the bottom.
        if obj["x"] < 0:
            obj["x"] = 0
            obj["dir"] *= -1
        elif obj["x"] > self.width - OBJECT_WIDTH:
            obj["x"] = self.width - OBJECT_WIDTH
            obj["dir"] *= -1

    def _spawn_object(self) -> dict:
        x = float(random.randint(0, self.width - OBJECT_WIDTH))
        if random.random() < self.config.bomb_chance:
            return {"x": x, "y": float(PLAYFIELD_TOP), "type": "bomb", "pattern": "straight", "dir": 1, "zigzag_timer": 0, "caught": False}

        pattern = random.choices(list(PATTERN_WEIGHTS.keys()), weights=list(PATTERN_WEIGHTS.values()))[0]
        return {
            "x": x,
            "y": float(PLAYFIELD_TOP),
            "type": "fruit",
            "fruit_index": random.randrange(len(FRUITS)),
            "pattern": pattern,
            "dir": random.choice([-1, 1]),
            "zigzag_timer": 0,
            "caught": False,
        }

    def _overlaps_catcher(self, obj: dict, catcher_y: int) -> bool:
        obj_bottom = obj["y"] + OBJECT_HEIGHT
        if obj_bottom < catcher_y or obj["y"] > catcher_y + BASKET_HEIGHT:
            return False
        return not (obj["x"] + OBJECT_WIDTH < self.catcher_x or obj["x"] > self.catcher_x + BASKET_TOP_WIDTH)

    def _spin_scale(self) -> float:
        # True rotation isn't feasible at this pixel budget (same lesson as the
        # rejected auto-downloaded team logos) -- a cheap horizontal squash cycle
        # (full width -> thin sliver -> full width, repeating) reads clearly enough
        # as "spinning/dazed" for a catcher that's only a few pixels wide to begin with.
        elapsed = self.config.hit_animation_frames - self.hit_animation_frames_remaining
        pos = elapsed % SPIN_CYCLE_FRAMES
        half = SPIN_CYCLE_FRAMES // 2
        triangle = pos if pos <= half else SPIN_CYCLE_FRAMES - pos
        return max(0.15, triangle / half)

    def _draw(self, canvas, graphics) -> None:
        canvas.Fill(*BG_RGB)

        for obj in self.objects:
            self._draw_object(canvas, graphics, obj)

        catcher_y = self.height - CATCHER_Y_MARGIN - BASKET_HEIGHT
        width_scale = self._spin_scale() if self.hit_animation_frames_remaining > 0 else 1.0
        self._draw_catcher(canvas, graphics, self.catcher_x, catcher_y, width_scale)

        self._draw_score(canvas, graphics)
        self._draw_lives(canvas, graphics)

        if self.game_over:
            self._draw_game_over(canvas, graphics)

    def _draw_object(self, canvas, graphics, obj: dict) -> None:
        x, y = int(obj["x"]), int(obj["y"])
        sprite_key = "bomb" if obj["type"] == "bomb" else FRUITS[obj["fruit_index"]]["name"]
        sprite = self._sprites.get(sprite_key)
        if sprite is not None:
            self._draw_sprite(canvas, sprite, x, y)
            return

        if obj["type"] == "bomb":
            body_color = graphics.Color(*BOMB_BODY_RGB)
            highlight_color = graphics.Color(*BOMB_HIGHLIGHT_RGB)
            fuse_rgb = BOMB_FUSE_A_RGB if self.frame_count % 6 < 3 else BOMB_FUSE_B_RGB
            fuse_color = graphics.Color(*fuse_rgb)

            self._fill_rect(canvas, graphics, x, y + 1, OBJECT_WIDTH, OBJECT_HEIGHT - 1, body_color)
            graphics.DrawLine(canvas, x, y + 1, x, y + 1, highlight_color)
            graphics.DrawLine(canvas, x + 1, y, x + 1, y, fuse_color)
            return

        fruit = FRUITS[obj["fruit_index"]]
        body_color = graphics.Color(*fruit["body"])
        accent_color = graphics.Color(*fruit["accent"])
        self._fill_rect(canvas, graphics, x, y + 1, OBJECT_WIDTH, OBJECT_HEIGHT - 1, body_color)
        graphics.DrawLine(canvas, x + 1, y, x + 1, y, accent_color)

    def _draw_sprite(self, canvas, sprite: "Image.Image", x: int, y: int) -> None:
        # Same per-pixel alpha-composited blit as espn_sports' team logos -- see
        # espn_sports/renderer.py's _draw_image for the precedent.
        for px in range(sprite.width):
            for py in range(sprite.height):
                r, g, b, a = sprite.getpixel((px, py))
                if a >= SPRITE_ALPHA_THRESHOLD:
                    canvas.SetPixel(x + px, y + py, r, g, b)

    def _draw_catcher(self, canvas, graphics, x: int, y: int, width_scale: float) -> None:
        weave_a = graphics.Color(*BASKET_WEAVE_A_RGB)
        weave_b = graphics.Color(*BASKET_WEAVE_B_RGB)
        center = x + BASKET_TOP_WIDTH / 2
        for row, base_width in enumerate(BASKET_ROW_WIDTHS):
            width = max(1, round(base_width * width_scale))
            row_x = round(center - width / 2)
            for col in range(width):
                color = weave_a if (row + col) % 2 == 0 else weave_b
                graphics.DrawLine(canvas, row_x + col, y + row, row_x + col, y + row, color)

    def _draw_score(self, canvas, graphics) -> None:
        color = graphics.Color(*SCORE_RGB)
        graphics.DrawText(canvas, self.status_font["font"], 1, self.status_font["size"]["height"], color, str(self.score))

    def _draw_lives(self, canvas, graphics) -> None:
        total_width = self.config.starting_lives * PIP_SPACING - (PIP_SPACING - PIP_SIZE)
        start_x = self.width - 1 - total_width
        for i in range(self.config.starting_lives):
            filled = i < self.lives
            color = graphics.Color(*(LIFE_PIP_RGB if filled else LIFE_PIP_EMPTY_RGB))
            self._fill_rect(canvas, graphics, start_x + i * PIP_SPACING, 1, PIP_SIZE, PIP_SIZE, color)

    def _draw_game_over(self, canvas, graphics) -> None:
        color = graphics.Color(*GAME_OVER_RGB)
        self._draw_centered(canvas, graphics, self.title_font, "GAME OVER", self.height // 2, color)

    def _draw_centered(self, canvas, graphics, font, text: str, y: int, color) -> None:
        x = center_text_position(text, canvas.width // 2, font["size"]["width"])
        graphics.DrawText(canvas, font["font"], x, y, color, text)

    def _fill_rect(self, canvas, graphics, x: int, y: int, w: int, h: int, color) -> None:
        for row in range(h):
            graphics.DrawLine(canvas, x, y + row, x + w - 1, y + row, color)
