"""Fills `codename` in data/foxhole/resources.json — the game's internal item
name (e.g. "MaintenanceSupplies"), which is what the map save stores for a
pinned stockpile's items. Without it, an import from the save
(services/save_reader.py) couldn't tell which catalog resource a line is.

Source: the datamined item catalog published by the FIR project
(github.com/GICodeWarrior/fir, foxhole/<war>/catalog.json — CodeName,
DisplayName, Icon per item, extracted from the game files). Matched by English
display name first, then by icon filename (most of our icons came from the
same game textures). Anything ambiguous or missing is reported and left
without a codename — the import UI lets the user pick the resource for an
unknown codename and remembers it (codename_aliases table), so a gap here
never blocks an import.

Run again after a game update adds items (bump FIR_WAR if FIR publishes a
newer folder):

    .venv/Scripts/python.exe scripts/map_resource_codenames.py
"""

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESOURCES_JSON = ROOT / "data" / "foxhole" / "resources.json"

FIR_WAR = "airborne-63"
CATALOG_URL = f"https://raw.githubusercontent.com/GICodeWarrior/fir/main/foxhole/{FIR_WAR}/catalog.json"

# Checked by hand where name/icon matching is ambiguous. "RPG" matches both
# the ammo (RpgAmmo) and the Warden launcher (RpgW) — this catalog entry is
# the ammo.
OVERRIDES = {
    "rpg_ammo": "RpgAmmo",
}


def _icon_stem(path: str) -> str:
    return path.split("/")[-1].split(".")[0].lower()


def main() -> None:
    with urllib.request.urlopen(CATALOG_URL, timeout=30) as resp:
        catalog = json.load(resp)

    by_name: dict[str, set] = {}
    by_icon: dict[str, set] = {}
    for item in catalog:
        for name in (item.get("DisplayName"), item.get("ChassisName")):
            if name:
                by_name.setdefault(name.lower(), set()).add(item["CodeName"])
        if item.get("Icon"):
            by_icon.setdefault(_icon_stem(item["Icon"]), set()).add(item["CodeName"])

    resources = json.loads(RESOURCES_JSON.read_text(encoding="utf-8"))
    missing = []
    for key, res in resources.items():
        if key in OVERRIDES:
            res["codename"] = OVERRIDES[key]
            continue
        codes = by_name.get(res["name"]["en"].lower()) or by_icon.get(_icon_stem(res.get("icon", ""))) or set()
        if len(codes) == 1:
            res["codename"] = next(iter(codes))
        else:
            res.pop("codename", None)
            missing.append(f"{key} ({res['name']['en']}): {sorted(codes) or 'not in catalog'}")

    RESOURCES_JSON.write_text(json.dumps(resources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"codename set on {len(resources) - len(missing)}/{len(resources)} resources")
    for line in missing:
        print("  unmapped:", line)


if __name__ == "__main__":
    main()
