"""Loads `.env` from the app folder (next to run.py) into
os.environ at import time, so web mode can be switched on by dropping a file
there instead of setting system environment variables — same experience for
`python run.py` and Docker (where real env vars win).

Plain KEY=VALUE lines; `#` comments and blank lines ignored; values may be
wrapped in quotes. Variables already set in the environment are never
overwritten. No .env file = nothing happens (local mode, as always).
"""

import os

from app.paths import APP_DIR

ENV_FILE = APP_DIR / ".env"


def load(path=ENV_FILE) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


load()
