import random
from pathlib import Path
from typing import Optional

from PIL import Image

import bullpen.api as api
from bullpen.logging import LOGGER
from bullpen.util import center_text_position

from .config import Config
from .data import Data

# A simple side-scrolling shooter (Defender-lite, per Eric's spec): the player ship
# is confined to the left edge of the panel and can only move up/down; enemies and
# a gun-upgrade pickup drift in from the right. The ship auto-fires continuously --
# there's no keypad button left over for a dedicated fire key once L/R is spent on
# vertical movement. Touching the pickup (not shooting it -- bullets pass through
# it harmlessly, since constant auto-fire would otherwise make it nearly
# uncollectable) upgrades the gun through 4 escalating shot patterns. Colliding with
# an enemy costs one of 3 lives and triggers a brief invulnerability flicker (no
# freeze/spin -- that fits a car crash, not a twitchy shooter); losing the last life
# shows a Game Over overlay, restarted via confirm (Enter), same as the other games.
PLAYER_X = 2  # fixed horizontal position -- only vertical movement is possible
PLAYER_WIDTH = 6
PLAYER_HEIGHT = 6
ENEMY_WIDTH = 6
ENEMY_HEIGHT = 6
PICKUP_WIDTH = 5
PICKUP_HEIGHT = 5
BULLET_DASH_WIDTH = 2  # a horizontal 2px dash, same silhouette as the racer's road lines
BULLET_DOT_SIZE = 2  # a 2x2 dot

ENEMY_KILL_POINTS = 10

MAX_GUN_LEVEL = 4
# Vertical offsets (from the player's center) and shape for each shot lane, by gun
# level. Level 4 reuses level 3's lanes and adds a pair of diagonal, screen-bouncing
# dots on top (handled separately in _fire(), since they need their own dy).
GUN_LANES = {
    1: [(0, "dash")],
    2: [(-2, "dash"), (2, "dash")],
    3: [(-4, "dash"), (0, "dot"), (4, "dash")],
    4: [(-4, "dash"), (0, "dot"), (4, "dash")],
}
DIAGONAL_BULLET_DY = 1  # pixels/frame vertical component for level 4's bouncing dots

# Eric's ship.png has a single orange pixel on its back row that he wants to pulse
# orange -> yellow -> red like a rocket engine, the same color-cycling trick
# fruit_catcher uses for its bomb's fuse spark (see that game's FUSE_SPARK_CYCLE_RGB).
ENGINE_FLAME_CYCLE_RGB = [(255, 140, 0), (255, 220, 0), (220, 30, 30)]
ENGINE_FLAME_FRAMES_PER_COLOR = 2

# How often the UFO sprites' chasing landing lights advance by one column (see
# _find_lights/_draw_enemy).
LIGHT_CHASE_FRAMES_PER_STEP = 2

# A scrolling starfield background, same right-to-left scroll direction as the
# racer's road dashes -- a handful of fixed 1px stars drifting left and wrapping
# back to the right edge, rather than a fixed lane, since space has no road.
STAR_COUNT = 10
STAR_SPEED = 0.5  # slower than enemies/bullets, for a background-depth feel

SPACE_RGB = (5, 5, 20)
STAR_RGB = (180, 180, 200)
PLAYER_RGB = (0, 200, 255)
PLAYER_ACCENT_RGB = (255, 255, 255)
ENEMY_RGB = (200, 30, 200)
ENEMY_ACCENT_RGB = (255, 220, 255)
PICKUP_RGB = (255, 200, 0)
BULLET_RGB = (255, 255, 255)
SCORE_RGB = (255, 255, 255)
GAME_OVER_RGB = (255, 60, 60)
PIP_RGB = (0, 200, 255)
PIP_EMPTY_RGB = (50, 50, 50)
PIP_SIZE = 2
PIP_SPACING = 3

# Fallback icon for the gun-upgrade pickup when no custom pickup.png is supplied --
# a simple "+" reads as a power-up regardless of art. The ship and enemy fall back
# to plain accented rectangles instead of a hand-drawn mask, since Eric plans to
# supply real art for both fairly soon and their shapes aren't as standardized as a
# heart/oil-drop/plus-sign.
PICKUP_MASK = (
    "00100",
    "00100",
    "11111",
    "00100",
    "00100",
)

# Optional pixel-art overrides, same convention as fruit_catcher/toddler_racer: drop
# a ship.png / enemy.png / pickup.png into this directory (RGBA, transparent
# background) to replace the built-in fallback shapes.
ASSETS_DIR = Path(__file__).parent / "assets"
SPRITE_ALPHA_THRESHOLD = 128


class Renderer(api.PluginRenderer[Data]):
    def __init__(self, config: Config, layout: api.Layout, colors: api.Color) -> None:
        # Same reasoning as the other two games: never part of the timed rotation,
        # so it reaches directly into data/game_mode.py for its input.
        from data.game_mode import GameMode

        self.config = config
        self.status_font = layout.font("shooter.status")
        self.title_font = layout.font("shooter.title")
        self.width = layout.width
        self.height = layout.height
        self._game_mode = GameMode()
        self._ship_sprite = self._load_sprite("ship.png")
        self._ship_engine_pixel = self._find_engine_pixel(self._ship_sprite) if self._ship_sprite is not None else None
        self._enemy_sprites = self._load_enemy_sprites()
        self._pickup_sprite = self._load_sprite("pickup.png")
        # Background only, not game state -- initialized once here rather than in
        # _reset_game, so the starfield keeps scrolling seamlessly through a restart
        # instead of jumping back to fixed starting positions.
        self.stars = [{"x": float(random.randint(0, self.width - 1)), "y": random.randint(0, self.height - 1)} for _ in range(STAR_COUNT)]

        self._reset_game()

    @staticmethod
    def _load_sprite(filename: str) -> Optional[Image.Image]:
        path = ASSETS_DIR / filename
        if not path.exists():
            return None
        try:
            return Image.open(path).convert("RGBA")
        except OSError as e:
            LOGGER.warning("[space_shooter] Failed to load sprite %s: %s", path, e)
            return None

    @classmethod
    def _load_enemy_sprites(cls) -> list:
        # Unlike ship.png/pickup.png (one fixed name each), enemies support any
        # number of variants -- drop UFO1.png, UFO2.png, etc. into assets/ and each
        # one becomes a possible look for a spawned enemy (picked at random per
        # spawn, see _spawn_entity), no code change needed to add more.
        sprites = []
        if not ASSETS_DIR.exists():
            return sprites
        for path in sorted(ASSETS_DIR.glob("UFO*.png")):
            try:
                image = Image.open(path).convert("RGBA")
            except OSError as e:
                LOGGER.warning("[space_shooter] Failed to load enemy sprite %s: %s", path, e)
                continue
            light_row, light_columns, light_color = cls._find_lights(image)
            sprites.append({"image": image, "light_row": light_row, "light_columns": light_columns, "light_color": light_color})
        return sprites

    @staticmethod
    def _find_lights(image: "Image.Image") -> tuple:
        # Auto-detects a row of "landing lights" (2+ yellow pixels) in a supplied
        # UFO sprite -- e.g. Eric's UFO1.png has 2 yellow pixels on its bottom row,
        # spaced 3px apart, that he wants to look like they're chasing/rotating.
        # Rather than requiring several pre-rendered animation frames, this samples
        # the single static sprite for that pattern and animates it procedurally
        # (see _draw_enemy), so it works for any UFO*.png with the same convention
        # without needing per-sprite code.
        best_row, best_columns, best_color = None, [], None
        for y in range(image.height):
            columns = []
            color = None
            for x in range(image.width):
                r, g, b, a = image.getpixel((x, y))
                if a >= SPRITE_ALPHA_THRESHOLD and r > 200 and g > 180 and b < 120:
                    columns.append(x)
                    color = (r, g, b)
            if len(columns) >= 2:
                best_row, best_columns, best_color = y, columns, color
        return best_row, best_columns, best_color

    @staticmethod
    def _find_engine_pixel(image: "Image.Image") -> Optional[tuple]:
        # Auto-detects a single orange pixel (Eric's ship.png has one, on its back
        # row) to animate as a pulsing rocket engine -- see _current_engine_color.
        for y in range(image.height):
            for x in range(image.width):
                r, g, b, a = image.getpixel((x, y))
                if a >= SPRITE_ALPHA_THRESHOLD and r > 200 and 80 < g < 200 and b < 100:
                    return (x, y)
        return None

    def _current_engine_color(self) -> tuple:
        idx = (self.frame_count // ENGINE_FLAME_FRAMES_PER_COLOR) % len(ENGINE_FLAME_CYCLE_RGB)
        return ENGINE_FLAME_CYCLE_RGB[idx]

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
        self.player_y = (self.height - PLAYER_HEIGHT) // 2
        self.gun_level = 1
        self.enemies: list[dict] = []
        self.pickups: list[dict] = []
        self.bullets: list[dict] = []
        self.score = 0
        self.lives = self.config.starting_lives
        self.frame_count = 0
        self.hit_flicker_frames_remaining = 0
        self.game_over = False

    def _consume_input(self) -> None:
        # consume_steer() is drained unconditionally even though movement comes from
        # held_direction() instead -- see fruit_catcher/toddler_racer's identical
        # reasoning: it's a one-shot flag shared with the menu.
        self._game_mode.consume_steer()
        confirmed = self._game_mode.consume_confirm()
        # L/R is the only steer input the keypad has -- reused here as up/down since
        # the ship only ever moves vertically.
        direction = self._game_mode.held_direction()

        if self.game_over:
            if confirmed:
                self._reset_game()
            return

        if direction == "left":
            self.player_y = max(0, self.player_y - self.config.steer_step)
        elif direction == "right":
            self.player_y = min(self.height - PLAYER_HEIGHT, self.player_y + self.config.steer_step)

    def _advance(self) -> None:
        if self.game_over:
            return
        self.frame_count += 1

        if self.hit_flicker_frames_remaining > 0:
            self.hit_flicker_frames_remaining -= 1
            if self.hit_flicker_frames_remaining == 0 and self.lives <= 0:
                self.game_over = True
            # No freeze here, unlike a car crash -- a twitchy shooter should keep
            # moving even while the player is briefly invulnerable and flickering.

        self._move_stars()
        self._move_enemies()
        self._move_pickups()
        self._move_bullets()
        self._resolve_collisions()

        if self.frame_count % self.config.spawn_interval_frames == 0:
            self._spawn_entity()
        if self.frame_count % self.config.fire_interval_frames == 0:
            self._fire()

    def _move_stars(self) -> None:
        for star in self.stars:
            star["x"] -= STAR_SPEED
            if star["x"] < 0:
                # Wrap back to the right edge with a fresh random y, rather than
                # respawning at a fixed spot -- keeps the field looking scattered
                # instead of every star re-entering in a single row over time.
                star["x"] = float(self.width - 1)
                star["y"] = random.randint(0, self.height - 1)

    def _move_enemies(self) -> None:
        for enemy in self.enemies:
            enemy["x"] -= self.config.enemy_speed
        self.enemies = [e for e in self.enemies if e["x"] + ENEMY_WIDTH > 0]

    def _move_pickups(self) -> None:
        for pickup in self.pickups:
            pickup["x"] -= self.config.enemy_speed
        self.pickups = [p for p in self.pickups if p["x"] + PICKUP_WIDTH > 0]

    def _move_bullets(self) -> None:
        for bullet in self.bullets:
            bullet["x"] += self.config.bullet_speed
            if bullet["dy"] != 0:
                bullet["y"] += bullet["dy"]
                size = self._bullet_size(bullet)
                if bullet["y"] <= 0 or bullet["y"] >= self.height - size:
                    bullet["dy"] *= -1
        self.bullets = [b for b in self.bullets if b["x"] < self.width]

    def _resolve_collisions(self) -> None:
        # All positions are already up to date for this frame (movement happens
        # first, in _advance) -- so every check below compares like-for-like,
        # nothing is stale by a frame.
        surviving_bullets = []
        for bullet in self.bullets:
            size = self._bullet_size(bullet)
            hit_enemy = next((e for e in self.enemies if self._overlaps(bullet["x"], bullet["y"], size, size, e["x"], e["y"], ENEMY_WIDTH, ENEMY_HEIGHT)), None)
            if hit_enemy is not None:
                self.enemies.remove(hit_enemy)
                self.score += ENEMY_KILL_POINTS
                continue  # bullet is also consumed on the hit
            surviving_bullets.append(bullet)
        self.bullets = surviving_bullets

        if self.hit_flicker_frames_remaining == 0:
            hit_by_enemy = next((e for e in self.enemies if self._overlaps_player(e, ENEMY_WIDTH, ENEMY_HEIGHT)), None)
            if hit_by_enemy is not None:
                self.enemies.remove(hit_by_enemy)  # despawn immediately on contact, same as the other games' hazards
                self.lives -= 1
                self.hit_flicker_frames_remaining = self.config.hit_flicker_frames

        collected = next((p for p in self.pickups if self._overlaps_player(p, PICKUP_WIDTH, PICKUP_HEIGHT)), None)
        if collected is not None:
            self.pickups.remove(collected)  # bullets pass through it untouched, only touch collects it
            self.gun_level = min(MAX_GUN_LEVEL, self.gun_level + 1)

    def _bullet_size(self, bullet: dict) -> int:
        return BULLET_DOT_SIZE if bullet["shape"] == "dot" else BULLET_DASH_WIDTH

    def _overlaps_player(self, entity: dict, width: int, height: int) -> bool:
        return self._overlaps(entity["x"], entity["y"], width, height, PLAYER_X, self.player_y, PLAYER_WIDTH, PLAYER_HEIGHT)

    @staticmethod
    def _overlaps(ax: float, ay: float, aw: int, ah: int, bx: float, by: float, bw: int, bh: int) -> bool:
        return not (ax + aw < bx or ax > bx + bw or ay + ah < by or ay > by + bh)

    def _spawn_entity(self) -> None:
        if random.random() < self.config.pickup_chance:
            y = random.randint(0, self.height - PICKUP_HEIGHT)
            self.pickups.append({"x": float(self.width), "y": float(y)})
        else:
            y = random.randint(0, self.height - ENEMY_HEIGHT)
            sprite = random.choice(self._enemy_sprites) if self._enemy_sprites else None
            self.enemies.append({"x": float(self.width), "y": float(y), "sprite": sprite})

    def _fire(self) -> None:
        center_y = self.player_y + PLAYER_HEIGHT / 2
        origin_x = float(PLAYER_X + PLAYER_WIDTH)
        for offset, shape in GUN_LANES[self.gun_level]:
            self.bullets.append({"x": origin_x, "y": center_y + offset, "shape": shape, "dy": 0.0})

        if self.gun_level == MAX_GUN_LEVEL:
            for dy in (-DIAGONAL_BULLET_DY, DIAGONAL_BULLET_DY):
                self.bullets.append({"x": origin_x, "y": center_y, "shape": "dot", "dy": float(dy)})

    def _draw(self, canvas, graphics) -> None:
        canvas.Fill(*SPACE_RGB)

        star_color = graphics.Color(*STAR_RGB)
        for star in self.stars:
            x, y = int(star["x"]), star["y"]
            graphics.DrawLine(canvas, x, y, x, y, star_color)

        for enemy in self.enemies:
            self._draw_enemy(canvas, graphics, enemy.get("sprite"), int(enemy["x"]), int(enemy["y"]))

        for pickup in self.pickups:
            x, y = int(pickup["x"]), int(pickup["y"])
            if self._pickup_sprite is not None:
                self._draw_sprite(canvas, self._pickup_sprite, x, y)
            else:
                self._draw_mask(canvas, graphics, PICKUP_MASK, x, y, graphics.Color(*PICKUP_RGB))

        bullet_color = graphics.Color(*BULLET_RGB)
        for bullet in self.bullets:
            x, y = int(bullet["x"]), int(bullet["y"])
            if bullet["shape"] == "dot":
                self._fill_rect(canvas, graphics, x, y, BULLET_DOT_SIZE, BULLET_DOT_SIZE, bullet_color)
            else:
                graphics.DrawLine(canvas, x, y, x + BULLET_DASH_WIDTH - 1, y, bullet_color)

        if not (self.hit_flicker_frames_remaining > 0 and self.frame_count % 2 == 0):
            # Blink every other frame while briefly invulnerable after a hit.
            self._draw_ship(canvas, graphics, PLAYER_X, self.player_y)

        score_color = graphics.Color(*SCORE_RGB)
        graphics.DrawText(canvas, self.status_font["font"], 1, self.status_font["size"]["height"], score_color, str(self.score))

        self._draw_lives(canvas, graphics)

        if self.game_over:
            self._draw_game_over(canvas, graphics)

    def _draw_ship(self, canvas, graphics, x: int, y: int) -> None:
        if self._ship_sprite is None:
            self._draw_fallback_rect(canvas, graphics, x, y, PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_RGB, PLAYER_ACCENT_RGB, accent_on_left=False)
            return

        engine_color = self._current_engine_color() if self._ship_engine_pixel is not None else None
        for px in range(self._ship_sprite.width):
            for py in range(self._ship_sprite.height):
                if (px, py) == self._ship_engine_pixel:
                    continue  # drawn separately below, animated
                r, g, b, a = self._ship_sprite.getpixel((px, py))
                if a >= SPRITE_ALPHA_THRESHOLD:
                    canvas.SetPixel(x + px, y + py, r, g, b)

        if self._ship_engine_pixel is not None:
            ex, ey = self._ship_engine_pixel
            canvas.SetPixel(x + ex, y + ey, *engine_color)

    def _draw_enemy(self, canvas, graphics, sprite_info: Optional[dict], x: int, y: int) -> None:
        if sprite_info is None:
            self._draw_fallback_rect(canvas, graphics, x, y, ENEMY_WIDTH, ENEMY_HEIGHT, ENEMY_RGB, ENEMY_ACCENT_RGB, accent_on_left=True)
            return

        image = sprite_info["image"]
        light_row = sprite_info["light_row"]
        for px in range(image.width):
            for py in range(image.height):
                if light_row is not None and py == light_row:
                    continue  # drawn separately below, animated
                r, g, b, a = image.getpixel((px, py))
                if a >= SPRITE_ALPHA_THRESHOLD:
                    canvas.SetPixel(x + px, y + py, r, g, b)

        light_columns = sprite_info["light_columns"]
        if light_row is not None and light_columns:
            spacing = light_columns[1] - light_columns[0] if len(light_columns) >= 2 else image.width
            phase = (self.frame_count // LIGHT_CHASE_FRAMES_PER_STEP) % max(spacing, 1)
            for base_col in light_columns:
                col = (base_col + phase) % image.width
                canvas.SetPixel(x + col, y + light_row, *sprite_info["light_color"])

    def _draw_fallback_rect(self, canvas, graphics, x: int, y: int, width: int, height: int, body_rgb, accent_rgb, accent_on_left: bool) -> None:
        body_color = graphics.Color(*body_rgb)
        self._fill_rect(canvas, graphics, x, y, width, height, body_color)
        accent_color = graphics.Color(*accent_rgb)
        accent_x = x if accent_on_left else x + width - 1
        graphics.DrawLine(canvas, accent_x, y + height // 2, accent_x, y + height // 2, accent_color)

    def _draw_lives(self, canvas, graphics) -> None:
        total_width = self.config.starting_lives * PIP_SPACING - (PIP_SPACING - PIP_SIZE)
        start_x = self.width - 1 - total_width
        for i in range(self.config.starting_lives):
            filled = i < self.lives
            color = graphics.Color(*(PIP_RGB if filled else PIP_EMPTY_RGB))
            self._fill_rect(canvas, graphics, start_x + i * PIP_SPACING, 1, PIP_SIZE, PIP_SIZE, color)

    def _draw_mask(self, canvas, graphics, mask: tuple, x: int, y: int, color) -> None:
        for row, line in enumerate(mask):
            for col, pixel in enumerate(line):
                if pixel == "1":
                    graphics.DrawLine(canvas, x + col, y + row, x + col, y + row, color)

    def _draw_sprite(self, canvas, sprite: "Image.Image", x: int, y: int) -> None:
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

    def _fill_rect(self, canvas, graphics, x: int, y: int, w: int, h: int, color) -> None:
        for row in range(h):
            graphics.DrawLine(canvas, x, y + row, x + w - 1, y + row, color)
