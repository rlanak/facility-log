"""Consumption math for Maintenance Tunnels, ported from the tray app's
`history.rs::compute_consumption()` — but walked over the whole append-only
reading log instead of a single persisted "last rate", since here every
reading is kept (same idea as stock_entries).
"""

import time

from app import models

# Health %: 100% = 4 days (96h) of mSupps left, never more — matches the
# regiment's Discord bot (Lorax) numbers, confirmed in the tray app.
HEALTH_FULL_SECONDS = 96 * 3600


def auto_rate_per_hour(readings: list[models.TunnelReading]) -> float | None:
    """Readings must be in game-time order. Per consecutive pair:
    - stock dropped over real time -> new rate;
    - stock went up -> refilled, the old rate no longer means anything;
    - otherwise (same value) -> keep the last known rate."""
    rate = None
    for prev, cur in zip(readings, readings[1:]):
        dt = cur.game_updated_unix - prev.game_updated_unix
        dq = prev.quantity - cur.quantity
        if dt > 0 and dq > 0:
            rate = dq / dt * 3600
        elif dq < 0:
            rate = None
    return rate


def tunnel_status(tunnel: models.MaintenanceTunnel, now_unix: float | None = None) -> dict:
    """Effective rate (a hand-typed rate — the exact in-game "Maintenance
    Settings" number — wins over the delta estimate) plus a projection of the
    stock to *now*: the cached value is only as fresh as the last time the
    player looked at the tunnel in game, so subtract what was burned since."""
    now_unix = now_unix if now_unix is not None else time.time()
    readings = tunnel.readings
    latest = readings[-1] if readings else None
    auto_rate = auto_rate_per_hour(readings)
    if tunnel.manual_rate_per_hour:
        rate, rate_source = tunnel.manual_rate_per_hour, "manual"
    elif auto_rate:
        rate, rate_source = auto_rate, "auto"
    else:
        rate, rate_source = None, None

    estimated_now = seconds_left = health_pct = None
    if latest and rate:
        elapsed = max(0.0, now_unix - latest.game_updated_unix)
        estimated_now = max(0.0, latest.quantity - rate * elapsed / 3600)
        seconds_left = int(estimated_now / rate * 3600)
        health_pct = min(100, round(seconds_left / HEALTH_FULL_SECONDS * 100))

    return {
        "quantity": latest.quantity if latest else None,
        "game_updated_unix": latest.game_updated_unix if latest else None,
        "reading_count": len(readings),
        "auto_rate_per_hour": auto_rate,
        "rate_per_hour": rate,
        "rate_source": rate_source,
        "estimated_now": estimated_now,
        "seconds_left": seconds_left,
        "health_pct": health_pct,
    }
