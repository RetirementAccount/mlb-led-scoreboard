# Custom sprite overrides

Drop a PNG here to replace that item's built-in color-blob art. If a file isn't
present, the game falls back to drawing the color blob as before -- nothing else
needs to change in code.

Exact filenames the game looks for:

- `cherry.png`
- `orange.png`
- `apple.png`
- `banana.png`
- `bomb.png`

Format:

- PNG with a transparent (alpha) background -- pixels with alpha below 128 are
  skipped, everything else is drawn at full color.
- Any size works, but this is a 64x32 LED matrix and each object only occupies a
  few rows of playfield, so keep sprites small -- 5x5 to 8x8 px is a reasonable
  range. Bigger sprites still render (top-left anchored at the object's falling
  position), they'll just look larger relative to the basket and other objects.
- No resizing/recoloring is done automatically -- what's in the PNG is exactly
  what's drawn, pixel for pixel.
