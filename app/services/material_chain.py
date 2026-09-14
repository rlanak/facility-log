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
        entry = preferred[resource_key]
        return (entry["building_type_key"], entry["recipe"])
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


def active_recipes_by_output(buildings) -> dict[str, dict]:
    """resource_key -> {building_type_key, recipe, queue_count} for whichever
    recipe the facility already has actively configured in production to
    make it — disambiguates resources more than one recipe can produce by
    preferring what the player actually set up over a generic guess, and
    carries the actual queue_count along so time estimates can use the
    player's real parallelism instead of assuming a single queue."""
    result: dict[str, dict] = {}
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
                    result[key] = {
                        "building_type_key": building.building_type_key,
                        "recipe": recipe,
                        "queue_count": slot["queue_count"],
                    }
    return result


def resolve_requirements(
    targets: list[tuple[str, float]],
    stock: dict[str, float],
    preferred_recipes: dict,
    farmable_keys: set = frozenset(),
    imported_keys: set = frozenset(),
) -> dict:
    """targets: [(resource_key, deficit_qty), ...] to resolve, top to bottom.
    stock: current stock by Foxhole resource key — a shared pool that gets
    consumed as targets are resolved, so the same stock isn't credited
    toward two different Metas. Mutated in place.

    farmable_keys / imported_keys stop the recursion early even when a
    recipe for that resource exists: a resource the player farms (or
    imports from an ally/coalition) is reported as-is instead of being
    exploded into whatever recipe happens to also produce it — e.g.
    Components has a "recycle Damaged Components" recipe, but if it's
    marked farmable the player wants "go get more Components", not a
    recycling chain they're not actually running. `imported` wins over
    `farmable` when a resource is somehow marked both.

    Returns {"production": {(building_type_key, recipe_key): cycles},
             "farm": {resource_key: qty}, "imports": {resource_key: qty}}.
    "farm" also catches whatever has no known recipe at all (raw resources,
    or unmapped catalog gaps).
    """
    production: dict[tuple[str, str], float] = {}
    farm: dict[str, float] = {}
    imports: dict[str, float] = {}

    def resolve(resource_key: str, needed: float, depth: int) -> None:
        if needed <= 1e-9:
            return
        have = stock.get(resource_key, 0)
        used = min(have, needed)
        stock[resource_key] = have - used
        deficit = needed - used
        if deficit <= 1e-9:
            return
        if resource_key in imported_keys:
            imports[resource_key] = imports.get(resource_key, 0) + deficit
            return
        if resource_key in farmable_keys:
            farm[resource_key] = farm.get(resource_key, 0) + deficit
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

    return {"production": production, "farm": farm, "imports": imports}


def compute_production_time(production: dict, preferred_recipes: dict) -> dict:
    """Total wall-clock time to run every cycle in `production` (the
    resolve_requirements() result) — not the per-cycle/per-queue unit time,
    the whole thing. Each node's own duration divides its cycles across
    whatever queue_count is actually configured for it (1 if the player
    isn't already producing it anywhere, i.e. worst case serial). The
    overall total is the longest dependency chain (an input has to exist
    before its recipe can consume it), not a flat sum — independent chains
    are assumed to run in parallel in different buildings.

    Returns {"total_seconds": float, "any_assumed_single_queue": bool} —
    the second flags whether the estimate leaned on the "assume 1 queue"
    fallback anywhere, so callers can caveat the number appropriately.
    """
    queue_count_by_node = {
        (entry["building_type_key"], entry["recipe"]["key"]): entry["queue_count"] for entry in preferred_recipes.values()
    }

    key_to_node: dict[str, tuple[str, str]] = {}
    for bt_key, recipe_key in production:
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        for o in recipe["outputs"]:
            if o.get("resource"):
                key_to_node[o["resource"]] = (bt_key, recipe_key)

    any_assumed_single_queue = False
    durations: dict[tuple[str, str], float] = {}
    for node, cycles in production.items():
        bt_key, recipe_key = node
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        queue_count = queue_count_by_node.get(node)
        if not queue_count:
            queue_count = 1
            any_assumed_single_queue = True
        rounds = math.ceil(cycles / queue_count)
        durations[node] = rounds * recipe["time_seconds"]

    memo: dict[tuple[str, str], float] = {}

    def critical_path(node: tuple[str, str], visiting: frozenset) -> float:
        if node in memo:
            return memo[node]
        if node in visiting:
            return 0  # defensive: catalog shouldn't have recipe cycles, but don't hang if it did
        bt_key, recipe_key = node
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        child_max = 0.0
        for io in recipe["inputs"]:
            child_node = key_to_node.get(io.get("resource"))
            if child_node:
                child_max = max(child_max, critical_path(child_node, visiting | {node}))
        total = durations[node] + child_max
        memo[node] = total
        return total

    total_seconds = max((critical_path(node, frozenset()) for node in production), default=0)
    return {"total_seconds": total_seconds, "any_assumed_single_queue": any_assumed_single_queue}
