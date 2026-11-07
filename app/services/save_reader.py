"""Reads the stockpiles the game caches for map pins, straight from Foxhole's
local map save (`%LOCALAPPDATA%\\Foxhole\\Saved\\SaveGames\\<steamid>_MapData.sav`)
— exact numbers, no screenshot/OCR involved.

The save is a binary UE4 GVAS file. Parsing it is delegated to the Rust CLI
in tools/save-parser/ (`--json` mode), which was
validated end to end against real saves — reimplementing GVAS here would just
be a second, untested copy. Build it once with scripts/build_save_parser.py;
the Docker image builds it for Linux.

What the save does and doesn't have (see tools/save-parser/CLAUDE.md): only locations the player *pinned* on the map
(Ctrl+A in game, max 25 per faction) appear, each with the stockpile the game
last cached for it and the game's own `LastUpdated` time — the cache only
refreshes when the player opens that pin's tooltip in game.

Two ways in: running locally, the save on this PC is found automatically;
on the web, the server can't see the player's PC, so the browser uploads the
.sav file and its bytes are parsed instead.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from app.paths import APP_DIR

_EXE_NAME = "foxhole-save-parser.exe" if sys.platform == "win32" else "foxhole-save-parser"

# Built by scripts/build_save_parser.py (cargo build --release). Docker sets
# FOXHOLE_SAVE_PARSER instead.
_PARSER_PATH = APP_DIR / "tools" / "save-parser" / "target" / "release" / _EXE_NAME

# A real save is ~10KB; anything far bigger isn't one.
MAX_SAVE_BYTES = 5 * 1024 * 1024


class SaveReadError(Exception):
    """`key` maps to an errors_i18n message; `detail` is the raw cause (stderr,
    exception text) — not translated, just appended for troubleshooting."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(key)
        self.key = key
        self.detail = detail


def locate_parser() -> Path | None:
    override = os.environ.get("FOXHOLE_SAVE_PARSER")
    if override and Path(override).is_file():
        return Path(override)
    return _PARSER_PATH if _PARSER_PATH.is_file() else None


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


def _run_parser(save_path: Path) -> list[dict]:
    parser = locate_parser()
    if not parser:
        raise SaveReadError("save_parser_missing")
    # CREATE_NO_WINDOW: the packaged app is a console .exe already; without
    # this every read would flash a second console window on Windows.
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            [str(parser), "--json", str(save_path)],
            capture_output=True,
            timeout=15,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SaveReadError("save_parse_failed", str(exc))
    if result.returncode != 0:
        raise SaveReadError("save_parse_failed", result.stderr.decode("utf-8", "replace").strip())
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except ValueError as exc:
        raise SaveReadError("save_parse_failed", str(exc))


def read_pinned_locations(save_bytes: bytes | None = None) -> list[dict]:
    """Every pinned location in the save, as the parser's `--json` prints it
    (map_id, code_name, coords_normalized, grid_coordinate,
    last_updated_unix, stockpile=[{code_name, quantity}], ...). With
    `save_bytes`, parses an uploaded file; otherwise the local save."""
    if save_bytes is None:
        save = locate_save()
        if not save:
            raise SaveReadError("save_missing")
        return _run_parser(save)

    if len(save_bytes) > MAX_SAVE_BYTES or not save_bytes.startswith(b"GVAS"):
        raise SaveReadError("save_invalid_file")
    # The CLI reads a path, so spill the upload to a temp file just for the call.
    fd, tmp_name = tempfile.mkstemp(suffix=".sav")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(save_bytes)
        return _run_parser(Path(tmp_name))
    finally:
        os.unlink(tmp_name)


def pin_key(location: dict) -> str:
    """The game gives a pin no name or ID — only hex + normalized position,
    which doesn't move between readings. Rounded to tolerate float noise
    between parses."""
    x, y = location["coords_normalized"]
    return f"{location['map_id']}:{x:.4f}:{y:.4f}"


def hex_display_name(map_id: str) -> str:
    """"EWorldConquestMapId::WeatheredExpanseHex" -> "Weathered Expanse"."""
    name = map_id.split("::")[-1]
    if name.endswith("Hex"):
        name = name[:-3]
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
