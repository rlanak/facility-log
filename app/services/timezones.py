"""The user's clock. Times written into text on the server (report header,
"ready ~21:37") must be in the reader's time zone, not the server's — a
Docker server runs on UTC. Every API call carries `tz` (an IANA name, from
the browser or picked in Configurações; see web/js/api.js)."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def zone(tz: str | None):
    """ZoneInfo for `tz`, or None when missing/unknown."""
    if not tz:
        return None
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        return None


def user_now(tz: str | None) -> datetime:
    """Aware 'now' in the user's zone; the server's own zone as fallback."""
    z = zone(tz)
    return datetime.now(z) if z else datetime.now().astimezone()
