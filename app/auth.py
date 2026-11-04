"""Optional Discord login for running facility-log on the web.

Off by default: with no DISCORD_CLIENT_ID in the environment the app behaves
exactly as before — local, no login, no account (a hard project rule; see
CLAUDE.md). With it set, every /api/* and /uploads/* request needs a session
from Discord OAuth2, and only members of one Discord server (guild) holding
one of the allowed roles get in.

No bot is needed: the `guilds.members.read` scope lets the logged-in user's
own token read their membership/roles in that one guild
(GET /users/@me/guilds/{guild_id}/member).

Nothing of the Discord account is kept (03/11/2026, so users don't have to
trust whoever runs the server with it): the token is used once at login
(role + name/avatar), then revoked at Discord and thrown away. The role is
therefore checked at login only; the session lasts SESSION_SECONDS (7 days)
from that login, so someone who loses the role is out within a week.

Environment:
    DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET   — from the Discord Developer Portal app
    DISCORD_REDIRECT_URI                       — e.g. https://logi.example.com/auth/callback
                                                 (must be registered in the portal)
    DISCORD_GUILD_ID                           — the regiment's server
    DISCORD_ALLOWED_ROLE_IDS                   — comma-separated role IDs
    SESSION_SECRET                             — long random string signing the cookie
"""

import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from fastapi.responses import JSONResponse

DISCORD_API = "https://discord.com/api/v10"
DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
SCOPES = "identify guilds.members.read"
SESSION_SECONDS = 7 * 24 * 3600


class Config:
    def __init__(self) -> None:
        self.client_id = os.environ.get("DISCORD_CLIENT_ID", "").strip()
        self.client_secret = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.environ.get("DISCORD_REDIRECT_URI", "").strip()
        self.guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
        self.allowed_role_ids = {
            r.strip() for r in os.environ.get("DISCORD_ALLOWED_ROLE_IDS", "").split(",") if r.strip()
        }
        self.session_secret = os.environ.get("SESSION_SECRET", "").strip()

    @property
    def enabled(self) -> bool:
        return bool(self.client_id)

    def missing(self) -> list[str]:
        """Settings that must be there once login is on — refusing to start
        half-configured beats silently letting everyone in."""
        required = {
            "DISCORD_CLIENT_SECRET": self.client_secret,
            "DISCORD_REDIRECT_URI": self.redirect_uri,
            "DISCORD_GUILD_ID": self.guild_id,
            "DISCORD_ALLOWED_ROLE_IDS": self.allowed_role_ids,
            "SESSION_SECRET": self.session_secret,
        }
        return [name for name, value in required.items() if not value]


config = Config()


class DiscordError(Exception):
    pass


def _request(method: str, url: str, *, data: dict | None = None, token: str | None = None) -> dict:
    headers = {"User-Agent": "facility-log (personal Foxhole tool)"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise DiscordError(f"{exc.code} {exc.read()[:200]!r}") from exc
    except (OSError, ValueError) as exc:
        raise DiscordError(str(exc)) from exc


def new_state() -> str:
    return secrets.token_urlsafe(24)


def authorize_url(state: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "prompt": "none",
        }
    )
    return f"{DISCORD_AUTHORIZE_URL}?{query}"


def exchange_code(code: str) -> dict:
    return _request(
        "POST",
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
    )


def revoke_token(token: str) -> None:
    """Best effort: after login the token is useless to anyone, even if it
    leaked somewhere in between."""
    try:
        _request(
            "POST",
            f"{DISCORD_API}/oauth2/token/revoke",
            data={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "token": token,
                "token_type_hint": "access_token",
            },
        )
    except DiscordError:
        pass


def fetch_user(access_token: str) -> dict:
    return _request("GET", f"{DISCORD_API}/users/@me", token=access_token)


def has_allowed_role(access_token: str) -> bool:
    """False when the user isn't in the guild at all (Discord answers 404)
    or holds none of the allowed roles."""
    try:
        member = _request("GET", f"{DISCORD_API}/users/@me/guilds/{config.guild_id}/member", token=access_token)
    except DiscordError as exc:
        if str(exc).startswith("404"):
            return False
        raise
    return bool(set(member.get("roles", [])) & config.allowed_role_ids)


def avatar_url(user_json: dict) -> str | None:
    if not user_json.get("avatar"):
        return None
    return f"https://cdn.discordapp.com/avatars/{user_json['id']}/{user_json['avatar']}.png?size=64"


# --- Request gate ------------------------------------------------------------

@dataclass
class SessionUser:
    """What the request handlers need about the logged-in user — a plain
    copy, so nothing touches a closed DB session later."""

    id: int
    name: str
    avatar_url: str | None


def _load_user(request) -> SessionUser | None:
    """The session's user, or None. No Discord call here: nothing about the
    Discord account is stored (see the module docstring), so the role was
    checked at login and the session simply expires SESSION_SECONDS after it."""
    from app import models
    from app.database import SessionLocal

    user_id = request.session.get("user_id")
    if not user_id:
        return None  # not logged in (keep the session: it may hold the OAuth state mid-login)
    if time.time() - request.session.get("login_at", 0) > SESSION_SECONDS:
        # The cookie is re-sent on every response, so its own max-age slides;
        # the login time inside it doesn't.
        request.session.clear()
        return None
    with SessionLocal() as db:
        user = db.get(models.User, user_id)
        if not user:
            request.session.clear()
            return None
        return SessionUser(id=user.id, name=user.display_name or user.username, avatar_url=user.avatar_url)


# Paths that name one facility's data, directly or through a building, a
# print or a report. Private facilities are checked against these, so every
# route under them (now and future ones with the same shape) is covered.
_FACILITY_PATHS = [
    (re.compile(r"^/api/facilities/(\d+)(?:/|$)"), "facility"),
    (re.compile(r"^/api/buildings/(\d+)(?:/|$)"), "building"),
    (re.compile(r"^/api/images/(\d+)(?:/|$)"), "image"),
    (re.compile(r"^/api/reports/(\d+)(?:/|$)"), "report"),
]


def _private_facility_blocked(path: str, query_params, user_id: int) -> bool:
    """True when the request touches a private facility that isn't this
    user's. Unknown ids pass through (the route answers 404 itself)."""
    from app import models
    from app.database import SessionLocal

    with SessionLocal() as db:
        facility_id = None
        for pattern, kind in _FACILITY_PATHS:
            m = pattern.match(path)
            if not m:
                continue
            obj_id = int(m.group(1))
            if kind == "facility":
                facility_id = obj_id
            elif kind == "building":
                b = db.get(models.Building, obj_id)
                facility_id = b.facility_id if b else None
            elif kind == "image":
                img = db.get(models.UploadImage, obj_id)
                b = db.get(models.Building, img.building_id) if img else None
                facility_id = b.facility_id if b else None
            else:
                r = db.get(models.Report, obj_id)
                facility_id = r.facility_id if r else None
            break
        if facility_id is None and query_params.get("facility_id", "").isdigit():
            facility_id = int(query_params["facility_id"])
        if facility_id is None:
            return False
        facility = db.get(models.Facility, facility_id)
        return bool(facility and facility.private and facility.owner_id != user_id)


async def gate(request, call_next):
    """Every /api/* and /uploads/* request needs a logged-in user with the
    role when login is on. Static files (the SPA itself) stay public so the
    login screen can load; /api/me answers either way so the SPA knows
    whether to show it."""
    request.state.user = None
    if not config.enabled:
        return await call_next(request)
    from starlette.concurrency import run_in_threadpool

    request.state.user = await run_in_threadpool(_load_user, request)
    path = request.url.path
    protected = path.startswith("/api/") or path.startswith("/uploads/")
    if protected and path != "/api/me" and request.state.user is None:
        return JSONResponse({"detail": "login_required"}, status_code=401)
    if request.state.user is not None and path.startswith("/api/") and await run_in_threadpool(
        _private_facility_blocked, path, request.query_params, request.state.user.id
    ):
        # Same answer as a facility that doesn't exist: a private one isn't
        # even confirmed to others.
        from app.services.errors_i18n import err

        return JSONResponse({"detail": err("facility_not_found", request.query_params.get("lang", "pt-BR"))}, status_code=404)
    return await call_next(request)


def is_local_request(request) -> bool:
    """True for a browser on this same machine — and NOT for traffic coming
    through a tunnel/reverse proxy (cloudflared connects from localhost too,
    but adds forwarding headers). Used so a remote web user never gets to
    read the *server's* own game save as if it were theirs."""
    host = request.client.host if request.client else ""
    forwarded = any(h in request.headers for h in ("x-forwarded-for", "cf-connecting-ip", "forwarded", "x-real-ip"))
    return host in ("127.0.0.1", "::1", "localhost") and not forwarded


def current_user_id(request) -> int | None:
    user = getattr(request.state, "user", None)
    return user.id if user else None
