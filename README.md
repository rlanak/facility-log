# facility-log

**English** · [Português](README.pt-BR.md)

Stock reports for **Foxhole** facilities, ready to paste into Discord: stock per building, facility
totals, production estimates, and what's still needed to produce or farm to hit your targets.

- Log stock by hand, from a **screenshot** of the STOCKPILE panel (items are recognized
  automatically), or from the **game save** (locations pinned on the map). A read value is never
  saved until you confirm it.
- **Dashboard** tab with a stock estimate based on the production queues, plus a Discord panel that
  updates itself through a webhook (no bot).
- **Private queues**: log who placed one, what's loaded and the time left; the app shows when it's
  ready and warns before the game releases it to the public stockpile (28h).
- Runs **locally** (no account, no paid service) or on the **web**, with Discord login restricted by
  role.
- Customizable look (themes, colors, fonts) and per-person time zone, in Settings.
- Interface in English and Portuguese; item and building names can use a different language than the
  interface.

Two ways to use it:

| | Local | Web |
|---|---|---|
| For | just you, on your PC | the whole regiment, in the browser |
| Login | none | Discord, only members with the role |
| Needs | Python (Windows) | a server with Docker |

---

## Run locally (Windows)

### 1. Install

1. Install **Python 3.11 or newer** ([python.org/downloads](https://www.python.org/downloads/)) and
   tick **"Add python.exe to PATH"** during setup. Check in a terminal: `python --version`.
2. Get the project — with Git (`git clone https://github.com/rlanak/facility-log.git`) or with
   GitHub's **Code → Download ZIP** button (then extract it).
3. In a terminal (PowerShell or Git Bash), inside the project folder:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 2. Open

```bash
.venv/Scripts/python.exe run.py
```

Open **http://localhost:8000**. To stop it, press `Ctrl+C` in the terminal.

**Desktop shortcut (recommended for everyday use):**

```bash
.venv/Scripts/python.exe scripts/create_shortcut.py
```

Creates a **"Facility Log"** shortcut: it starts the app without a console window, with an icon next
to the clock (double-click opens the browser; "Exit" shuts it down). The tray menu follows Windows'
language (English or Portuguese). If you move the project folder,
run the command again.

### 3. Reading screenshots

Works out of the box: **RapidOCR** is installed with the app and reads the numbers. In **Settings**
you can switch to:

- **Local AI (Ollama)** — a bit more accurate, uses your GPU. Install [Ollama](https://ollama.com),
  run `ollama pull glm-ocr` and pick "Local AI" with the `glm-ocr` model. It takes about 3 GB of video
  memory (shared with the game). No GPU? Stay with RapidOCR.
- **AI via API** — Anthropic or any OpenAI-compatible service, with **your own** key (billed per use
  by that service).

When sending a screenshot, **"Zero what isn't in the screenshot"** (on by default) sets to 0 the items
logged in that building that the screenshot doesn't show — the STOCKPILE panel lists everything there
is.

### 4. Import from the game save (optional)

Reads the exact stock of the locations you pinned on the in-game map (e.g. a Material Transfer
Station), no screenshot needed. It needs the save reader, compiled once:

1. Install Rust ([rustup.rs](https://rustup.rs)).
2. Run `.venv/Scripts/python.exe scripts/build_save_parser.py`.

In game, pin the location on the map and open its tooltip (that's when the game stores the stock in
the save). In the app, use the **Save** button on the building card to pick the pin and link it.
After that, **"Refresh linked from save"** (Buildings tab) updates every linked MTS/RTS at once.

### Updating

- **With Git:** `git pull` in the project folder and, if `requirements.txt` changed, run the
  `pip install` again. Then reopen the app.
- **From the ZIP:** download the new ZIP, extract it over the old one and **keep the `data/` folder**.

### Where your data lives

Everything is in the project's **`data/`** folder: `facility_log.db` (the database), `uploads/`
(screenshots), `icon_exemplars/` (icons the app has learned) and `secret.key` (protects saved secrets,
such as the webhook). **Backup = copy the whole `data/` folder** with the app closed.

---

## Run on the web (server with Docker)

You need a Linux server with **Docker** (a small VM is enough: 2 vCPU and 2 GB RAM) and a way to
publish it over HTTPS.

### 1. Create the Discord app

It powers "Sign in with Discord". It isn't a bot and doesn't need to join your server.

1. At [discord.com/developers/applications](https://discord.com/developers/applications), click
   **New Application**.
2. Under **OAuth2**, copy the **Client ID** and generate the **Client Secret** (*Reset Secret*; it's
   shown only once).
3. Still in OAuth2, under **Redirects**, add the address where the app will live, ending in
   `/auth/callback` (e.g. `https://facility-log.example.ts.net/auth/callback`).
4. In Discord, enable **Settings → Advanced → Developer Mode**. Then right-click the server → **Copy
   Server ID**, and right-click the role allowed in (on your profile or in Server Settings → Roles) →
   **Copy Role ID**.

You can ignore the portal's "App Verification" page: verification is only required for bots in more
than 100 servers.

### 2. Configure

On the server, create a folder with this repository's `docker-compose.yml` and `.env.example` (or
clone the repository) and copy the example:

```bash
cp .env.example .env
nano .env
```

Fill in:

| Variable | What it is |
|---|---|
| `DISCORD_CLIENT_ID` | the app's Client ID |
| `DISCORD_CLIENT_SECRET` | the app's Client Secret |
| `DISCORD_REDIRECT_URI` | the same address added under Redirects |
| `DISCORD_GUILD_ID` | your Discord server's ID |
| `DISCORD_ALLOWED_ROLE_IDS` | the role ID (several separated by commas) |
| `SESSION_SECRET` | a long random string — generate with `openssl rand -base64 48` |
| `FACILITY_LOG_SECRET_KEY` | another long random string (protects saved webhooks and keys). **Keep a copy**: without it, saved secrets are lost |

Protect the file: `chmod 600 .env`.

### 3. Start

```bash
docker compose up -d
```

Pulls the published image (`ghcr.io/rlanak/facility-log`) and starts the app on `127.0.0.1:8000` —
reachable only from the server itself until you publish it. Data goes to `./data-docker`. If any login
variable is missing, the app **refuses to start** (on purpose: it never runs open without login).
Check with `docker compose logs`.

Prefer building the image from source? `docker build -t ghcr.io/rlanak/facility-log:latest .` in the
repository folder, then the same `docker compose up -d`.

### 4. Publish over HTTPS

**Tailscale Funnel** (free, no domain, no router ports to open):

1. Create an account at [tailscale.com](https://tailscale.com) and install it on the server:
   `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`.
2. In the Tailscale admin console: **DNS → HTTPS Certificates → Enable**, and make sure the access
   policy gives the server the `funnel` attribute.
3. `sudo tailscale funnel --bg 8000` — the address is printed (`https://<name>.<your-tailnet>.ts.net`).
   That's the one for `DISCORD_REDIRECT_URI` and the Discord portal.

Users don't install anything: they just open the link in a browser.

**Cloudflare Tunnel** is the alternative if you have a domain on Cloudflare: point the tunnel at
`http://127.0.0.1:8000`. A reverse proxy with HTTPS (Caddy, Nginx) works too.

### Reading screenshots on the web

The server reads the numbers with **RapidOCR** (or AI via API, if configured). On top of that, **each
person** can use the AI on **their own computer**: in Settings → **"My computer's AI"**, the browser
sends the number crops to that person's Ollama — the server never reaches anyone's computer. It needs
Ollama with `glm-ocr` and the site's address allowed in Ollama
(`setx OLLAMA_ORIGINS "https://your-address"`, then restart Ollama); the steps are shown on that
screen. If the person's AI doesn't answer, the server reader takes over.

If your server has a GPU and Ollama, `FACILITY_LOG_SERVER_OLLAMA=1` in `.env` makes the server's own
"Local AI" option available to everyone (hidden by default on the web).

### Game save on the web

Each person uploads their own `_MapData.sav` file. In **Chrome and Edge** the browser remembers the
file: after the first time it's just **"Read again"**. In Firefox it's remembered while the tab stays
open.

### Updating

```bash
docker compose pull && docker compose up -d
```

### Backup

Copy the `data-docker/` folder (database, screenshots, learned icons) and keep `.env` separately. A
consistent copy while the app is running:

```bash
docker compose exec -T -u app facility-log python -c "import sqlite3; s=sqlite3.connect('/data/facility_log.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d)"
```

(creates `data-docker/backup.db`).

Uploaded screenshots are kept and go into every backup, though they are only used while being read. To
keep them from piling up, `FACILITY_LOG_UPLOAD_DAYS=30` in `.env` deletes those older than 30 days (off
by default).

---

## Troubleshooting

| Symptom | What to do |
|---|---|
| Local: `python` is not recognized | Reinstall Python ticking "Add python.exe to PATH" |
| Local: the shortcut opens nothing | Check `data/facility_log.log`; if port 8000 is taken, set `PORT=8001` in a `.env` |
| Local: "403" when opened from another PC or through a tunnel | On purpose: without login the app only answers its own PC. For the web, set up Discord login |
| Web: the container won't start | `docker compose logs` — usually a missing `.env` variable |
| Web: error on Discord login | `DISCORD_REDIRECT_URI` must be **identical** to the one under Redirects (https, no trailing slash) |
| Web: "no permission" on login | The account doesn't have the `DISCORD_ALLOWED_ROLE_IDS` role in the `DISCORD_GUILD_ID` server |
| Report time is off | Check the time zone in Settings → Time zone (defaults to your computer's) |
| "Import from save" says the save reader wasn't found | The save reader isn't compiled (step 4 of the local setup). On the web, each person uploads their own `.sav` |

## License

MIT — see [LICENSE](LICENSE).
