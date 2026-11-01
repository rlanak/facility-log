"""Reads Maintenance Tunnel mSupps straight from the game's local map save
(`%LOCALAPPDATA%\\Foxhole\\Saved\\SaveGames\\<steamid>_MapData.sav`) — no
screenshot/OCR involved.

The save is a binary UE4 GVAS file. Parsing it is delegated to the Rust CLI
from the sibling repo `foxhole-msupps-parser` (`--json` mode), which was
validated end to end against real saves — reimplementing GVAS here would just
be a second, untested copy. The packaged .exe bundles that CLI the same way it
bundles Tesseract (see scripts/prepare_msupps_parser_vendor.py +
facility_log.spec).

What the save does and doesn't have (learned the hard way in the tray app,
see that repo's CLAUDE.md): only locations the player *pinned* on the map
(Ctrl+A in game, max 25 per faction) appear, each with the stockpile the game
last cached for it and the game's own `LastUpdated` time. The in-game
"Maintenance Settings" consumption rate is NOT saved anywhere — it's computed
live by the client, so consumption here can only come from comparing two
readings over time (see services/msupps.py) or a rate typed in by hand.
"""

import json
import os
import re
import subprocess
from pathlib import Path

from app.paths import APP_DIR, BUNDLE_DIR

_EXE_NAME = "foxhole-msupps-parser.exe"

# Order matters: the bundled copy wins inside the frozen .exe; in dev, the
# vendored copy (what the .exe will ship) wins over a sibling-repo build.
_PARSER_CANDIDATES = [
    BUNDLE_DIR / "msupps-parser" / _EXE_NAME,
    APP_DIR / "vendor" / "msupps-parser" / _EXE_NAME,
    APP_DIR.parent / "foxhole-msupps-parser" / "target" / "release" / _EXE_NAME,
]

MAINTENANCE_TUNNEL_CODE_NAME = "MaintenanceTunnel"
MSUPPS_CODE_NAME = "MaintenanceSupplies"


class SaveReadError(Exception):
    """`key` maps to an errors_i18n message; `detail` is the raw cause (stderr,
    exception text) — not translated, just appended for troubleshooting."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(key)
        self.key = key
        self.detail = detail


def locate_parser() -> Path | None:
    for path in _PARSER_CANDIDATES:
        if path.is_file():
            return path
    return None


def save_games_dir() -> Path | None:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if not local_appdata:
        return None
    return Path(local_appdata) / "Foxhole" / "Saved" / "SaveGames"


def locate_save() -> Path | None:
    """One `<steamid>_MapData.sav` per Steam account that ever logged in on
    this PC — the most recently written one is the account being played."""
    folder = save_games_dir()
    if not folder or not folder.is_dir():
        return None
    saves = sorted(folder.glob("*_MapData.sav"), key=lambda p: p.stat().st_mtime, reverse=True)
    return saves[0] if saves else None


def read_pinned_locations() -> list[dict]:
    parser = locate_parser()
    if not parser:
        raise SaveReadError("msupps_parser_missing")
    save = locate_save()
    if not save:
        raise SaveReadError("msupps_save_missing")

    # CREATE_NO_WINDOW: the packaged app is a console .exe already; without
    # this every sync would flash a second console window on Windows.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [str(parser), "--json", str(save)],
            capture_output=True,
            timeout=15,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SaveReadError("msupps_parse_failed", str(exc))
    if result.returncode != 0:
        raise SaveReadError("msupps_parse_failed", result.stderr.decode("utf-8", "replace").strip())
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except ValueError as exc:
        raise SaveReadError("msupps_parse_failed", str(exc))


def maintenance_tunnels(locations: list[dict]) -> list[dict]:
    """Same filter as the parser's `maintenance_tunnels_with_msupps()`: only
    tunnel pins that actually have a cached mSupps count."""
    tunnels = []
    for loc in locations:
        if loc.get("code_name") != MAINTENANCE_TUNNEL_CODE_NAME:
            continue
        msupps = next((i["quantity"] for i in loc.get("stockpile", []) if i.get("code_name") == MSUPPS_CODE_NAME), None)
        if msupps is None:
            continue
        tunnels.append({**loc, "msupps": msupps})
    return tunnels


def tunnel_key(map_id: str, coords: list[float]) -> str:
    """The game gives a pin no name or ID — only hex + normalized position,
    which doesn't move between readings. Same format as the tray app's
    `tunnel_key.rs` (rounded to tolerate float noise between parses)."""
    return f"{map_id}:{coords[0]:.4f}:{coords[1]:.4f}"


def hex_display_name(map_id: str) -> str:
    """"EWorldConquestMapId::WeatheredExpanseHex" -> "Weathered Expanse"."""
    name = map_id.split("::")[-1]
    if name.endswith("Hex"):
        name = name[:-3]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
