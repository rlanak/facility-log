"""Keeps one Discord message per facility showing the Dashboard estimate
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
_MAX_BUILDING_FIELDS = 21

_STRINGS = {
    "pt-BR": {
        "title": "📊 {facility} — dashboard",
        "intro": "Estimativa do estoque agora, pelas filas configuradas, a partir do último lançamento de cada prédio.",
        "updated": "🔄 Atualizado {when} · a cada {interval}",
        "summary_running": "🟢 {n} fila(s) rodando",
        "summary_stopped": "🔴 {n} parada(s)",
        "summary_lacking": "falta: {items}",
        "summary_stale": "⚠️ {n} prédio(s) com lançamento de mais de 24h — a estimativa pode estar longe do jogo",
        "targets": "🎯 Metas (estimado)",
        "of": "de",
        "pct_left": "{pct}% · faltam ≈ {qty}",
        "done": "✅ atingida",
        "production": "🏭 Produção",
        "no_production": "Nenhum prédio com fila configurada.",
        "queues": "{n} filas",
        "queue": "{n} fila",
        "empty_at": "insumo acaba {when}",
        "no_limit": "nenhum insumo controlado limita",
        "stopped_since": "parado {when}",
        "stopped": "parado",
        "lacks": "acabou {items} neste prédio",
        "elsewhere": "💡 tem em outro prédio: {list}",
        "in_building": "{qty} em {name}",
        "made": "+{qty} {name} desde o lançamento",
        "stock": "📦 Estoque:",
        "logged": "lançado {when}",
        "stale": "⚠️ lançado {when} — antigo, lance de novo",
        "never_logged": "nada lançado ainda",
        "stations": "🗄️ Estações (estoque lançado)",
        "more_buildings": "+{n} prédios não cabem na mensagem",
        "footer": "facility-log · ≈ estimado — não sabe de fila pausada, falta de energia nem material movido",
        "minute": "1 min",
        "private": "🔒 Filas privadas",
        "private_running": "🔒 **{owner}** · {item} · {building} · fabricado {made} · pronto {when}",
        "private_running_open": "🔒 **{owner}** · {item} · {building} · em produção",
        "private_ready": "✅ **{owner}** · {item} · {building} · {made} prontos — retirar antes de {when} (vai pro público)",
        "private_released": "⚠️ **{owner}** · {item} · {building} · não retirado: foi pro estoque público",
        "incoming": "{qty} já fabricados em fila privada (não contam)",
    },
    "en-US": {
        "title": "📊 {facility} — dashboard",
        "intro": "Estimated stock right now, from the configured queues, starting at each building's last log.",
        "updated": "🔄 Updated {when} · every {interval}",
        "summary_running": "🟢 {n} queue(s) running",
        "summary_stopped": "🔴 {n} stopped",
        "summary_lacking": "missing: {items}",
        "summary_stale": "⚠️ {n} building(s) logged more than 24h ago — the estimate may be far from the game",
        "targets": "🎯 Targets (estimated)",
        "of": "of",
        "pct_left": "{pct}% · ≈ {qty} to go",
        "done": "✅ reached",
        "production": "🏭 Production",
        "no_production": "No building with queues configured.",
        "queues": "{n} queues",
        "queue": "{n} queue",
        "empty_at": "input runs out {when}",
        "no_limit": "no tracked input limits it",
        "stopped_since": "stopped {when}",
        "stopped": "stopped",
        "lacks": "ran out of {items} in this building",
        "elsewhere": "💡 available in another building: {list}",
        "in_building": "{qty} in {name}",
        "made": "+{qty} {name} since the log",
        "stock": "📦 Stock:",
        "logged": "logged {when}",
        "stale": "⚠️ logged {when} — old, log again",
        "never_logged": "nothing logged yet",
        "stations": "🗄️ Stations (logged stock)",
        "more_buildings": "+{n} buildings don't fit in the message",
        "footer": "facility-log · ≈ estimated — unaware of paused queues, power shortage or moved stock",
        "minute": "1 min",
        "private": "🔒 Private queues",
        "private_running": "🔒 **{owner}** · {item} · {building} · made {made} · ready {when}",
        "private_running_open": "🔒 **{owner}** · {item} · {building} · producing",
        "private_ready": "✅ **{owner}** · {item} · {building} · {made} ready — retrieve before {when} (goes public)",
        "private_released": "⚠️ **{owner}** · {item} · {building} · not retrieved: went to the public stockpile",
        "incoming": "{qty} already made in a private queue (not counted)",
    },
}

# A log older than this gets a warning: queues and stock have probably changed.
STALE_SECONDS = 24 * 3600


def _t(key: str, lang: str, **kwargs) -> str:
    return _STRINGS.get(lang, _STRINGS["pt-BR"])[key].format(**kwargs)


def _ts(dt: datetime, style: str = "R") -> str:
    return f"<t:{int(dt.timestamp())}:{style}>"


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _bar(fraction: float, width: int = 10) -> str:
    filled = max(0, min(width, round(fraction * width)))
    return "▰" * filled + "▱" * (width - filled)


def _label(b: dict) -> str:
    return f"{b['name']} ({b['location']})" if b.get("location") else b["name"]


def _targets_value(targets: list[dict], lang: str) -> str:
    lines = []
    for t in sorted(targets, key=lambda t: t["projected"] / t["target"] if t["target"] else 1):
        key = t["resource_def_key"]
        frac = t["projected"] / t["target"] if t["target"] else 1
        state = (
            _t("done", lang)
            if frac >= 1
            else _t("pct_left", lang, pct=round(frac * 100), qty=_display_qty(t["target"] - t["projected"], key))
        )
        line = (
            f"`{_bar(frac)}` **{t['name']}** ≈ {_display_qty(t['projected'], key)} {_t('of', lang)}"
            f" {_display_qty(t['target'], key)} · {state}"
        )
        if t.get("incoming") and frac < 1:
            line += " · " + _t("incoming", lang, qty=_display_qty(t["incoming"], key))
        lines.append(line)
    return _clip("\n".join(lines), _FIELD_MAX)


def _private_value(orders: list[dict], lang: str) -> str:
    lines = []
    for o in orders:
        item = ", ".join(out["name"] for out in o["outputs"]) or o["recipe_key"]
        where = f"{o['building_name']} ({o['building_location']})" if o.get("building_location") else o["building_name"]
        args = {"owner": o["owner_name"], "item": item, "building": where}
        if o["status"] == "released":
            lines.append(_t("private_released", lang, **args))
        elif o["status"] == "ready":
            made = " + ".join(_display_qty(out["done"], out["resource"]) for out in o["outputs"]) or "?"
            lines.append(_t("private_ready", lang, made=made, when=_ts(o["expires_at"]), **args))
        elif o["ready_at"]:
            made = " + ".join(
                f"{_display_qty(out['done'], out['resource'])}/{_display_qty(out['total'], out['resource'])}"
                for out in o["outputs"]
            ) or "?"
            lines.append(_t("private_running", lang, made=made, when=_ts(o["ready_at"]), **args))
        else:
            lines.append(_t("private_running_open", lang, **args))
    return _clip("\n".join(lines), _FIELD_MAX)


def _elsewhere(key: str, building: dict, buildings: list[dict], lang: str) -> list[str]:
    """Where else in the facility a missing input sits (stations first) —
    the estimate never moves material, but the player can."""
    others = [o for o in buildings if o["id"] != building["id"] and o["projected"].get(key, 0) >= 1]
    others.sort(key=lambda o: (not o.get("storage"), -o["projected"][key]))
    return [_t("in_building", lang, qty=_display_qty(o["projected"][key], key), name=_label(o)) for o in others[:2]]


def _logged_line(b: dict, lang: str) -> str:
    if not b["last_logged_at"]:
        return f"*{_t('never_logged', lang)}*"
    if b["elapsed_seconds"] >= STALE_SECONDS and not b.get("storage"):
        return _t("stale", lang, when=_ts(b["last_logged_at"]))
    return f"*{_t('logged', lang, when=_ts(b['last_logged_at']))}*"


def _stock_parts(b: dict, catalog_lang: str) -> list[str]:
    parts = []
    for key, qty in sorted(b["projected"].items(), key=lambda kv: foxhole_data.resource_display_name(kv[0], catalog_lang)):
        if qty < 0.5:
            continue
        changed = abs(qty - b["logged"].get(key, 0)) >= 0.5
        parts.append(f"{foxhole_data.resource_display_name(key, catalog_lang)} {'≈ ' if changed else ''}{_display_qty(qty, key)}")
    return parts


def _building_value(b: dict, buildings: list[dict], lang: str, catalog_lang: str, with_stock: bool) -> str:
    lines = [_logged_line(b, lang)]
    for s in b["slots"]:
        names = ", ".join(p["name"] for p in s["produced"]) or s["recipe_key"]
        queues = _t("queue" if s["queue_count"] == 1 else "queues", lang, n=s["queue_count"])
        if s["running"]:
            status = _t("empty_at", lang, when=_ts(s["empty_at"])) if s["empty_at"] else _t("no_limit", lang)
            lines.append(f"🟢 **{names}** · {queues} · {status}")
        else:
            status = _t("stopped_since", lang, when=_ts(s["empty_at"])) if s["empty_at"] else _t("stopped", lang)
            lines.append(f"🔴 **{names}** · {queues} · {status}")
            if s["missing"]:
                lines.append("　" + _t("lacks", lang, items=", ".join(s["missing"])))
            found = [
                f"{foxhole_data.resource_display_name(k, catalog_lang)} — {', '.join(where)}"
                for k in s.get("missing_keys", [])
                if (where := _elsewhere(k, b, buildings, lang))
            ]
            if found:
                lines.append("　" + _t("elsewhere", lang, list=" · ".join(found)))
        made = [p for p in s["produced"] if p["qty"] >= 0.5]
        if made:
            lines.append(
                "　" + " · ".join(_t("made", lang, qty=_display_qty(p["qty"], p["resource"]), name=p["name"]) for p in made)
            )
    if with_stock:
        parts = _stock_parts(b, catalog_lang)
        if parts:
            lines.append(f"{_t('stock', lang)} " + " · ".join(parts))
    return _clip("\n".join(lines), _FIELD_MAX)


def _stations_value(stations: list[dict], catalog_lang: str) -> str:
    lines = [f"**{_label(b)}**: " + " · ".join(_stock_parts(b, catalog_lang)) for b in stations]
    return _clip("\n".join(lines), _FIELD_MAX)


def _summary(producing: list[dict], lang: str) -> str:
    slots = [s for b in producing for s in b["slots"]]
    if not slots:
        return ""
    running = sum(1 for s in slots if s["running"])
    lacking = sorted({m for s in slots if not s["running"] for m in s["missing"]})
    stale = sum(1 for b in producing if b["last_logged_at"] and b["elapsed_seconds"] >= STALE_SECONDS)
    line = f"{_t('summary_running', lang, n=running)} · {_t('summary_stopped', lang, n=len(slots) - running)}"
    if lacking:
        line += " · " + _t("summary_lacking", lang, items=", ".join(lacking))
    if stale:
        line += "\n" + _t("summary_stale", lang, n=stale)
    return line


def build_embed(facility_name: str, data: dict, lang: str, catalog_lang: str) -> dict:
    now = data["now"]
    buildings = data["buildings"]
    producing = [b for b in buildings if b["slots"]]
    stations = [b for b in buildings if b.get("storage") and not b["slots"] and _stock_parts(b, catalog_lang)]
    slots = [s for b in producing for s in b["slots"]]
    running = sum(1 for s in slots if s["running"])
    # Green: everything runs · amber: something stopped · red: nothing runs.
    color = 0x10B981 if running == len(slots) else (0xF59E0B if running else 0xEF4444)
    summary = _summary(producing, lang)

    def assemble(with_stock: bool, with_stations: bool) -> dict:
        fields = []
        if data["targets"]:
            fields.append({"name": _t("targets", lang), "value": _targets_value(data["targets"], lang), "inline": False})
        if data.get("private_orders"):
            fields.append({"name": _t("private", lang), "value": _private_value(data["private_orders"], lang), "inline": False})
        for b in producing[:_MAX_BUILDING_FIELDS]:
            title = f"🏭 {b['name']}" + (f" · 📍{b['location']}" if b.get("location") else "")
            fields.append(
                {"name": _clip(title, 256), "value": _building_value(b, buildings, lang, catalog_lang, with_stock), "inline": False}
            )
        if len(producing) > _MAX_BUILDING_FIELDS:
            fields.append(
                {"name": "…", "value": _t("more_buildings", lang, n=len(producing) - _MAX_BUILDING_FIELDS), "inline": False}
            )
        if not producing:
            fields.append({"name": _t("production", lang), "value": _t("no_production", lang), "inline": False})
        if with_stations and stations:
            fields.append({"name": _t("stations", lang), "value": _stations_value(stations, catalog_lang), "inline": False})
        description = _t("intro", lang) + "\n" + _t("updated", lang, when=_ts(now), interval=_t("minute", lang))
        if summary:
            description += "\n\n" + summary
        return {
            "title": _clip(_t("title", lang, facility=facility_name), 256),
            "description": description,
            "color": color,
            "fields": fields[:25],
            "footer": {"text": _t("footer", lang)},
            "timestamp": now.isoformat(),
        }

    # Too big for one message: drop the stations first, then the stock lines.
    for with_stock, with_stations in ((True, True), (True, False), (False, False)):
        embed = assemble(with_stock, with_stations)
        if _embed_size(embed) <= _EMBED_BUDGET:
            break
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
