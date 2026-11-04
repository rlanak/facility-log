from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth, models, schemas
from app.database import get_db

router = APIRouter(tags=["auth"])


def _fail(reason: str) -> RedirectResponse:
    # The SPA reads ?auth_error=... and shows a translated message.
    return RedirectResponse(f"/?auth_error={reason}#/")


@router.get("/auth/login")
def login(request: Request):
    if not auth.config.enabled:
        return RedirectResponse("/")
    state = auth.new_state()
    request.session["oauth_state"] = state
    return RedirectResponse(auth.authorize_url(state))


@router.get("/auth/callback")
def callback(request: Request, code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    if not auth.config.enabled:
        return RedirectResponse("/")
    expected = request.session.pop("oauth_state", None)
    if error or not code or not state or state != expected:
        return _fail("cancelled")
    try:
        token = auth.exchange_code(code)
        access = token["access_token"]
        if not auth.has_allowed_role(access):
            return _fail("no_role")
        profile = auth.fetch_user(access)
    except (auth.DiscordError, KeyError):
        return _fail("discord")

    user = db.scalar(select(models.User).where(models.User.discord_id == profile["id"]))
    if not user:
        user = models.User(discord_id=profile["id"])
        db.add(user)
    user.username = profile.get("username", "")
    user.display_name = profile.get("global_name") or ""
    user.avatar_url = auth.avatar_url(profile)
    user.access_token = access
    user.refresh_token = token.get("refresh_token", "")
    user.token_expires_at = auth.token_expiry(token)
    user.roles_checked_at = int(datetime.now(timezone.utc).timestamp())
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/")


@router.post("/auth/logout")
def logout(request: Request):
    if auth.config.enabled:
        request.session.clear()
    return {"ok": True}


@router.get("/api/me", response_model=schemas.MeOut)
def me(request: Request):
    user = getattr(request.state, "user", None)
    return schemas.MeOut(
        auth_enabled=auth.config.enabled,
        user=schemas.UserOut(id=user.id, name=user.name, avatar_url=user.avatar_url) if user else None,
    )
