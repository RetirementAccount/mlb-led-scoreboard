import io
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image

from bullpen.logging import LOGGER

CACHE_DIR = Path(__file__).parent / "_logo_cache"
TIMEOUT_SECONDS = 10
USER_AGENT = "mlb-led-scoreboard-espn-sports/0.1 +https://github.com/MLB-LED-Scoreboard/mlb-led-scoreboard"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]")


def fetch_logo(url: str, size: int) -> Optional[Image.Image]:
    """Fetch (with on-disk caching) and downscale a team logo to size x size RGBA.

    Only ever called from the data thread's update() -- never from render(), since
    the render loop must stay fast and this may hit the network on a cache miss.
    """
    if not url:
        return None

    cache_path = CACHE_DIR / _cache_filename(url, size)
    if cache_path.exists():
        try:
            return Image.open(cache_path).convert("RGBA")
        except OSError:
            pass

    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            data = response.read()
        image = Image.open(io.BytesIO(data)).convert("RGBA")
        image = image.resize((size, size), Image.LANCZOS)

        CACHE_DIR.mkdir(exist_ok=True)
        image.save(cache_path)
        return image
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        LOGGER.warning("[espn_sports] Failed to fetch logo %s: %s", url, e)
        return None


def _cache_filename(url: str, size: int) -> str:
    stem = url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    safe_stem = _SAFE_NAME.sub("_", stem)
    return f"{safe_stem}_{size}.png"
