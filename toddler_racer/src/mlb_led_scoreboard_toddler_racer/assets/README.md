# Custom heart sprite

Drop a PNG here named exactly `heart.png` to replace the built-in pink pixel-heart
shape used for the life indicator (bottom-left of the screen). If the file isn't
present, the game draws its own small placeholder heart instead -- nothing else
needs to change in code.

Format:

- **5x5 px**, PNG, with a transparent (alpha) background -- pixels with alpha
  below 128 are skipped, everything else is drawn at full color.
- Pink (or whatever color you like) is fine -- the sprite is drawn exactly as
  supplied, no automatic tinting.
- Only one sprite is needed. There's no separate "empty life" variant: as lives
  are lost, hearts simply stop being drawn rather than being replaced by a dimmed
  or outlined version.
- No resizing is done automatically -- a size other than 5x5 still renders (top-left
  anchored, same spacing math), it'll just look bigger/smaller relative to the road
  and car than intended.
