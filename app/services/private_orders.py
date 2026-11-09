"""Private ("Personal") production orders (09/11/2026 — the regiment queues
privately so finished items go straight to reserved MTSs instead of the
public stockpile).

How the game runs them (foxhole.wiki.gg, Facilities / Materials Factory):
- up to 5 orders run at once per building, public and private together;
  one running order per player per building;
- the player loads the inputs by hand (liquids still come from the tank);
- the output waits in the player's own slot and, if not retrieved, goes to
  the building's public stockpile 28 hours after the order completes.

So in the app a private order never draws on nor adds to the public stock
(the projection ignores it); it takes one of the building's queues, and
its output only counts once someone logs it where it was put (an MTS).

Math, from what the player logs (the order panel):
- cycles left = min over the loaded solid inputs of loaded ÷ per cycle;
  a cycle shown running (cycle_left_seconds > 0) already took its inputs,
  so it's one more on top;
- ready at = start + cycle_left + cycles × cycle time;
- done so far = finished cycles up to now (only complete ones).
"""

from datetime import datetime, timedelta, timezone

from app.services import foxhole_data

RELEASE_HOURS = 28


def _as_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def solid_inputs(recipe: dict) -> list[dict]:
    """The inputs a player loads into a private order (not liquids, not power)."""
    out = []
    for io in recipe["inputs"]:
        key = io.get("resource")
        if not key:
            continue
        rdef = foxhole_data.get_resource_def(key)
        if rdef and rdef.get("is_liquid"):
            continue
        out.append(io)
    return out


def compute(order, building, now: datetime, catalog_lang: str = "pt-BR") -> dict:
    recipe = foxhole_data.get_recipe(building.building_type_key, order.recipe_key) if building.building_type_key else None
    cycle_seconds = recipe["time_seconds"] if recipe else 0
    loaded = order.inputs
    inputs = []
    limits = []
    for io in solid_inputs(recipe) if recipe else []:
        per = foxhole_data.recipe_io_qty(io)
        qty = float(loaded.get(io["resource"], 0) or 0)
        cycles = int(qty // per) if per > 0 else 0
        limits.append((cycles, io["resource"]))
        inputs.append(
            {
                "resource": io["resource"],
                "name": foxhole_data.resource_display_name(io["resource"], catalog_lang),
                "loaded": qty,
                "per_cycle": per,
                "cycles": cycles,
            }
        )
    in_progress = 1 if order.cycle_left_seconds > 0 else 0
    from_inputs = min((c for c, _ in limits), default=None)
    total = None if from_inputs is None else from_inputs + in_progress
    # Which input ends it (only worth naming when they don't all end together).
    limiting = None
    if limits and len({c for c, _ in limits}) > 1:
        limiting = foxhole_data.resource_display_name(min(limits)[1], catalog_lang)

    started = _as_utc(order.started_at)
    elapsed = (now - started).total_seconds()
    done = 0
    t = elapsed
    if in_progress:
        if t >= order.cycle_left_seconds:
            done = 1
            t -= order.cycle_left_seconds
        else:
            t = -1
    if t >= 0 and cycle_seconds:
        done += int(t // cycle_seconds)
    if total is not None:
        done = min(done, total)

    ready_at = expires_at = None
    if total is not None:
        ready_at = started + timedelta(seconds=order.cycle_left_seconds + (total - in_progress) * cycle_seconds)
        expires_at = ready_at + timedelta(hours=RELEASE_HOURS)
    if ready_at is None or now < ready_at:
        status = "running"
    elif now < expires_at:
        status = "ready"
    else:
        status = "released"  # the game moved the output to the public stockpile

    outputs = []
    for io in recipe["outputs"] if recipe else []:
        if "resource" not in io:
            continue
        per = foxhole_data.recipe_io_qty(io)
        outputs.append(
            {
                "resource": io["resource"],
                "name": foxhole_data.resource_display_name(io["resource"], catalog_lang),
                "per_cycle": per,
                "done": per * done,
                "total": None if total is None else per * total,
            }
        )

    return {
        "id": order.id,
        "building_id": order.building_id,
        "owner_name": order.owner_name,
        "recipe_key": order.recipe_key,
        "recipe_found": recipe is not None,
        "inputs": inputs,
        "outputs": outputs,
        "cycle_seconds": cycle_seconds,
        "cycle_left_seconds": order.cycle_left_seconds,
        "total_cycles": total,
        "done_cycles": done,
        "remaining_cycles": None if total is None else max(0, total - done),
        "limiting": limiting,
        "started_at": started,
        "ready_at": ready_at,
        "expires_at": expires_at,
        "status": status,
        "created_by_name": order.created_by.name if order.created_by else None,
    }


def open_orders(db, building) -> list:
    from app import models

    return (
        db.query(models.PrivateOrder)
        .filter(models.PrivateOrder.building_id == building.id, models.PrivateOrder.closed_at.is_(None))
        .order_by(models.PrivateOrder.started_at)
        .all()
    )


def running_count(db, building, now: datetime) -> int:
    """Private orders still producing — each takes one of the building's queues."""
    return sum(1 for o in open_orders(db, building) if compute(o, building, now)["status"] == "running")


def for_facility(db, facility_id: int, now: datetime, catalog_lang: str = "pt-BR") -> list[dict]:
    from app import crud

    out = []
    for building in crud.get_buildings(db, facility_id):
        for order in open_orders(db, building):
            item = compute(order, building, now, catalog_lang)
            item["building_name"] = building.name
            item["building_location"] = building.location
            item["building_type_key"] = building.building_type_key
            out.append(item)
    out.sort(key=lambda o: (o["ready_at"] is None, o["ready_at"] or o["started_at"]))
    return out


def incoming(orders: list[dict]) -> dict[str, float]:
    """Output on its way per resource (orders not yet released to the public
    stockpile) — shown next to the Metas, never added to them."""
    totals: dict[str, float] = {}
    for o in orders:
        if o["status"] == "released":
            continue
        for out in o["outputs"]:
            qty = out["total"] if out["total"] is not None else out["done"]
            if qty:
                totals[out["resource"]] = totals.get(out["resource"], 0) + qty
    return totals

