# LED Matrix Sports Ticker — Project Handoff

This doc captures where the project stands so Claude Code has full context without re-deriving it. Hand this file to Claude Code as background before starting work on the rotation controller.

## Goal

A wall-mounted (eventually desk-optional) LED matrix sports ticker that rotates through multiple content types: MLB scores, other sports (NFL/NHL as later additions), news headlines, and eventually fun modes (crypto/Kalshi ticker, music visualizer/equalizer, retro mini-games, FitQuest stat display). Mode switching intended to eventually be controlled via a Stream Deck or macro pad over USB.

## Hardware (current + planned)

- **Panels:** 2x Adafruit 64x32 RGB LED Matrix, 5mm pitch, 12.5" each. Only **1 panel currently wired and confirmed working**. Second panel deferred — needs its own power path (see below) before adding.
- **Driver:** Adafruit RGB Matrix Bonnet (onboard level shifter; fine for a 2-panel chain, no extra hardware needed there).
- **Brain:** Raspberry Pi 5, hostname `RazPi5One`, SSH user `program27`.
- **Power:**
  - Pi is powered via its own **USB-C supply**, separate from the matrix. (Important: do NOT backpower the Pi from the Bonnet — LED matrix current draw is spiky/noisy and can cause Pi instability/crashes.)
  - Matrix power: 5V 10A supply → 2-Way 2.1mm DC barrel splitter (Adafruit #1351) → Bonnet terminal block (Panel 1) + a barrel-jack-to-screw-terminal adapter (Adafruit #368 or equivalent from DigiKey/Jameco) → Panel 2's stock power cable (Adafruit #4767, which has a 4-pin panel-side connector and red/black spade leads, NOT a barrel jack).
  - Panel 2's full power path is the main **not-yet-done** item.
- **Mounting:** Not yet done. Plan is a shared plywood/aluminum backing board (~25" x 6.25" for both panels), M3 standoffs into the panels' threaded mounting holes, M2.5 standoffs for the Pi+Bonnet mounted on the same board (or nearby), cables routed through a channel/raceway down to a wall outlet. Renter-friendly options discussed: Command strips/French cleat for the board, or M3 magnetic feet + metal-backed board for a fully removable mount. Diffusion acrylic (Adafruit "Black LED Diffusion Acrylic Panel") also planned — sits directly on the panel face via Uglu Dash adhesive squares, softens/sharpens raw LED pixel look, improves readability at both close and wall-viewing distance.
- **Pi 5 GPIO note:** the classic `rpi-rgb-led-matrix` library historically didn't support Pi 5's RP1 GPIO chip, but the specific `mlb-led-scoreboard` fork in use already has Pi 5 support built in (via an `--led-rpi1-pio` flag), and it works — no need to migrate to Adafruit's separate PioMatter library.

## Software state

- Repo: forked from `MLB-LED-Scoreboard/mlb-led-scoreboard` (master branch only) to Eric's own GitHub, then cloned locally to Eric's dev machine — **this is now the active development location**, not the Pi.
- The Pi has its own separate clone (currently pointed at the original upstream repo from initial testing) — **should be re-pointed to Eric's fork** once the fork has real commits, so deployment = `git pull` on the Pi rather than manual edits there.
- Installed via `install.sh` inside a Python venv on the Pi (`venv/` folder, must be owned by `program27`, not root — a `chown -R program27:program27 venv/` was needed after an earlier `sudo`-owned install caused permission errors).
- **Confirmed working run command (1 panel, Pi 5, Adafruit Bonnet):**
  ```
  sudo ./main.py --led-chain=1 --led-parallel=1 --led-gpio-mapping=adafruit-hat --led-cols=64 --led-rows=32
  ```
  Notes on flags: `--led-gpio-mapping=adafruit-hat` is required (default "regular" mapping produces a blank display on this hardware). `--led-cols=64 --led-rows=32` is required (defaults to 32x32, which without this flag renders a 32-wide image that visually "duplicates" across the 64-wide panel).
  For 2 panels later: `--led-chain=2` instead of `--led-chain=1`.
- **Emulator mode (`--emulated`) is currently broken** on this setup — hit a version-mismatch bug between the scoreboard code and newer `RGBMatrixEmulator` releases (`AttributeError` on `config.matrix_options.emulator_title`). Downgrading to `RGBMatrixEmulator==0.16.3` didn't fully resolve it either — the real (non-emulated) hardware path is what's actually confirmed working, so real-hardware testing is the practical path forward rather than the emulator.
- **Not yet configured:**
  - `config.json` favorite team(s)/division(s) — still defaults
  - OpenWeatherMap API key (currently invalid/placeholder, throws a warning, weather screen non-functional until set — free key from home.openweathermap.org)
  - `colors/teams.json`, `colors/scoreboard.json`, `coordinates/w32h32.json` — all currently missing, falling back to defaults (may be fine, may want customizing later for the diffusion-acrylic-adjusted look)

## Known good SSH workflow

```
ssh program27@razpi5one
cd ~/mlb-led-scoreboard
sudo ./main.py --led-chain=1 --led-parallel=1 --led-gpio-mapping=adafruit-hat --led-cols=64 --led-rows=32
```
(Ctrl+C to stop.) Note: dropped VPN connections will kill the SSH session and any foreground process running in it — this is expected, not a Pi problem. A systemd auto-start service (not yet built) would make the display persist independent of SSH sessions and survive drops/reboots.

## Rotation controller — already built (discovered, not written from scratch)

What the "Next steps #1" section below used to call unbuilt turned out to already exist in this fork, under the `bullpen` plugin system:

- **`bullpen`** (`bullpen/`) defines the mode interface almost exactly as originally envisioned: each mode is a `(PluginConfig, PluginData, PluginRenderer)` triple with `update()` (fetch/advance state) and `render()` (draw one frame). Plugins are discovered via setuptools entry points in the group `bullpen.mlbled.plugin` — `bullpen/example-plugin/` is a minimal working template.
- **`renderers/main.py`**'s `MainRenderer.render()` is the master loop: it shows live games, then walks `config.rotation_screen_rules` by priority level and calls each due plugin's `render()` for its configured `seconds`. This is the rotation controller.
- **Config-driven**: `config.json`'s `rotation.screens` array adds a mode by `"kind"` (plugin name), `seconds`, and `with_priority`/`priority`. `schemas/config.schema.json` already has an open-ended "Plugin screen" variant so any plugin name is valid without touching the schema. Per-plugin settings live under the top-level `"plugins": { "<name>": {...} }` key.
- **News** (`news/`) is a full real-world example of this API already wired in (RSS + weather).

Net effect: adding a new "mode" no longer means building infrastructure — it means writing a plugin package (`pyproject.toml` with an entry point + `Config`/`Data`/`Renderer` classes) and adding a `rotation.screens` entry, cloning the `news`/`example-plugin` pattern.

## Sports plugins — in progress

Built `espn_sports/` (`mlb-led-scoreboard-espn-sports` package) — one shared plugin package covering **NFL, NHL, NBA, NCAAF, NCAAB, and EPL**, all backed by ESPN's public (unofficial) scoreboard JSON endpoint (`site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard`), since all six leagues share the same response shape. One `Config`/`Data`/`Renderer` implementation, six thin per-league `Config` subclasses (just sets `SPORT_PATH`/`LEAGUE_KEY`/`LEAGUE_NAME`), six entry points (`nfl`, `nhl`, `nba`, `ncaaf`, `ncaab`, `epl`).

- Optional per-league `teams` filter (like the existing MLB `teams` config) via `"plugins": {"nfl": {"teams": ["Bills"]}}`; omitted means show all of that league's games for the day.
- Renderer is intentionally basic for now: league name, `AWAY score-score HOME`, and a status line (live clock/period, or `FINAL`), one game at a time, cycling every few seconds through however many games matched. No team logos/colors yet — that's a natural follow-up once the base plugin is confirmed working (logo art would need the same low-res pixel-art treatment noted below).
- **Not yet tested against real hardware or the emulator** (emulator is still broken here — see below) — only unit-tested against sample ESPN JSON fixtures. Treat as unverified until run for real on the Pi.
- No API key needed (ESPN's scoreboard endpoint is public/undocumented — could change or rate-limit without notice; no auth, no SLA).

## Next steps (in rough priority order, per Eric's direction)

1. **Verify the new sports plugins on real hardware** — install `./espn_sports` on the Pi (or add to `requirements.txt` there), add `rotation.screens` entries for whichever leagues are in season, confirm rendering looks right at 64x32 and that ESPN's endpoint behaves as expected in practice.
2. **Team colors/logos for the new sports plugins** — currently text-only. Bundled MLB team logos already exist in this repo; the new leagues have none yet.
3. **Custom logo creation** (if/when needed beyond what's bundled) — not a file-type problem, PNG w/ transparency is fine from any tool (Aseprite, Photoshop, etc.); the actual constraint is pixel-art skill at very low resolution (logos read at roughly 16-24px within the canvas). Avoid auto-downscaled vector/gradient art — design pixel-by-pixel or hand-clean instead.
4. **Mode-switching input** — Stream Deck (USB HID device, Python lib `python-elgato-streamdeck`) or a cheap USB macro pad (shows up as a standard keyboard) as a physical way to flip the "current mode" variable, running as a separate thread/process alongside the render loop. Not wired to GPIO — plain USB. With the rotation controller now understood to be config/priority driven, this would most likely work by having the input listener rewrite/reload the active priority level rather than needing a new dispatch mechanism.
5. **Crypto/Kalshi ticker mode** — still not started; would be its own `bullpen` plugin following the same pattern as the new sports plugins.
6. **Second panel** — deferred by choice. Needs the barrel-jack-to-screw-terminal adapter (or checking whether one shipped with the panels already) before wiring in.
7. **Diffusion acrylic + physical mounting** — deferred by choice, planned for after software is further along.
8. **systemd auto-start service** — deferred until happy with the base display, so as not to be automating something still being actively debugged.

## Working conventions to carry over

- Eric prefers one-repo-one-venv, editable installs, structured dev folders (matches his `kalshi_core` pattern elsewhere).
- Preference for conversational exploration of concepts before implementation — build the mental model first, then code.
- Fork-first workflow: customize on his own GitHub fork, Pi pulls from the fork rather than being hand-edited directly.
