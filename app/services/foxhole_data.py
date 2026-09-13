import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "foxhole"


@lru_cache(maxsize=1)
def get_resource_defs() -> dict:
    return json.loads((DATA_DIR / "resources.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def get_building_type_defs() -> dict:
    return json.loads((DATA_DIR / "building_types.json").read_text(encoding="utf-8"))


def get_resource_def(key: str) -> dict | None:
    return get_resource_defs().get(key)


def get_building_type(key: str) -> dict | None:
    return get_building_type_defs().get(key)


def get_recipe(building_type_key: str, recipe_key: str) -> dict | None:
    building_type = get_building_type(building_type_key)
    if not building_type:
        return None
    return next((r for r in building_type["recipes"] if r["key"] == recipe_key), None)


# Every building's liquid tank caps at 5000L regardless of building or liquid
# type (confirmed against the author's own screenshots) — only how many units fit
# in that cap varies, via each liquid's liters_per_unit ("galão") conversion.
LIQUID_TANK_CAPACITY_LITERS = 5000


def liquid_liters_per_unit(resource_key: str) -> float | None:
    res_def = get_resource_def(resource_key)
    if not res_def or not res_def.get("is_liquid"):
        return None
    return res_def.get("liters_per_unit")


def liquid_tank_max_units(resource_key: str) -> float | None:
    liters_per_unit = liquid_liters_per_unit(resource_key)
    if not liters_per_unit:
        return None
    return LIQUID_TANK_CAPACITY_LITERS / liters_per_unit


def active_liquid_keys(building_type_key: str, production_slots: list[dict]) -> list[str]:
    """Which liquids a building currently has a tank for — derived from the
    liquid resources used by whichever recipes are active in production, not
    a separate setting. Mirrors facilityDetail.js's activeLiquidKeys()."""
    active_recipe_keys = {slot["recipe_key"] for slot in production_slots}
    keys: list[str] = []
    for recipe in get_building_type(building_type_key)["recipes"] if get_building_type(building_type_key) else []:
        if recipe["key"] not in active_recipe_keys:
            continue
        for io in [*recipe["inputs"], *recipe["outputs"]]:
            key = io.get("resource")
            if key and liquid_liters_per_unit(key) and key not in keys:
                keys.append(key)
    return keys


LANG_CODES = {"en-US": "en", "pt-BR": "pt"}


def resource_display_name(resource_key: str, lang: str = "pt-BR") -> str:
    res_def = get_resource_def(resource_key)
    if not res_def:
        return resource_key
    names = res_def["name"]
    return names.get(LANG_CODES.get(lang, "pt")) or names["en"]


def building_display_name(building_type_key: str, lang: str = "pt-BR") -> str:
    building_type = get_building_type(building_type_key)
    if not building_type:
        return building_type_key
    if LANG_CODES.get(lang) == "en":
        return building_type["name_en"]
    return building_type.get("name_pt") or building_type["name_en"]
