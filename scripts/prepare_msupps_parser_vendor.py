"""Builds the Rust save reader from the sibling repo foxhole-msupps-parser and
copies it into vendor/msupps-parser/ so facility_log.spec can bundle it into
the standalone .exe — end users then read their Maintenance Tunnel mSupps
straight from the game save without installing Rust (see CLAUDE.md,
"Túneis de Manutenção").

Run before building the .exe (re-run whenever the parser changes):

    .venv/Scripts/python.exe scripts/prepare_msupps_parser_vendor.py [path/to/foxhole-msupps-parser]

Needs cargo (rustup) on PATH. Defaults to ../foxhole-msupps-parser next to
this repo.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT.parent / "foxhole-msupps-parser"
DEST = ROOT / "vendor" / "msupps-parser"
EXE_NAME = "foxhole-msupps-parser.exe"


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not (source / "Cargo.toml").is_file():
        raise SystemExit(f"foxhole-msupps-parser not found at {source}. Pass its folder as an argument.")

    subprocess.run(["cargo", "build", "--release"], cwd=source, check=True)
    built = source / "target" / "release" / EXE_NAME

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    shutil.copy2(built, DEST / EXE_NAME)
    print(f"Copied {EXE_NAME} ({built.stat().st_size / 1024:.0f} KB) into {DEST}")


if __name__ == "__main__":
    main()
