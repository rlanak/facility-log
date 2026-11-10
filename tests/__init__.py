"""Tests (stdlib unittest — nothing to install):

    .venv/Scripts/python.exe -m unittest discover -s tests -t .

They never touch the real data folder: FACILITY_LOG_DATA_DIR points at a
temporary folder before anything from `app` is imported, and the app runs in
local mode whatever the developer's own .env says.
"""

import atexit
import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="facility-log-tests-")
os.environ["FACILITY_LOG_DATA_DIR"] = _TMP
# Set (to nothing) rather than removed: app/envfile.py only fills in what's
# missing, so a .env with web mode on can't switch it on here.
os.environ["DISCORD_CLIENT_ID"] = ""
os.environ["FACILITY_LOG_REQUIRE_LOGIN"] = ""
os.environ["FACILITY_LOG_ALLOW_OPEN"] = ""
os.environ["FACILITY_LOG_UPLOAD_DAYS"] = ""


def _cleanup() -> None:
    try:
        from app.database import engine

        engine.dispose()  # Windows won't delete a database file that's still open
    except Exception:
        pass
    shutil.rmtree(_TMP, ignore_errors=True)


atexit.register(_cleanup)
