"""Starts facility-log.

    python run.py           dev mode: console window, auto-reload on code changes
    pythonw run.py --tray   everyday mode: no console window, an icon in the
                            Windows tray (next to the clock) with Abrir / Sair —
                            this is what the desktop shortcut runs (see
                            scripts/create_shortcut.py)
"""

import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

from app import envfile  # noqa: F401  (.env can set HOST/PORT too)
from app.paths import APP_DIR

# 127.0.0.1 by default: the app only answers this PC. For web mode behind a
# Cloudflare Tunnel that's still right (cloudflared connects locally); set
# HOST=0.0.0.0 only to expose it on the network directly.
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
URL = f"http://127.0.0.1:{PORT}"
LOG_FILE = APP_DIR / "data" / "facility_log.log"


def _already_running() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def _tray_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(4, 120, 87, 255))
    draw.rectangle((16, 16, 26, 48), fill="white")  # F
    draw.rectangle((16, 16, 34, 24), fill="white")
    draw.rectangle((16, 29, 31, 36), fill="white")
    draw.rectangle((38, 16, 48, 48), fill="white")  # L
    draw.rectangle((38, 40, 52, 48), fill="white")
    return img


def run_tray() -> None:
    # Double-clicking the shortcut while it's already up just opens the page.
    if _already_running():
        webbrowser.open(URL)
        return

    # pythonw has no console: stdout/stderr are None, and uvicorn's logging
    # would choke writing to them. Send everything to a log file instead
    # ("Ver log" in the tray menu) — the old console window was the only
    # place errors showed up.
    LOG_FILE.parent.mkdir(exist_ok=True)
    log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    print(f"\n--- facility-log iniciando {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

    import pystray

    from app.main import app as fastapi_app

    server = uvicorn.Server(uvicorn.Config(fastapi_app, host=HOST, port=PORT))
    threading.Thread(target=server.run, daemon=True).start()

    def open_when_ready():
        for _ in range(150):
            if server.started:
                webbrowser.open(URL)
                return
            time.sleep(0.1)

    threading.Thread(target=open_when_ready, daemon=True).start()

    def quit_app(icon, _item):
        server.should_exit = True
        icon.stop()

    icon = pystray.Icon(
        "facility-log",
        _tray_image(),
        f"Facility Log — {URL}",
        menu=pystray.Menu(
            pystray.MenuItem("Abrir Facility Log", lambda: webbrowser.open(URL), default=True),
            pystray.MenuItem("Ver log", lambda: os.startfile(LOG_FILE)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", quit_app),
        ),
    )
    icon.run()


if __name__ == "__main__":
    if "--tray" in sys.argv:
        run_tray()
    else:
        uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
