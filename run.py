import multiprocessing
import os
import threading
import webbrowser

import uvicorn

from app import envfile  # noqa: F401  (.env can set HOST/PORT too)
from app.paths import FROZEN

# 127.0.0.1 by default: the app only answers this PC. For web mode behind a
# Cloudflare Tunnel that's still right (cloudflared connects locally); set
# HOST=0.0.0.0 only to expose it on the network directly.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))

if __name__ == "__main__":
    # Harmless in dev; required on Windows once frozen by PyInstaller, in case
    # any dependency ever spawns a subprocess (multiprocessing re-execs the
    # .exe itself otherwise, per the Python docs for frozen executables).
    multiprocessing.freeze_support()

    if FROZEN:
        # PyInstaller's static analysis only bundles modules it can see
        # imported somewhere — passing uvicorn the "app.main:app" string (as
        # the dev branch below does) means it never sees a real `import
        # app.main` anywhere, so the whole app package silently gets left
        # out of the .exe. Importing it directly here fixes that.
        from app.main import app as fastapi_app

        # No source tree to `git pull` and no console shortcut for a
        # non-technical user to remember — a plain double-click should just
        # open the app. uvicorn's --reload also relies on re-importing this
        # script by module path in a subprocess, which doesn't exist once
        # frozen, so it's disabled here.
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
        uvicorn.run(fastapi_app, host=HOST, port=PORT, reload=False)
    else:
        uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
