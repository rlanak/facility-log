"""Keeps one Discord message per facility showing the "Ao vivo" estimate
— without a bot: a channel webhook can post a message and then keep
editing it.

Opt-in: only facilities with a webhook configured (FacilityWebhook) are
touched; without one this module does nothing. A background task in the
server process edits each message every INTERVAL_SECONDS — the only thing
in the app that runs on its own. It writes nothing but the webhook's own
bookkeeping (message id, last sent, last error); stock stays as logged.

Countdowns use Discord timestamps (<t:unix:R>), which every client redraws
by itself — "insumo acaba em 12 minutos" keeps ticking between edits, so
the edit interval only needs to follow the stock numbers.
"""

import asyncio
import json
import logging
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from app import models
from app.database import SessionLocal
from app.services import foxhole_data, projection
from app.services.report_generator import _display_qty

log = logging.getLogger("facility_log.discord")

INTERVAL_SECONDS = 60
# A thread is given as its ID or as its link (…/channels/<guild>/<channel>/<thread>, from "Copiar link").
THREAD_RE = re.compile(r"^(?:https://(?:ptb\.|canary\.)?discord(?:app)?\.com/channels/\d+/(?:\d+/)?)?(\d{15,25})/?$")
WEBHOOK_URL_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/(\d+)/([\w-]+)/?$")

# Embed limits (Discord): 25 fields, 1024 chars per field value, 6000 in total.
_FIELD_MAX = 1024
_EMBED_BUDGET = 5800
_MAX_BUILDING_FIELDS = 22

_STRINGS = {
    "pt-BR": {
        "title": "📊 {facility} — ao vivo",
        "intro": "Estimativa pelas filas configuradas, contando desde o último lançamento de cada prédio.",
        "updated": "🔄 Atualizado {when} · a cada {interval}",
        "targets": "🎯 Metas (estimado)",
        "production": "🏭 Produção",
        "no_production": "Nenhum prédio com fila configurada.",
        "queues": "{n} filas",
        "queue": "{n} fila",
        "empty_at": "insumo acaba {when}",
        "no_limit": "sem limite de insumo",
        "stopped_since": "parado {when}",
        "stopped": "parado",
        "lacks": "falta {items}",
        "made": "+{qty} {name} desde o lançamento",
        "logged": "lançado {when}",
        "never_logged": "nada lançado ainda",
        "more_buildings": "+{n} prédios não cabem na mensagem",
        "footer": "facility-log · ≈ estimado: não sabe de fila pausada, falta de energia nem material movido",
        "minute": "1 min",
    },
    "en-US": {
        "title": "📊 {facility} — live",
        "intro": "Estimate from the configured queues, counting from each building's last log.",
        "updated": "🔄 Updated {when} · every {interval}",
        "targets": "🎯 Targets (estimated)",
        "production": "🏭 Production",
        "no_production": "No building with queues configured.",
        "queues": "{n} queues",
        "queue": "{n} queue",
        "empty_at": "input runs out {when}",
        "no_limit": "no input limit",
        "stopped_since": "stopped {when}",
        "stopped": "stopped",
        "lacks": "needs {items}",
        "made": "+{qty} {name} since the log",
        "logged": "logged {when}",
        "never_logged": "nothing logged yet",
        "more_buildings": "+{n} buildings don't fit in the message",
        "footer": "facility-log · ≈ estimated: unaware of paused queues, power shortage or moved stock",
        "minute": "1 min",
    },
}


def _t(key: str, lang: str, **kwargs) -> str:
    return _STRINGS.get(lang, _STRINGS["pt-BR"])[key].format(**kwargs)


def _ts(dt: datetime, style: str = "R") -> str:
    return f"<t:{int(dt.timestamp())}:{style}>"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bar(fraction: float, width: int = 10) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "▰" * filled + "▱" * (width - filled)


def _targets_value(targets: list[dict]) -> str:
    lines = []
    for t in sorted(targets, key=lambda t: t["projected"] / t["target"] if t["target"] else 1):
        frac = t["projected"] / t["target"] if t["target"] else 1
        done = " ✅" if frac >= 1 else ""
        lines.append(
            f"`{_bar(frac)}` **{t['name']}** ≈ {_display_qty(t['projected'], t['resource_def_key'])}"
            f" / {_display_qty(t['target'], t['resource_def_key'])}{done}"
        )
    return _clip("\n".join(lines), _FIELD_MAX)


def _building_value(b: dict, lang: str, catalog_lang: str, with_stock: bool) -> str:
    lines = []
    for s in b["slots"]:
        names = ", ".join(p["name"] for p in s["produced"]) or s["recipe_key"]
        queues = _t("queue" if s["queue_count"] == 1 else "queues", lang, n=s["queue_count"])
        if s["running"]:
            status = _t("empty_at", lang, when=_ts(s["empty_at"])) if s["empty_at"] else _t("no_limit", lang)
            line = f"🟢 **{names}** · {queues} · {status}"
        else:
            status = _t("stopped_since", lang, when=_ts(s["empty_at"])) if s["empty_at"] else _t("stopped", lang)
            line = f"🔴 **{names}** · {queues} · {status}"
            if s["missing"]:
                line += " · " + _t("lacks", lang, items=", ".join(s["missing"]))
        lines.append(line)
        made = [p for p in s["produced"] if p["qty"] >= 0.5]
        if made:
            lines.append(
                "　" + " · ".join(_t("made", lang, qty=_display_qty(p["qty"], p["resource"]), name=p["name"]) for p in made)
            )
    if with_stock:
        stock = [(k, q) for k, q in b["projected"].items() if q >= 0.5]
        if stock:
            names = {p["resource"]: p["name"] for s in b["slots"] for p in s["produced"]}
            parts = []
            for key, qty in sorted(stock, key=lambda kv: kv[0]):
                changed = abs(qty - b["logged"].get(key, 0)) >= 0.5
                name = names.get(key) or foxhole_data.resource_display_name(key, catalog_lang)
                parts.append(f"{name} {'≈ ' if changed else ''}{_display_qty(qty, key)}")
            lines.append("📦 " + " · ".join(parts))
    when = _t("logged", lang, when=_ts(b["last_logged_at"])) if b["last_logged_at"] else _t("never_logged", lang)
    lines.append(f"*{when}*")
    return _clip("\n".join(lines), _FIELD_MAX)


def build_embed(facility_name: str, data: dict, lang: str, catalog_lang: str) -> dict:
    now = data["now"]
    producing = [b for b in data["buildings"] if b["slots"]]
    any_stopped = any(not s["running"] for b in producing for s in b["slots"])

    def assemble(with_stock: bool) -> dict:
        fields = []
        if data["targets"]:
            fields.append({"name": _t("targets", lang), "value": _targets_value(data["targets"]), "inline": False})
        for b in producing[:_MAX_BUILDING_FIELDS]:
            title = f"🏭 {b['name']}" + (f" · 📍{b['location']}" if b.get("location") else "")
            fields.append({"name": _clip(title, 256), "value": _building_value(b, lang, catalog_lang, with_stock), "inline": False})
        if len(producing) > _MAX_BUILDING_FIELDS:
            fields.append(
                {"name": "…", "value": _t("more_buildings", lang, n=len(producing) - _MAX_BUILDING_FIELDS), "inline": False}
            )
        if not producing:
            fields.append({"name": _t("production", lang), "value": _t("no_production", lang), "inline": False})
        return {
            "title": _clip(_t("title", lang, facility=facility_name), 256),
            "description": _t("intro", lang)
            + "\n"
            + _t("updated", lang, when=_ts(now), interval=_t("minute", lang)),
            "color": 0xF59E0B if any_stopped else 0x10B981,
            "fields": fields,
            "footer": {"text": _t("footer", lang)},
            "timestamp": now.isoformat(),
        }

    embed = assemble(with_stock=True)
    if _embed_size(embed) > _EMBED_BUDGET:
        embed = assemble(with_stock=False)
    return embed


def _embed_size(embed: dict) -> int:
    return (
        len(embed["title"])
        + len(embed["description"])
        + len(embed["footer"]["text"])
        + sum(len(f["name"]) + len(f["value"]) for f in embed["fields"])
    )


def parse_thread(text: str | None) -> str | None:
    """Thread ID from an ID or a thread link; None for empty. Raises
    ValueError for anything else."""
    text = (text or "").strip()
    if not text:
        return None
    m = THREAD_RE.match(text)
    if not m:
        raise ValueError(text)
    return m.group(1)


def _url(hook: models.FacilityWebhook, path: str = "", **query) -> str:
    # thread_id goes on every call (post, edit, delete) — Discord looks the
    # message up inside the thread.
    if hook.thread_id:
        query["thread_id"] = hook.thread_id
    qs = "&".join(f"{k}={v}" for k, v in query.items())
    return hook.url.rstrip("/") + path + (f"?{qs}" if qs else "")


class WebhookError(Exception):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status


def _call(method: str, url: str, payload: dict | None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        # Discord's edge rejects the default Python-urllib agent.
        headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (facility-log, 1.0)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read()[:300].decode("utf-8", "replace")
        raise WebhookError(exc.code, f"HTTP {exc.code}: {detail}") from exc
    except (OSError, ValueError) as exc:
        raise WebhookError(None, str(exc)) from exc


def send(db, hook: models.FacilityWebhook, now: datetime | None = None) -> None:
    """Edit the facility's message (or post it, the first time or when it
    was deleted in Discord). Records the outcome on the hook; raises
    WebhookError so a caller that asked for it (\"Enviar agora\") can show it."""
    now = now or datetime.now(timezone.utc)
    facility = db.get(models.Facility, hook.facility_id)
    data = projection.facility_dashboard(db, hook.facility_id, now, hook.catalog_lang)
    payload = {
        "embeds": [build_embed(facility.name, data, hook.lang, hook.catalog_lang)],
        "allowed_mentions": {"parse": []},
    }
    try:
        if hook.message_id:
            try:
                _call("PATCH", _url(hook, f"/messages/{hook.message_id}"), payload)
            except WebhookError as exc:
                if exc.status != 404:
                    raise
                # 404 on the message: deleted in Discord, post a fresh one.
                # (If the whole webhook is gone, the POST 404s too and that's the error shown.)
                hook.message_id = None
        if not hook.message_id:
            message = _call("POST", _url(hook, wait="true"), payload)
            hook.message_id = str(message["id"])
        hook.last_error = None
    except WebhookError as exc:
        hook.last_error = str(exc)
        raise
    finally:
        hook.last_sent_at = now
        db.commit()


def delete_message(hook: models.FacilityWebhook) -> None:
    if not hook.message_id:
        return
    try:
        _call("DELETE", _url(hook, f"/messages/{hook.message_id}"), None)
    except WebhookError as exc:
        log.info("webhook da facility %s: não apagou a mensagem: %s", hook.facility_id, exc)


def tick() -> None:
    """One round of the background task. Skips hooks sent recently, so two
    server processes on the same database (the tray app + a test server)
    don't double the edits."""
    now = datetime.now(timezone.utc)
    due_before = now - timedelta(seconds=INTERVAL_SECONDS - 5)
    db = SessionLocal()
    try:
        for hook in db.query(models.FacilityWebhook).all():
            last = hook.last_sent_at
            if last and (last if last.tzinfo else last.replace(tzinfo=timezone.utc)) > due_before:
                continue
            try:
                send(db, hook, now)
            except WebhookError as exc:
                log.warning("webhook da facility %s: %s", hook.facility_id, exc)
            except Exception:  # never let one facility kill the loop
                log.exception("webhook da facility %s", hook.facility_id)
                db.rollback()
    finally:
        db.close()


async def run_forever() -> None:
    while True:
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("discord dashboard tick")
        await asyncio.sleep(INTERVAL_SECONDS)
