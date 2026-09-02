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
- **Mounting:** Not yet done. Plan is a shared plywood/aluminum backing board (~25" x 6.25" for both panels), M3 standoffs into the panels' threaded mounting holes, M2.5 standoffs for the Pi+Bonnet mounted on the same board (or nearby), cables routed through a channel/raceway down to a wall outlet. Renter-friendly options discussed: Command strips/French cleat for the board, or M3 magnetic feet + metal-backed board for a fully removable mount.
- **Diffusion acrylic:** Ordered (Adafruit "Black LED Diffusion Acrylic Panel" or equivalent) — sits directly on the panel face via Uglu Dash adhesive squares, softens/sharpens raw LED pixel look, improves readability at both close and wall-viewing distance. Not yet installed.
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

## Display now runs as a systemd service (persistent, auto-start)

As of 2026-09-02, the display is managed by systemd rather than hand-launched over SSH — it survives SSH drops and reboots, and restarts itself on failure (`Restart=on-failure`).

- Unit file lives in the repo at `systemd/mlb-led-scoreboard.service` and is installed at `/etc/systemd/system/mlb-led-scoreboard.service` on the Pi (copy, don't symlink, since `/etc` isn't inside the git-tracked working tree). If the run command ever changes (e.g. `--led-chain=2` once the second panel is wired in), edit the repo copy, `git pull` on the Pi, then re-copy it into place and `sudo systemctl daemon-reload && sudo systemctl restart mlb-led-scoreboard.service`.
- Runs as `User=root` in the unit (same reason the manual command needed `sudo`: the LED matrix library needs root for GPIO).
- Useful commands on the Pi:
  ```
  systemctl status mlb-led-scoreboard.service   # no sudo needed to view
  sudo systemctl restart mlb-led-scoreboard.service
  sudo systemctl stop mlb-led-scoreboard.service
  journalctl -u mlb-led-scoreboard.service -f   # tail logs (may need sudo depending on journald ACLs)
  ```
- A narrowly-scoped passwordless sudo rule (`/etc/sudoers.d/mlb-led-scoreboard`, exactly `/home/program27/mlb-led-scoreboard/main.py *`) still exists from before the systemd switch. It's no longer needed for normal operation now that systemd handles starting the process as root itself, but was left in place rather than removed since it's harmless and narrowly scoped.
- Ad-hoc SSH login for anything else still works the same way: `ssh program27@razpi5one.local` (note: the plain `razpi5one` hostname doesn't resolve via normal DNS from a dev machine, only the mDNS `.local` form does — see gotchas below).

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
- No API key needed (ESPN's scoreboard endpoint is public/undocumented — could change or rate-limit without notice; no auth, no SLA).

**Verified on real hardware (2026-09-01):** confirmed working on the Pi, all six leagues showing real ESPN data and rendering correctly at 64x32. Two real issues turned up during that verification, both fixed:

1. **`with_priority: 0` doesn't mean "regularly rotate in"** — it means "only show on a day with zero scheduled MLB/WBC/WPBL games." `data/schedule.py`'s priority system treats priority as a *mode selector*, not a weight: priority 1 = "any game scheduled today" (matches essentially every day in season), priority 2 = a live Cubs game specifically, priority 0 = a true off-day. Screens registered only at `with_priority: 0` (this is the upstream default for `news` and `standings` too, not just the new plugins) never get a turn except on bye days. Fixed by changing `news`, `standings`, and all six new sports screens to `"with_priority": [0, 1]` in both `config.example.json` and the Pi's live `config.json`, so they now interleave with MLB games during the season as originally intended.
2. **Scroll speed governs total rotation pace, not just readability** — `rotation.scroll_until_finished: true` means each screen lingers until its scrolling ticker text fully crosses the panel *or* its configured `seconds` elapses, whichever is longer. `scrolling_speed` in config isn't raw seconds; it's an index 0–6 into `SCROLLING_SPEEDS = [0.3, 0.2, 0.1, 0.075, 0.05, 0.025, 0.01]` (seconds per pixel-frame) in `data/config/__init__.py`. Default index 2 (0.1s/pixel) made full rotation cycles feel very slow. Settled on index **4** (0.05s/pixel, 2x faster) after testing 4 and 5 live on the panel.

**Pi environment gotchas hit and fixed during this session** (worth knowing about, may recur):
- Several `*.egg-info` and `build/` directories under `bullpen/`, `standings/`, and `news/` were **root-owned**, left over from an earlier `sudo pip install`. This broke `pip install -r requirements.txt` with "Cannot update time stamp" / "Permission denied" errors on build. Fixed with `sudo chown -R program27:program27 ~/mlb-led-scoreboard`. Lesson: never `sudo pip install` in this project — only `sudo` the final `./main.py` run, since the LED library needs root for GPIO but nothing else should.
- Added a narrowly-scoped passwordless sudo rule (`/etc/sudoers.d/mlb-led-scoreboard`) for exactly `/home/program27/mlb-led-scoreboard/main.py *`, so the display can be launched/relaunched over SSH without an interactive password prompt. Stopping it still requires an interactive `sudo pkill -f mlb-led-scoreboard/main.py` (deliberately not covered by the NOPASSWD rule, to keep it narrow) — and `pkill -f` should always be run interactively, not as part of a larger compound SSH command string, since `-f` matches against the full command line and will self-match (and kill) the invoking shell if the pattern text appears in that larger string.
- The Pi answers to `razpi5one.local` (mDNS) reliably; plain `razpi5one` doesn't resolve via normal DNS from a dev machine. mDNS resolution has been intermittently flaky (occasional transient "could not resolve hostname" on an otherwise-working connection) — just retry.
- **Long multi-line commands pasted into Eric's terminal get corrupted** — a `nano`/`visudo` paste containing a literal `^X` (meant as a keystroke, not text) landed as text in the file; a multi-line heredoc silently did nothing; a long single-line base64 string got line-wrapped with stray inserted/dropped characters. Root cause looks like visual line-wrapping (from wherever the text is copied) getting preserved as literal characters on paste, rather than anything Pi/SSH-specific. Workaround that worked: get file content onto the Pi via `git commit` + `git pull` instead of terminal paste, then only ask Eric to run short single-line commands (well under ~80 chars) to move it into place with `sudo`.

## Next steps (in rough priority order, per Eric's direction)

1. **Mode-switching input** — Stream Deck (USB HID device, Python lib `python-elgato-streamdeck`) or a cheap USB macro pad (shows up as a standard keyboard) as a physical way to flip the "current mode" variable, running as a separate thread/process alongside the render loop. Not wired to GPIO — plain USB. With the rotation controller now understood to be config/priority driven, this would most likely work by having the input listener rewrite/reload the active priority level rather than needing a new dispatch mechanism.
2. **Crypto/Kalshi ticker mode** — still not started; would be its own `bullpen` plugin following the same pattern as the new sports plugins.
3. **Second panel** — deferred by choice. Needs the barrel-jack-to-screw-terminal adapter (or checking whether one shipped with the panels already) before wiring in.
4. **Physical mounting** — deferred by choice, planned for after software is further along. Backing board + acrylic install (acrylic now ordered — see Hardware section).

Done as of 2026-09-02: display is now a persistent systemd service (see below) rather than hand-launched over SSH. Team colors added to the sports plugins (see below).

## Team colors + logo experiment (2026-09-02)

Added real per-team colors to `espn_sports`, and tried (then shelved) auto-downloaded logos:

- **Colors**: ESPN's scoreboard JSON already includes each team's `color`/`alternateColor` hex values (no separate lookup table needed — works uniformly across all six leagues, including hundreds of NCAA teams with zero extra maintenance). `espn_sports/src/mlb_led_scoreboard_espn_sports/colors.py` picks the team's own color for its abbreviation/score text, falling back to the alternate color (then plain white) when the primary color is too dark to read against the black background (luminance threshold). Shipped and live on the Pi.
- **Logos**: ESPN also provides a direct logo PNG URL per team (`team.logo` in the JSON). Built fetch+disk-cache+downscale support (`logos.py`, wired into `Data.update()` on the background thread so it never blocks rendering) behind a `show_logos` config flag, default **off**. Tested against a real logo (Seahawks) at 12px, 16px, and 24px — even at 24px (75% of the panel's 32px height) the fine linework and thin outlines collapse into an unrecognizable blob. This is inherent to downscaling a detailed vector logo, not a size-tuning problem. Auto-fetch logos are **not recommended** as-is. Hand-drawn/hand-cleaned per-team pixel art was considered as an alternative but shelved (real per-team effort, unclear it'll ever get prioritized) — not currently a planned next step.

## Working conventions to carry over

- Eric prefers one-repo-one-venv, editable installs, structured dev folders (matches his `kalshi_core` pattern elsewhere).
- Preference for conversational exploration of concepts before implementation — build the mental model first, then code.
- Fork-first workflow: customize on his own GitHub fork, Pi pulls from the fork rather than being hand-edited directly.
