from datetime import datetime, timedelta

from app.services import foxhole_data


def estimate_production(building_type_key: str, recipe_key: str, queue_count: int, now: datetime) -> dict | None:
    """Rough production estimate: assumes `queue_count` concurrent orders of the
    same recipe all started around `now`, so they all finish ~recipe.time_seconds
    later. This is intentionally not a precise, server-synced countdown — it's a
    ballpark figure the user enters/refreshes by hand (see recipe data notes).
    """
    if queue_count <= 0:
        return None

    recipe = foxhole_data.get_recipe(building_type_key, recipe_key)
    if not recipe:
        return None

    eta = now + timedelta(seconds=recipe["time_seconds"])

    outputs = [
        {
            "resource": io["resource"],
            "name": foxhole_data.resource_display_name(io["resource"]),
            "qty": io.get("qty", 1) * queue_count,
        }
        for io in recipe["outputs"]
    ]
    inputs = [
        {
            "resource": io["resource"],
            "name": foxhole_data.resource_display_name(io["resource"]),
            "qty": io.get("qty", 1) * queue_count,
        }
        for io in recipe["inputs"]
        if "resource" in io
    ]

    return {
        "recipe_key": recipe_key,
        "module": recipe.get("module"),
        "queue_count": queue_count,
        "time_seconds": recipe["time_seconds"],
        "eta": eta,
        "outputs": outputs,
        "inputs": inputs,
    }
