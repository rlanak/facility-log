import math
from datetime import datetime, timedelta

from app.services import foxhole_data


def estimate_production(
    building_type_key: str,
    recipe_key: str,
    queue_count: int,
    current_stock: dict[str, float],
    now: datetime,
    lang: str = "pt-BR",
) -> dict | None:
    """Estimates how long it'll take `queue_count` parallel production lines to
    burn through the *currently logged stock* of this recipe's inputs, and how
    much output that yields — not just one cycle. `current_stock` is the
    building's current qty per Foxhole resource key (from its stock entries).

    Whichever tracked input runs out first caps the number of full cycles
    (a recipe needs its full input amount each cycle, no partial cycles).
    This is a ballpark figure the user enters/refreshes by hand, not a
    precise/live countdown — see recipe data notes.
    """
    if queue_count <= 0:
        return None

    recipe = foxhole_data.get_recipe(building_type_key, recipe_key)
    if not recipe:
        return None

    tracked_inputs = [io for io in recipe["inputs"] if "resource" in io]
    if not tracked_inputs:
        return None

    cycles_per_input = [
        current_stock.get(io["resource"], 0) // io.get("qty", 1) for io in tracked_inputs
    ]
    total_cycles = int(min(cycles_per_input))

    rounds = math.ceil(total_cycles / queue_count) if total_cycles > 0 else 0
    total_time_seconds = rounds * recipe["time_seconds"]
    eta = now + timedelta(seconds=total_time_seconds)

    def items(io_list, qty_multiplier):
        return [
            {
                "resource": io["resource"],
                "name": foxhole_data.resource_display_name(io["resource"], lang),
                "qty": io.get("qty", 1) * qty_multiplier,
            }
            for io in io_list
        ]

    outputs = items(recipe["outputs"], total_cycles)
    inputs_consumed = items(tracked_inputs, total_cycles)
    leftovers = [
        {**item, "qty": current_stock.get(item["resource"], 0) - item["qty"]}
        for item in inputs_consumed
    ]

    return {
        "recipe_key": recipe_key,
        "module": recipe.get("module"),
        "queue_count": queue_count,
        "cycles": total_cycles,
        "time_seconds": total_time_seconds,
        "eta": eta,
        "outputs": outputs,
        "inputs_consumed": inputs_consumed,
        # Unmultiplied per-cycle requirement (inputs_consumed is total_cycles * qty,
        # which is all zero when total_cycles is 0 — callers need this one instead
        # to report how much is actually needed when stock can't sustain a cycle).
        "inputs_per_cycle": items(tracked_inputs, 1),
        "leftovers": leftovers,
    }


def estimate_building_slots(
    building_type_key: str,
    slots: list[dict],
    current_stock: dict[str, float],
    now: datetime,
    lang: str = "pt-BR",
) -> list[dict]:
    """One estimate per active production slot (a building can run several
    different recipes at once, up to its queue_slots total — see
    Building.production_slots). Each slot is estimated independently against
    the same current_stock snapshot: if two slots share an input, each one's
    numbers assume the other isn't also drawing on it, so combined they can
    overstate true runway. Matches the project's existing "ballpark, not a
    precise simulation" stance for production estimates.
    """
    estimates = []
    for slot in slots:
        estimate = estimate_production(
            building_type_key, slot["recipe_key"], slot["queue_count"], current_stock, now, lang
        )
        if estimate:
            estimates.append(estimate)
    return estimates
