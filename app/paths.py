"""Path resolution that works both in dev (running from source with `python
run.py`) and inside a PyInstaller-frozen .exe.

Two different bases matter once frozen:
- BUNDLE_DIR: read-only resources packed into the .exe (web/, data/foxhole/,
  the portable Tesseract). PyInstaller's onefile mode extracts these to a
  fresh temp directory (`sys._MEIPASS`) on every launch, so nothing written
  there survives between runs.
- APP_DIR: where the user's real data lives (facility_log.db, uploads/).
  This must stay next to the .exe itself (not the temp extraction dir), or
  the user's stock history would vanish every time they closed the app.
"""

import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", "")) if FROZEN else Path(__file__).resolve().parent.parent

APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
