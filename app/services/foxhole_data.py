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


def resource_display_name(resource_key: str) -> str:
    res_def = get_resource_def(resource_key)
    return res_def["name"]["en"] if res_def else resource_key
