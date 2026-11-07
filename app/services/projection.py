"""Live estimate for the dashboard (03/11/2026, the regiment's command asked
for a screen that keeps itself up to date): what each building's stock
probably is *now*, assuming its configured queues kept running since the
last time stock was logged there.

Never written anywhere — computed on every request and only shown, marked
as an estimate. Reports, Metas and the cards keep using logged stock only.
The next real log (save, print, by hand) resets the starting point.

Model, per building:
- Starting point = the building's current logged stock, at the time of its
  most recent log (any resource).
- Each distinct recipe in production_slots runs `queues` cycles in parallel,
  one round every `time_seconds`; only finished rounds count (a cycle in
  progress hasn't delivered yet).
- Recipes run until an input runs out (same cap as production.py).
  Several recipes in one building draw on the same stock one after the
  other here (the first listed gets first pick) — the game interleaves
  them, so this is a ballpark like the rest of the estimates.
- Output lands in the same building. Unlimited inputs (Water) never run out.
Not modeled: queues paused/changed since the log, power shortage, stock
moved between buildings by players.
"""

import math
from datetime import datetime, timedelta, timezone

from app.services import foxhole_data


def _as_utc(dt: datetime) -> datetime:
    # SQLite gives naive datetimes back; they were stored as UTC.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def project_building(building, entries, now: datetime, unlimited_keys: set, lang: str = "pt-BR") -> dict:
    """building: a Building row; entries: its current StockEntry rows."""
    logged: dict[str, float] = {}
    for e in entries:
        if e.resource.resource_def_key:
            logged[e.resource.resource_def_key] = logged.get(e.resource.resource_def_key, 0) + e.quantity
    last_logged_at = max((_as_utc(e.recorded_at) for e in entries), default=None)
    elapsed = max(0, (now - last_logged_at).total_seconds()) if last_logged_at else 0

    stock = dict(logged)
    queues_by_recipe: dict[str, int] = {}
    for slot in building.production_slots or []:
        queues_by_recipe[slot["recipe_key"]] = queues_by_recipe.get(slot["recipe_key"], 0) + slot["queue_count"]

    slots = []
    for recipe_key, queues in queues_by_recipe.items():
        recipe = foxhole_data.get_recipe(building.building_type_key, recipe_key) if building.building_type_key else None
        if not recipe or queues <= 0:
            continue
        cycle_seconds = recipe["time_seconds"]
        inputs = [io for io in recipe["inputs"] if "resource" in io and io["resource"] not in unlimited_keys]
        if inputs:
            max_cycles = int(min(stock.get(io["resource"], 0) // foxhole_data.recipe_io_qty(io) for io in inputs))
        else:
            max_cycles = None  # nothing tracked limits it: runs as long as the queues do
        rounds_done = int(elapsed // cycle_seconds) if cycle_seconds else 0
        cycles_done = rounds_done * queues if max_cycles is None else min(rounds_done * queues, max_cycles)

        for io in inputs:
            stock[io["resource"]] = stock.get(io["resource"], 0) - foxhole_data.recipe_io_qty(io) * cycles_done
        produced = []
        for io in recipe["outputs"]:
            if "resource" not in io:
                continue
            qty = foxhole_data.recipe_io_qty(io) * cycles_done
            stock[io["resource"]] = stock.get(io["resource"], 0) + qty
            produced.append({"resource": io["resource"], "name": foxhole_data.resource_display_name(io["resource"], lang), "qty": qty})

        empty_at = None
        if max_cycles is not None and last_logged_at:
            empty_at = last_logged_at + timedelta(seconds=math.ceil(max_cycles / queues) * cycle_seconds)
        slots.append(
            {
                "recipe_key": recipe_key,
                "queue_count": queues,
                "cycle_seconds": cycle_seconds,
                "cycles_done": cycles_done,
                "max_cycles": max_cycles,
                "running": max_cycles is None or cycles_done < max_cycles,
                "empty_at": empty_at,
                "produced": produced,
                # Inputs that stop the recipe (stock below one cycle), for "parado: falta X".
                "missing": [
                    foxhole_data.resource_display_name(io["resource"], lang)
                    for io in inputs
                    if stock.get(io["resource"], 0) < foxhole_data.recipe_io_qty(io)
                ],
                "missing_keys": [
                    io["resource"] for io in inputs if stock.get(io["resource"], 0) < foxhole_data.recipe_io_qty(io)
                ],
            }
        )

    return {
        "logged": logged,
        "projected": {k: max(0.0, v) for k, v in stock.items()},
        "last_logged_at": last_logged_at,
        "elapsed_seconds": int(elapsed),
        "slots": slots,
    }


def facility_dashboard(db, facility_id: int, now: datetime, catalog_lang: str = "pt-BR") -> dict:
    """Everything the Dashboard tab and the Discord webhook show: each
    building projected, plus the facility's Metas against the projected
    total. Shared so the two never disagree."""
    from app import crud  # crud doesn't import this module, but keep services import-light

    resources = crud.resources_for_facility(db, facility_id)
    unlimited = crud.unlimited_resource_keys(resources)
    type_defs = foxhole_data.get_building_type_defs()

    buildings = []
    logged_total: dict[str, float] = {}
    projected_total: dict[str, float] = {}
    for building, entries in crud.get_current_stock_for_facility(db, facility_id).items():
        p = project_building(building, entries, now, unlimited, catalog_lang)
        for key, qty in p["logged"].items():
            logged_total[key] = logged_total.get(key, 0) + qty
        for key, qty in p["projected"].items():
            projected_total[key] = projected_total.get(key, 0) + qty
        buildings.append(
            {
                "id": building.id,
                "name": building.name,
                "building_type_key": building.building_type_key,
                "location": building.location,
                "storage": bool(type_defs.get(building.building_type_key, {}).get("storage")),
                **p,
            }
        )

    targets = []
    by_id = {r.id: r for r in resources}
    for resource_id, target in crud.get_facility_targets(db, facility_id).items():
        r = by_id.get(resource_id)
        if not r or not r.resource_def_key or r.resource_def_key in unlimited:
            continue
        targets.append(
            {
                "resource_def_key": r.resource_def_key,
                "name": crud.resolve_resource_name(r, catalog_lang),
                "target": target,
                "logged": logged_total.get(r.resource_def_key, 0),
                "projected": projected_total.get(r.resource_def_key, 0),
            }
        )
    return {"now": now, "buildings": buildings, "targets": targets}
