"""Downloads icon PNGs from the foxholetools/assets GitHub repo (Git LFS-backed)
into web/assets/foxhole/{items,structures}/, and patches data/foxhole/*.json
with the matched icon paths.

Uses the GitHub LFS batch API directly (no git-lfs checkout needed): each PNG
is stored as an LFS pointer text file at the normal raw URL, which is resolved
to a real (pre-signed, time-limited) download URL via a batch API call.

Run once: python scripts/download_foxhole_icons.py
"""
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_ASSETS = ROOT / "web" / "assets" / "foxhole"
DATA_DIR = ROOT / "data" / "foxhole"

REPO_RAW_BASE = "https://raw.githubusercontent.com/foxholetools/assets/main"
LFS_BATCH_URL = "https://github.com/foxholetools/assets.git/info/lfs/objects/batch"

# resource_key -> "ItemIcons/<file>.png"
RESOURCE_ICON_FILES = {
    "coal": "ItemIcons/CoalIcon.png",
    "sulfur": "ItemIcons/SulfurIcon.png",
    "water": "ItemIcons/WaterIcon.png",
    "salvage": "ItemIcons/SalvageIcon.png",
    "components": "ItemIcons/ComponentsIcon.png",
    "coke": "ItemIcons/CokeIcon.png",
    "maintenance_supplies": "ItemIcons/MaintenanceSuppliesIcon.png",
    "barbed_wire": "ItemIcons/BarbedWireMaterialItemIcon.png",
    "metal_beam": "ItemIcons/MetalBeamMaterialItemIcon.png",
    "sandbag": "ItemIcons/SandbagMaterialItemIcon.png",
    "rare_materials": "ItemIcons/RareMaterialsIcon.png",
    "flame_ammo": "ItemIcons/FlameAmmoIcon.png",
    "rpg_ammo": "ItemIcons/RpgItemIcon.png",
    "construction_materials": "ItemIcons/BasicMaterialsIcon.png",
}

# building_type_key -> "StructureIcons/<file>.png"
# NOTE: this repo's filenames are the game's internal object names, which
# don't all line up with current wiki names 1:1 (e.g. Ammunition Factory used
# to be called "Small Arms Factory"). Only include entries here that were
# visually confirmed to match — see the script's printed confirmation step.
BUILDING_ICON_FILES = {
    "coal_refinery": "StructureIcons/FacilityRefinery2Icon.png",
    "metalworks_factory": "StructureIcons/MetalworksFactoryBase.png",
    "concrete_mixer": "StructureIcons/ConcreteMixerIcon.png",
    "ammunition_factory": "StructureIcons/FacilitySmallArmsFactoryIcon.png",
    "oil_refinery": "StructureIcons/OilRefineryMod2Icon.png",
}


def get_pointer(path: str) -> tuple[str, int]:
    url = f"{REPO_RAW_BASE}/UI/{path}"
    with urllib.request.urlopen(url) as r:
        text = r.read().decode("utf-8")
    lines = text.strip().split("\n")
    oid = lines[1].split(":")[1]
    size = int(lines[2].split(" ")[1])
    return oid, size


def batch_download_urls(objects: list[dict]) -> dict[str, str]:
    body = json.dumps(
        {
            "operation": "download",
            "transfers": ["basic"],
            "objects": [{"oid": o["oid"], "size": o["size"]} for o in objects],
        }
    ).encode()
    req = urllib.request.Request(
        LFS_BATCH_URL,
        data=body,
        headers={"Accept": "application/vnd.git-lfs+json", "Content-Type": "application/vnd.git-lfs+json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        result = json.load(r)
    return {obj["oid"]: obj["actions"]["download"]["href"] for obj in result["objects"]}


def download_all(file_map: dict[str, str], dest_subdir: str) -> dict[str, str]:
    """Returns {key: relative_web_path} for successfully downloaded files."""
    dest_dir = WEB_ASSETS / dest_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    objects = []
    for key, path in file_map.items():
        oid, size = get_pointer(path)
        objects.append({"key": key, "path": path, "oid": oid, "size": size})

    download_urls = batch_download_urls(objects)

    saved = {}
    for obj in objects:
        href = download_urls.get(obj["oid"])
        if not href:
            print(f"  ! no download URL for {obj['path']}")
            continue
        filename = obj["path"].split("/")[-1]
        dest_path = dest_dir / filename
        with urllib.request.urlopen(href) as r:
            content = r.read()
        dest_path.write_bytes(content)
        actual_size = len(content)
        ok = actual_size == obj["size"]
        print(f"  {'OK ' if ok else 'SIZE MISMATCH'} {obj['path']} -> {dest_path.relative_to(WEB_ASSETS.parent.parent)} ({actual_size} bytes)")
        if ok:
            saved[obj["key"]] = f"/assets/foxhole/{dest_subdir}/{filename}"
    return saved


def patch_resources_json(icon_paths: dict[str, str]) -> None:
    path = DATA_DIR / "resources.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, web_path in icon_paths.items():
        if key in data:
            data[key]["icon"] = web_path
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def patch_building_types_json(icon_paths: dict[str, str]) -> None:
    path = DATA_DIR / "building_types.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, web_path in icon_paths.items():
        if key in data:
            data[key]["icon"] = web_path
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("Downloading resource icons...")
    resource_icons = download_all(RESOURCE_ICON_FILES, "items")
    patch_resources_json(resource_icons)

    print("Downloading building icons...")
    building_icons = download_all(BUILDING_ICON_FILES, "structures")
    patch_building_types_json(building_icons)

    print(f"\n{len(resource_icons)} resource icons, {len(building_icons)} building icons saved and linked.")


if __name__ == "__main__":
    main()
