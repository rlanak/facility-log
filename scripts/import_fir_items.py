"""Completes data/foxhole/resources.json with every inventory item of the game.

Source: the item catalog the FIR project extracts from the game files
(github.com/GICodeWarrior/fir, foxhole/<war>/catalog.json + icons/). Only
items with an ItemCategory (inventory items — not vehicles or structures)
and not Warden-only (hard rule: Colonial only). Items already in the catalog
(matched by `codename`) are kept as they are; new ones get the English name
for both languages (it's the name used in game/Discord; the player can set a
nickname), `farmable` only for raw ores (FARMABLE) and their icon. Every item also gets its
`category`, used to group the item search.

Re-run when FIR publishes a newer war folder (update FIR_WAR).
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOURCES_JSON = ROOT / "data" / "foxhole" / "resources.json"
ICONS_DIR = ROOT / "web" / "assets" / "foxhole" / "items"

FIR_WAR = "airborne-63"
FIR_BASE = f"https://raw.githubusercontent.com/GICodeWarrior/fir/main/foxhole/{FIR_WAR}"

CATEGORIES = {
    "EItemCategory::SmallArms": "small_arms",
    "EItemCategory::HeavyArms": "heavy_arms",
    "EItemCategory::HeavyAmmo": "heavy_ammo",
    "EItemCategory::Utility": "utility",
    "EItemCategory::Supplies": "supplies",
    "EItemCategory::Medical": "medical",
    "EItemCategory::Uniforms": "uniforms",
    "EItemCategory::Parts": "parts",
}

# Raw resources mined in the world — the rest is produced (or picked up).
FARMABLE = {"Iron", "Copper", "Aluminum"}


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read()


def make_key(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.lower().replace("'", "")).strip("_") or "item"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}_{n}", n + 1
    return key


def main() -> int:
    catalog = json.loads(fetch(f"{FIR_BASE}/catalog.json"))
    resources = json.loads(RESOURCES_JSON.read_text(encoding="utf-8"))
    by_codename = {d.get("codename"): k for k, d in resources.items() if d.get("codename")}

    added = categorized = 0
    for item in catalog:
        category = CATEGORIES.get(item.get("ItemCategory"))
        code = item.get("CodeName")
        name = (item.get("DisplayName") or "").strip()
        if not category or not code or not name or item.get("FactionVariant") == "EFactionId::Wardens":
            continue
        key = by_codename.get(code)
        if key:
            if resources[key].get("category") != category:
                resources[key]["category"] = category
                categorized += 1
            continue
        icon_file = f"{code}.png"
        icon_path = ICONS_DIR / icon_file
        if not icon_path.exists():
            try:
                icon_path.write_bytes(fetch(f"{FIR_BASE}/icons/{icon_file}"))
            except Exception as exc:  # noqa: BLE001 — an item without icon is still useful
                print(f"  no icon for {code}: {exc}")
                icon_file = None
        key = make_key(name, set(resources))
        resources[key] = {
            "name": {"en": name, "pt": name},
            "farmable": code in FARMABLE,
            "icon": f"/assets/foxhole/items/{icon_file}" if icon_file else None,
            "codename": code,
            "category": category,
        }
        by_codename[code] = key
        added += 1
        print(f"+ {key}: {name}")

    RESOURCES_JSON.write_text(json.dumps(resources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{added} added, {categorized} categorized, {len(resources)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
