# Custom sprites

Drop a PNG here to replace that entity's built-in placeholder shape. If a file
isn't present, the game falls back to a simple colored rectangle (ship/enemy) or a
"+" icon (pickup) -- nothing else needs to change in code.

Exact filenames the game looks for, and the size each is drawn at (top-left
anchored at the entity's position -- any size works, but this is what the fallback
shapes and hitboxes are sized to match):

- `ship.png` -- **6x6 px**. The player ship, always facing right (it never turns).
- `UFO1.png`, `UFO2.png`, `UFO3.png`, ... -- **6x6 px** each, facing left (they fly
  toward the player). Unlike ship.png/pickup.png, enemies support any number of
  variants: every `UFO*.png` file present is loaded, and each spawned enemy picks
  one at random. Add more later just by dropping in another same-size PNG named
  `UFOn.png` -- no code changes needed.
- `pickup.png` -- **5x5 px**. The gun-upgrade pickup.

Format:

- PNG with a transparent (alpha) background -- pixels with alpha below 128 are
  skipped, everything else is drawn at full color.
- No resizing/recoloring is done automatically -- what's in the PNG is exactly
  what's drawn, pixel for pixel.
