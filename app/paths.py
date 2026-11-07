"""The project folder — where web/, data/foxhole/ (catalog) and the user's
data (data/facility_log.db, uploads) live. The app always runs from source.
"""

from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
