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

import re
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
    before = max(0, int(getattr(order, "done_before", 0) or 0))

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
                # Made so far, including what was already in the output slot
                # when it was logged (done_before, in output units).
                "done": per * done + before,
                "total": None if total is None else per * total + before,
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
        "done_before": before,
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


def recipe_keys(building_type_key: str) -> set[str]:
    """Every item a building's recipes use or make — what an order panel can show."""
    building_type = foxhole_data.get_building_type(building_type_key) or {}
    return {io["resource"] for r in building_type.get("recipes", []) for io in r["inputs"] + r["outputs"] if io.get("resource")}


def guess_from_print(building_type_key: str, items: list[dict], allowed_recipes: set[str] | None = None) -> dict:
    """From the items found in an order panel screenshot, the recipe it shows,
    the loaded inputs and the output count (= already made). Only a pre-fill.

    The panel reads inputs → output, left to right, so the output must sit
    right of every input found. Look-alike icons (Assembly Materials I-V,
    150/300mm) tie in the detector: a slot also counts as its tied rival.
    Most items explained wins; a recipe with an input missing loses a point."""
    building_type = foxhole_data.get_building_type(building_type_key) or {}
    found: dict[str, dict] = {}
    for i in items:
        if i.get("resource_def_key"):
            found.setdefault(i["resource_def_key"], i)
    for i in items:
        if i.get("ambiguous") and i.get("rival_key"):
            found.setdefault(i["rival_key"], i)
    # Tiers of one item (Assembly Materials I-V…) differ only by a small
    # badge, and a learned exemplar can pick the wrong tier with confidence:
    # a tier the recipe needs also matches a sibling tier that was found.
    def family(key: str) -> str:
        return re.sub(r"_\d+$", "", key)

    def lookup(key: str):
        if key in found:
            return found[key], False
        sib = next((v for k, v in found.items() if k != key and family(k) == family(key) and family(k) != k), None)
        return sib, sib is not None

    best, best_score = None, 0
    for recipe in building_type.get("recipes", []):
        if allowed_recipes is not None and recipe["key"] not in allowed_recipes:
            continue
        outs = [io["resource"] for io in recipe["outputs"] if io.get("resource")]
        ins = [io["resource"] for io in solid_inputs(recipe)]
        out_items = [i for i in (lookup(k)[0] for k in outs) if i]
        if not out_items:
            continue
        in_items = [i for i in (lookup(k)[0] for k in ins) if i]
        if any(i is o for i in in_items for o in out_items):
            continue
        if in_items and min(o["box_x"] for o in out_items) <= max(i["box_x"] for i in in_items):
            continue
        score = 2 * len(in_items) + len(out_items) - (len(ins) - len(in_items))
        if score > best_score:
            best, best_score = recipe, score
    if not best:
        return {"recipe_key": None, "inputs": {}, "done_before": None, "unsure": False}
    inputs = {}
    unsure = False
    for io in solid_inputs(best):
        item, swapped = lookup(io["resource"])
        unsure = unsure or swapped or bool(item and item.get("ambiguous"))
        if item and item.get("quantity_guess"):
            inputs[io["resource"]] = item["quantity_guess"]
    out_key = next(io["resource"] for io in best["outputs"] if io.get("resource"))
    out_item, swapped = lookup(out_key)
    unsure = unsure or swapped or bool(out_item and out_item.get("ambiguous"))
    return {
        "recipe_key": best["key"],
        "inputs": inputs,
        "done_before": out_item.get("quantity_guess") if out_item else None,
        "unsure": unsure,
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
    """Already made in private queues per resource (not yet released to the
    public stockpile) — shown next to the Metas, never added to them: a Meta
    only counts what's in a building's public stock or a station."""
    totals: dict[str, float] = {}
    for o in orders:
        if o["status"] == "released":
            continue
        for out in o["outputs"]:
            qty = out["done"]
            if qty:
                totals[out["resource"]] = totals.get(out["resource"], 0) + qty
    return totals

