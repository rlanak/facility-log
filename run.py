"""Starts facility-log.

    python run.py           dev mode: console window, auto-reload on code changes
    pythonw run.py --tray   everyday mode: no console window, an icon in the
                            Windows tray (next to the clock) with Open / Exit —
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

# Tray menu text, in Windows' display language (Portuguese or English;
# FACILITY_LOG_LANG=pt|en overrides). The page itself follows the language
# picked in the app — the tray can't see that (it lives in the browser).
_TRAY_TEXT = {
    "en": {"open": "Open Facility Log", "log": "View log", "exit": "Exit"},
    "pt": {"open": "Abrir Facility Log", "log": "Ver log", "exit": "Sair"},
}


def _tray_lang() -> str:
    forced = os.environ.get("FACILITY_LOG_LANG", "").lower()[:2]
    if forced in _TRAY_TEXT:
        return forced
    try:
        import ctypes

        # LANGID: low 10 bits = primary language; 0x16 = Portuguese.
        if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 0x16:
            return "pt"
        return "en"
    except Exception:
        import locale

        return "pt" if (locale.getlocale()[0] or "").lower().startswith("pt") else "en"


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
    # ("View log" in the tray menu) — the old console window was the only
    # place errors showed up.
    LOG_FILE.parent.mkdir(exist_ok=True)
    log = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    print(f"\n--- facility-log starting {time.strftime('%Y-%m-%d %H:%M:%S')} ---")

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

    text = _TRAY_TEXT[_tray_lang()]
    icon = pystray.Icon(
        "facility-log",
        _tray_image(),
        f"Facility Log — {URL}",
        menu=pystray.Menu(
            pystray.MenuItem(text["open"], lambda: webbrowser.open(URL), default=True),
            pystray.MenuItem(text["log"], lambda: os.startfile(LOG_FILE)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(text["exit"], quit_app),
        ),
    )
    icon.run()


if __name__ == "__main__":
    if "--tray" in sys.argv:
        run_tray()
    else:
        uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
