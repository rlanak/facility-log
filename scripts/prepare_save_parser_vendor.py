"""Builds the Rust game-save reader in tools/save-parser/ and copies the
binary into vendor/save-parser/ so facility_log.spec can bundle it into the
standalone .exe — end users can import pinned stockpiles (e.g. MTS) from the
game save without installing Rust (see CLAUDE.md, "Leitura do save do jogo").

Run before building the .exe (re-run whenever tools/save-parser changes):

    .venv/Scripts/python.exe scripts/prepare_save_parser_vendor.py

Needs cargo (rustup) on PATH.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "tools" / "save-parser"
DEST = ROOT / "vendor" / "save-parser"
EXE_NAME = "foxhole-save-parser.exe" if sys.platform == "win32" else "foxhole-save-parser"


def main() -> None:
    subprocess.run(["cargo", "build", "--release"], cwd=SOURCE, check=True)
    built = SOURCE / "target" / "release" / EXE_NAME

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    shutil.copy2(built, DEST / EXE_NAME)
    print(f"Copied {EXE_NAME} ({built.stat().st_size / 1024:.0f} KB) into {DEST}")


if __name__ == "__main__":
    main()
