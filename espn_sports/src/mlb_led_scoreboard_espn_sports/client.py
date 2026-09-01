import json
import urllib.error
import urllib.request
from typing import Any, Optional

from bullpen.logging import LOGGER

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports"
TIMEOUT_SECONDS = 10
USER_AGENT = "mlb-led-scoreboard-espn-sports/0.1 +https://github.com/MLB-LED-Scoreboard/mlb-led-scoreboard"


def fetch_scoreboard(sport_path: str) -> Optional[dict[str, Any]]:
    """Fetch the raw scoreboard JSON for a given ESPN sport/league path (e.g. "football/nfl").

    Returns None on any network/parse failure so callers can treat it as a deferred/failed update
    rather than crashing the data thread.
    """
    url = f"{BASE_URL}/{sport_path}/scoreboard"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        LOGGER.warning("[espn_sports] Failed to fetch scoreboard for %s: %s", sport_path, e)
        return None
