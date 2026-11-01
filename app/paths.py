"""The project folder — where web/, data/foxhole/ (catalog) and the user's
data (data/facility_log.db, uploads) live. There used to be a PyInstaller
.exe with a separate read-only bundle dir; it was retired (31/10/2026) in
favor of running from source with a tray icon (run.py --tray).
"""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
