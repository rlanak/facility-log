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
    carries the real queue_count along so time estimates can use the
    player's actual parallelism. queue_count is the recipe's queues summed
    over every slot and building running it (two Ammunition Factories with
    2 queues of 3C each = 4 queues) — it used to be only the first slot's."""
    queues: dict[tuple[str, str], int] = {}
    result: dict[str, dict] = {}
    for building in buildings:
        if not building.building_type_key or not building.production_slots:
            continue
        for slot in building.production_slots:
            recipe = foxhole_data.get_recipe(building.building_type_key, slot["recipe_key"])
            if not recipe:
                continue
            node = (building.building_type_key, recipe["key"])
            queues[node] = queues.get(node, 0) + slot["queue_count"]
            for o in recipe["outputs"]:
                key = o.get("resource")
                if key and key not in result:
                    result[key] = {"building_type_key": building.building_type_key, "recipe": recipe}
    for entry in result.values():
        entry["queue_count"] = queues[(entry["building_type_key"], entry["recipe"]["key"])]
    return result


def resolve_requirements(
    targets: list[tuple[str, float]],
    stock: dict[str, float],
    preferred_recipes: dict,
    farmable_keys: set = frozenset(),
    imported_keys: set = frozenset(),
    unlimited_keys: set = frozenset(),
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
        # Unlimited (e.g. Water): always available, nothing to produce or farm.
        if needed <= 1e-9 or resource_key in unlimited_keys:
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
        out_qty = next(
            (foxhole_data.recipe_io_qty(o) for o in recipe["outputs"] if o.get("resource") == resource_key), None
        )
        if not out_qty:
            farm[resource_key] = farm.get(resource_key, 0) + deficit
            return
        cycles = math.ceil(deficit / out_qty)
        prod_key = (bt_key, recipe["key"])
        production[prod_key] = production.get(prod_key, 0) + cycles
        for io in recipe["inputs"]:
            if "resource" not in io:
                continue
            resolve(io["resource"], foxhole_data.recipe_io_qty(io) * cycles, depth + 1)

    for resource_key, deficit in targets:
        resolve(resource_key, deficit, 0)

    return {"production": production, "farm": farm, "imports": imports}


# A facility building runs up to 5 production queues at once, and that's
# how the regiment normally runs them — the reference estimate (the author,
# 02/11/2026: "o mais importante é ver o tempo com as 5").
FULL_QUEUES = 5


def compute_production_time(production: dict, preferred_recipes: dict) -> dict:
    """Wall-clock time to run every cycle in `production` (the
    resolve_requirements() result), twice: with the queues the facility has
    configured right now ("current") and with every building at its full 5
    queues ("full", the reference number).

    Per node (building+recipe): time = ceil(cycles / queues) × one cycle's
    time. A node nobody is producing yet has no current queues — it counts
    as 5 in both estimates (the report says it's an estimate). A node
    already running more than 5 (several buildings) keeps its real count in
    the full estimate too.

    Whole chain: production is pipelined — a recipe starts as soon as its
    inputs' first cycle is out, it doesn't wait for the whole input batch
    (the old model summed the chain, so "10h of rockets + 2h of Cmat" came
    out as 12h when it really takes ~10h). So a node finishes at
      max(first input out + its own run time,
          last input out + one of its own cycles)
    and the total is the latest finish. `critical_path` follows the inputs
    that set each finish, from the first input to the final product.

    Returns {"nodes": {node: {configured, cycle_seconds, current: {...},
    full: {...}}}, "current": {total_seconds, critical_path}, "full": {...},
    "has_current": bool} — has_current says whether any node runs with
    configured queues other than 5 (only then the current estimate differs).
    """
    configured_by_node = {
        (entry["building_type_key"], entry["recipe"]["key"]): entry["queue_count"] for entry in preferred_recipes.values()
    }

    key_to_node: dict[str, tuple[str, str]] = {}
    for bt_key, recipe_key in production:
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        for o in recipe["outputs"]:
            if o.get("resource"):
                key_to_node[o["resource"]] = (bt_key, recipe_key)

    def run(cycles: float, queue_count: int, cycle_seconds: int) -> dict:
        rounds = math.ceil(cycles / queue_count)
        return {"queue_count": queue_count, "rounds": rounds, "seconds": rounds * cycle_seconds}

    nodes: dict[tuple[str, str], dict] = {}
    for node, cycles in production.items():
        bt_key, recipe_key = node
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        configured = configured_by_node.get(node)
        cycle_seconds = recipe["time_seconds"]
        nodes[node] = {
            "configured": configured,
            "cycle_seconds": cycle_seconds,
            "current": run(cycles, configured or FULL_QUEUES, cycle_seconds),
            "full": run(cycles, max(configured or 0, FULL_QUEUES), cycle_seconds),
        }

    def chain(mode: str) -> dict:
        # node -> (first output at, finish at, path to the finish)
        memo: dict[tuple[str, str], tuple[float, float, list]] = {}

        def visit(node: tuple[str, str], visiting: frozenset) -> tuple[float, float, list]:
            if node in memo:
                return memo[node]
            if node in visiting:
                return 0, 0, []  # defensive: catalog shouldn't have recipe cycles
            bt_key, recipe_key = node
            recipe = foxhole_data.get_recipe(bt_key, recipe_key)
            info = nodes[node]
            first_in, last_in, path_in = 0.0, 0.0, []
            for io in recipe["inputs"]:
                child = key_to_node.get(io.get("resource"))
                if child:
                    c_first, c_finish, c_path = visit(child, visiting | {node})
                    first_in = max(first_in, c_first)
                    if c_finish > last_in:
                        last_in, path_in = c_finish, c_path
            own = info[mode]["seconds"]
            finish = max(first_in + own, last_in + info["cycle_seconds"])
            memo[node] = (first_in + info["cycle_seconds"], finish, path_in + [node])
            return memo[node]

        finish, path = max(((visit(n, frozenset())[1], visit(n, frozenset())[2]) for n in production), default=(0, []))
        return {"total_seconds": finish, "critical_path": path}

    return {
        "nodes": nodes,
        "current": chain("current"),
        "full": chain("full"),
        "has_current": any(n["configured"] and n["configured"] < FULL_QUEUES for n in nodes.values()),
    }
