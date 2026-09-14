"""Recursive "how do I hit this Meta" resolver: given a shortfall on some
resource, walks the Foxhole recipe graph backwards (output -> inputs) to
figure out how many production cycles of what, and how much raw material,
are needed — netting out whatever's already in stock at every step along the
way, not just at the top level.

Deliberately NOT modeled (per the author): output already in progress isn't
credited against the requirement (only *stock*, i.e. already-logged
quantities, nets out) — crediting active production would need matching
cycle timing against the target, which is a different, bigger problem. Also
doesn't know about Liquid Transfer Stations moving liquid between buildings.
"""

import math

from app.services import foxhole_data

MAX_DEPTH = 25


def _all_recipes():
    for bt_key, bt in foxhole_data.get_building_type_defs().items():
        for recipe in bt["recipes"]:
            yield bt_key, recipe


def _find_recipe_for_output(resource_key: str, preferred: dict) -> tuple[str, dict] | None:
    if resource_key in preferred:
        return preferred[resource_key]
    candidates = []
    for bt_key, recipe in _all_recipes():
        if any(o.get("resource") == resource_key for o in recipe["outputs"]):
            candidates.append((bt_key, recipe))
    if not candidates:
        return None
    # Prefer a Base-module recipe (no upgrade prerequisite) as the generic
    # default when the facility isn't already producing this resource
    # anywhere — least assumptions about what the player has unlocked.
    for bt_key, recipe in candidates:
        if recipe.get("module") in (None, "Base"):
            return (bt_key, recipe)
    return candidates[0]


def active_recipes_by_output(buildings) -> dict[str, tuple[str, dict]]:
    """resource_key -> (building_type_key, recipe) for whichever recipe the
    facility already has actively configured in production to make it —
    disambiguates resources more than one recipe can produce by preferring
    what the player actually set up over a generic guess."""
    result: dict[str, tuple[str, dict]] = {}
    for building in buildings:
        if not building.building_type_key or not building.production_slots:
            continue
        for slot in building.production_slots:
            recipe = foxhole_data.get_recipe(building.building_type_key, slot["recipe_key"])
            if not recipe:
                continue
            for o in recipe["outputs"]:
                key = o.get("resource")
                if key and key not in result:
                    result[key] = (building.building_type_key, recipe)
    return result


def resolve_requirements(
    targets: list[tuple[str, float]], stock: dict[str, float], preferred_recipes: dict
) -> dict:
    """targets: [(resource_key, deficit_qty), ...] to resolve, top to bottom.
    stock: current stock by Foxhole resource key — a shared pool that gets
    consumed as targets are resolved, so the same stock isn't credited
    toward two different Metas. Mutated in place.

    Returns {"production": {(building_type_key, recipe_key): cycles},
             "farm": {resource_key: qty}} — farm holds whatever has no known
    recipe (raw/gathered resources, or unmapped catalog gaps).
    """
    production: dict[tuple[str, str], float] = {}
    farm: dict[str, float] = {}

    def resolve(resource_key: str, needed: float, depth: int) -> None:
        if needed <= 1e-9:
            return
        have = stock.get(resource_key, 0)
        used = min(have, needed)
        stock[resource_key] = have - used
        deficit = needed - used
        if deficit <= 1e-9:
            return
        if depth >= MAX_DEPTH:
            farm[resource_key] = farm.get(resource_key, 0) + deficit
            return
        recipe_info = _find_recipe_for_output(resource_key, preferred_recipes)
        if not recipe_info:
            farm[resource_key] = farm.get(resource_key, 0) + deficit
            return
        bt_key, recipe = recipe_info
        out_qty = next((o["qty"] for o in recipe["outputs"] if o.get("resource") == resource_key), None)
        if not out_qty:
            farm[resource_key] = farm.get(resource_key, 0) + deficit
            return
        cycles = math.ceil(deficit / out_qty)
        prod_key = (bt_key, recipe["key"])
        production[prod_key] = production.get(prod_key, 0) + cycles
        for io in recipe["inputs"]:
            if "resource" not in io:
                continue
            resolve(io["resource"], io["qty"] * cycles, depth + 1)

    for resource_key, deficit in targets:
        resolve(resource_key, deficit, 0)

    return {"production": production, "farm": farm}
