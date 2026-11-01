"""Builds the Rust game-save reader in tools/save-parser/ — the app looks for
it at tools/save-parser/target/release/ (see app/services/save_reader.py).
Needed for "Importar do save" (MTS etc.); everything else works without it.

Run once after cloning, and again whenever tools/save-parser changes:

    .venv/Scripts/python.exe scripts/build_save_parser.py

Needs cargo (rustup) on PATH.
"""

import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / "tools" / "save-parser"


def main() -> None:
    subprocess.run(["cargo", "build", "--release"], cwd=SOURCE, check=True)
    print(f"OK: {SOURCE / 'target' / 'release'}")


if __name__ == "__main__":
    main()
