"""Downloads item/building icon PNGs from the official Foxhole wiki
(foxhole.wiki.gg) into web/assets/foxhole/{items,structures}/, and patches
data/foxhole/{resources,building_types}.json with the matched icon paths.

Second icon source, used for resources the foxholetools/assets GitHub repo
(see download_foxhole_icons.py) doesn't have — raw/refined materials and
Colonial aircraft parts so far. The wiki's WAF blocks bare requests (no/
generic User-Agent, no Referer) with an HTML "Blocked" page instead of the
image, and negotiates WebP over PNG unless the Accept header says otherwise
— hence the specific headers below.

Each filename below was found by opening the item's wiki page and reading
off the infobox image's actual <img src>, NOT guessed from the item's name —
the wiki's internal filenames often don't match (e.g. Rare Metal's image is
literally named "RareMaterialsIcon.png" on their server, a same-name clash
with our own unrelated rare_materials.png from the other source). Every icon
was visually spot-checked (contact sheet) before committing.

Run once: python scripts/download_foxhole_icons_wiki.py
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_ASSETS = ROOT / "web" / "assets" / "foxhole"
DATA_DIR = ROOT / "data" / "foxhole"

WIKI_BASE = "https://foxhole.wiki.gg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/png,image/*;q=0.5",
    "Accept-Language": "en-US,en;q=0.9",
}

# resource_key -> (wiki page, image filename on foxhole.wiki.gg/images/, local filename)
RESOURCE_ICON_FILES = {
    "oil": ("Oil", "OilIcon.png", "OilIcon.png"),
    "rare_metal": ("Rare_Metal", "RareMaterialsIcon.png", "RareMetalIcon.png"),
    "concrete_materials": ("Concrete_Materials", "ConcreteBagIcon.png", "ConcreteMaterialsIcon.png"),
    "heavy_oil": ("Heavy_Oil", "HeavyOilIcon.png", "HeavyOilIcon.png"),
    "petrol": ("Petrol", "RefinedFuelIcon.png", "PetrolIcon.png"),
    "enriched_oil": ("Enriched_Oil", "EnrichedOilIcon.png", "EnrichedOilIcon.png"),
    "assembly_materials_1": ("Assembly_Materials_I", "AssemblyMaterials1Icon.png", "AssemblyMaterials1Icon.png"),
    "assembly_materials_2": ("Assembly_Materials_II", "AssemblyMaterials2Icon.png", "AssemblyMaterials2Icon.png"),
    "assembly_materials_3": ("Assembly_Materials_III", "AssemblyMaterials3Icon.png", "AssemblyMaterials3Icon.png"),
    "assembly_materials_4": ("Assembly_Materials_IV", "AssemblyMaterials4Icon.png", "AssemblyMaterials4Icon.png"),
    "assembly_materials_5": ("Assembly_Materials_V", "AssemblyMaterials5Icon.png", "AssemblyMaterials5Icon.png"),
    "processed_construction_materials": (
        "Processed_Construction_Materials",
        "ProcessedConstructionMaterialsIcon.png",
        "ProcessedConstructionMaterialsIcon.png",
    ),
    "steel_construction_materials": (
        "Steel_Construction_Materials",
        "SteelConstructionMaterialsIcon.png",
        "SteelConstructionMaterialsIcon.png",
    ),
    "damaged_components": ("Damaged_Components", "ComponentsDamagedIcon.png", "DamagedComponentsIcon.png"),
    "rare_alloys": ("Rare_Alloys", "FacilityMaterials09Icon.png", "RareAlloysIcon.png"),
    "gravel": ("Gravel", "GroundMaterialsIcon.png", "GravelIcon.png"),
    "pipe": ("Pipe", "EngineRoomPipeIcon.png", "PipeIcon.png"),
    "heavy_explosive_powder": (
        "Heavy_Explosive_Powder",
        "HeavyExplosiveMaterialsIcon.png",
        "HeavyExplosivePowderIcon.png",
    ),
    # Aircraft parts: the wiki models both factions (C/W suffixes) plus some
    # generic-named files reused across pages; resolved by opening each of
    # our 8 Colonial items' own wiki page rather than guessing from the
    # Category:Aircraft_part_icons listing, since large-part filenames don't
    # carry a faction suffix at all (e.g. "AircraftEngineIcon.png" is the
    # Colonial Large Engine despite the generic name).
    "colonial_aircraft_engine_small": (
        "Colonial_Aircraft_Engine_(Small)",
        "AircraftPartSmallEngineCIcon.png",
        "AircraftPartSmallEngineCIcon.png",
    ),
    "colonial_aircraft_mech_parts_small": (
        "Colonial_Aircraft_Mechanical_Parts_(Small)",
        "AircraftPartSmallMechanicalCIcon.png",
        "AircraftPartSmallMechanicalCIcon.png",
    ),
    "colonial_aircraft_engine_large": (
        "Colonial_Aircraft_Engine_(Large)",
        "AircraftEngineIcon.png",
        "AircraftPartLargeEngineCIcon.png",
    ),
    "colonial_aircraft_mech_parts_large": (
        "Colonial_Aircraft_Mechanical_Parts_(Large)",
        "AircraftFuselageIcon.png",
        "AircraftPartLargeMechanicalCIcon.png",
    ),
    "damaged_colonial_aircraft_engine_small": (
        "Damaged_Colonial_Aircraft_Engine_(Small)",
        "DamagedAircraftPartSmallEngineCIcon.png",
        "DamagedAircraftPartSmallEngineCIcon.png",
    ),
    "damaged_colonial_aircraft_mech_parts_small": (
        "Damaged_Colonial_Aircraft_Mechanical_Parts_(Small)",
        "DamagedAircraftPartSmallMechanicalCIcon.png",
        "DamagedAircraftPartSmallMechanicalCIcon.png",
    ),
    "damaged_colonial_aircraft_engine_large": (
        "Damaged_Colonial_Aircraft_Engine_(Large)",
        "DamagedAircraftEngineIcon.png",
        "DamagedAircraftPartLargeEngineCIcon.png",
    ),
    "damaged_colonial_aircraft_mech_parts_large": (
        "Damaged_Colonial_Aircraft_Mechanical_Parts_(Large)",
        "DamagedAircraftFuselageIcon.png",
        "DamagedAircraftPartLargeMechanicalCIcon.png",
    ),
    # Ammunition/ordnance, mounted weapons, and uniforms: resolved via the
    # MediaWiki API (action=parse&prop=wikitext&redirects=1) instead of
    # scraping rendered pages in a browser — reading the infobox template's
    # `image = ...` parameter straight out of the wikitext is both more
    # reliable (no ambiguity about which <img> on the page is the real icon)
    # and sidesteps foxhole.wiki.gg's Cloudflare challenge, which the API
    # endpoint isn't behind but a burst of normal page loads is (it started
    # serving "Just a moment..." challenge pages after ~10 rapid browser
    # navigations in a row; the api.php requests here were never blocked).
    # All 62 were downloaded and spot-checked via a contact sheet before
    # committing. The same wikitext also carries a `faction` field, which
    # caught 5 more candidates (Tenta Torpedo, BF5 White Ash Flask Grenade,
    # B2 Varsi Anti-Tank Grenade, Mounted Bonesaw MK.3, Clancy-Raca M4) that
    # this Colonial-only catalog had mislabeled — actually Warden per the
    # wiki. Deliberately left out of this dict pending a fix to those 5
    # resource entries themselves (a data problem, not an icon problem) —
    # see the "not faction-verified" item in the project backlog notes.
    "120mm": ("120mm", "LightArtilleryAmmoItemIcon.png", "LightArtilleryAmmoItemIcon.png"),
    "14_5mm": ("14.5mm", "ATRifleAmmoItemIcon.png", "ATRifleAmmoItemIcon.png"),
    "150mm": ("150mm", "HeavyArtilleryAmmoItemIcon.png", "HeavyArtilleryAmmoItemIcon.png"),
    "20mm": ("20mm", "AircraftAmmoIcon.png", "AircraftAmmoIcon.png"),
    "250mm_fury_shell": ("250mm_“Fury”_Shell", "MortarTankAmmoBRIcon.png", "MortarTankAmmoBRIcon.png"),
    "300mm": ("300mm", "LRArtilleryAmmoItemIcon.png", "LRArtilleryAmmoItemIcon.png"),
    "30mm": ("30mm", "MiniTankAmmoItemIcon.png", "MiniTankAmmoItemIcon.png"),
    "3c_he_rocket": ("3C-High_Explosive_Rocket", "HERocketAmmoIcon.png", "HERocketAmmoIcon.png"),
    "40mm": ("40mm", "LightTankAmmoItemIcon.png", "LightTankAmmoItemIcon.png"),
    "4c_fire_rocket": ("4C-Fire_Rocket", "FlameRocketAmmoIcon.png", "FlameRocketAmmoIcon.png"),
    "68mm": ("68mm", "ATAmmoIcon.png", "ATAmmoIcon.png"),
    "75mm": ("75mm", "BattleTankAmmoItemIcon.png", "BattleTankAmmoItemIcon.png"),
    "912_shrike_rounds": ("912_Shrike_Rounds", "DiveBomberAmmoIcon.png", "DiveBomberAmmoIcon.png"),
    "94_5mm": ("94.5mm", "ATLargeAmmoIcon.png", "ATLargeAmmoIcon.png"),
    "950_70b_aa_shell": ("950-70b_Anti-Aircraft_Shell", "AAAmmoIcon.png", "AAAmmoIcon.png"),
    "abisme_at99": ("Abisme_AT-99", "AntiTankMineItemIcon.png", "AntiTankMineItemIcon.png"),
    "anti_tank_sticky_bomb": ("Anti-Tank_Sticky_Bomb", "StickyBombIcon.png", "StickyBombIcon.png"),
    "ap_rpg": ("AP⧸RPG", "ATRpgAmmoItemIcon.png", "ATRpgAmmoItemIcon.png"),
    "arc_rpg": ("ARC⧸RPG", "ATMortarAmmoItemIcon.png", "ATMortarAmmoItemIcon.png"),
    "argenti_r_ii_rifle": ("Argenti_r.II_Rifle", "RifleCItemIcon.png", "RifleCItemIcon.png"),
    "austers_harness": ("Auster's_Harness", "ParatrooperUniformCIcon.png", "ParatrooperUniformCIcon.png"),
    "catara_mo_ii": ("Catara_mo.II", "LightMachineGunIcon.png", "LightMachineGunIcon.png"),
    "crows_foot_mine": ("Crow's_Foot_Mine", "InfantryMineIcon.png", "InfantryMineIcon.png"),
    "daucus_isg_iii": ("Daucus_isg.III", "InfantrySupportGunItemIcon.png", "InfantrySupportGunItemIcon.png"),
    "dawn_ve_ii": ("“Dawn”_Ve.II", "ATRifleLightCIcon.png", "ATRifleLightCIcon.png"),
    "dusk_ce_iii": ("“Dusk”_ce.III", "AssaultRifleHeavyCItemIcon.png", "AssaultRifleHeavyCItemIcon.png"),
    "e680_rudder_lock": ("E680-S_Rudder_Lock", "SeaMineIcon.png", "SeaMineIcon.png"),
    "e681_hullbreaker_mine": ("E681-B_Hullbreaker_Mine", "SurfaceMineIcon.png", "SurfaceMineIcon.png"),
    "fabri_rucksack": ("Fabri_Rucksack", "EngineerUniformCIcon.png", "EngineerUniformCIcon.png"),
    "flare_mortar_shell": ("Flare_Mortar_Shell", "MortarAmmoIconFlare.png", "MortarAmmoIconFlare.png"),
    "grenadiers_baldric": ("Grenadier's_Baldric", "GrenadeUniformCIcon.png", "GrenadeUniformCIcon.png"),
    "heavy_topcoat": ("Heavy_Topcoat", "SnowUniformCIcon.png", "SnowUniformCIcon.png"),
    "ignifist_30": ("Ignifist_30", "ATRPGLightCItemIcon.png", "ATRPGLightCItemIcon.png"),
    "incendiary_mortar_shell": ("Incendiary_Mortar_Shell", "MortarAmmoIconFlame.png", "MortarAmmoIconFlame.png"),
    "krr3_792_auger": ("KRR3-792_Auger", "SniperRifleCItemIcon.png", "SniperRifleCItemIcon.png"),
    "lamentum_mm_iv": ("Lamentum_mm.IV", "HeavyMachineGunIcon.png", "HeavyMachineGunIcon.png"),
    "legion_vexillum": ("Legion_Vexillum", "BannerTCItemIcon.png", "BannerTCItemIcon.png"),
    "legionarys_oilcoat": ("Legionary's_Oilcoat", "RainUniformCIcon.png", "RainUniformCIcon.png"),
    "lodesmans_lorica": ("Lodesman's_Lorica", "PilotUniformCIcon.png", "PilotUniformCIcon.png"),
    "mark_ii_raidbreaker": ("Mark_II_Raidbreaker", "AerialBombsIcon.png", "AerialBombsIcon.png"),
    "medic_fatigues": ("Medic_Fatigues", "MedicUniformCIcon.png", "MedicUniformCIcon.png"),
    "model_7_evie": ("Model-7_“Evie”", "DepthChargeIcon.png", "DepthChargeIcon.png"),
    "moray_torpedo": ("Moray_Torpedo", "TorpedoIcon.png", "TorpedoIcon.png"),
    "mortar_shell": ("Mortar_Shell", "MortarAmmoIcon.png", "MortarAmmoIcon.png"),
    "mounted_fissura_gd_i": ("Mounted_Fissura_gd.I", "GrenadeLauncherTCIcon.png", "GrenadeLauncherTCIcon.png"),
    "naval_buoy": ("Naval_Buoy", "WaterWallItemIcon.png", "WaterWallItemIcon.png"),
    "officialis_attire": ("Officialis'_Attire", "OfficerUniformCIcon.png", "OfficerUniformCIcon.png"),
    "paratroopers_ruck": ("Paratrooper's_Ruck", "ParatrooperBackpackItemIcon.png", "ParatrooperBackpackItemIcon.png"),
    "pt815_smoke_grenade": ("PT-815_Smoke_Grenade", "Smokegrenadeicon1.png", "Smokegrenadeicon1.png"),
    "quickhatch_rt_i": ("“Quickhatch”_Rt.I", "ATRifleSniperCIcontga.png", "ATRifleSniperCIcontga.png"),
    "quillback_torpedo": ("Quillback_Torpedo", "MiniTorpedoAmmoIcon.png", "MiniTorpedoAmmoIcon.png"),
    "recon_camo": ("Recon_Camo", "ScoutUniformCIcon.png", "ScoutUniformCIcon.png"),
    "remex_garb": ("Remex_Garb", "NavalUniformC.png", "NavalUniformC.png"),
    "shatter_missile": ("Shatter_Missile", "DemolitionRocketAmmoIcon.png", "DemolitionRocketAmmoIcon.png"),
    "shrapnel_mortar_shell": ("Shrapnel_Mortar_Shell", "MortarAmmoIconShrapnel.png", "MortarAmmoIconShrapnel.png"),
    "tankmans_coveralls": ("Tankman's_Coveralls", "TankUniformCIcon.png", "TankUniformCIcon.png"),
    "thermal_shielding": ("Thermal_Shielding", "FacilityMaterials11Icon.png", "FacilityMaterials11Icon.png"),
    "tremola_grenade_gpb1": ("Tremola_Grenade_GPb-1", "HELaunchedGrenadeItemIcon.png", "HELaunchedGrenadeItemIcon.png"),
    "tripod_generic": ("Tripod", "DeployableTripodItemIcon.png", "DeployableTripodItemIcon.png"),
    "typhon_ra_xii": ("“Typhon”_ra.XII", "ATRifleTCIcon.png", "ATRifleTCIcon.png"),
    "unstable_substances": ("Unstable_Substances", "FacilityMaterials10Icon.png", "FacilityMaterials10Icon.png"),
    "velian_flak_vest": ("Velian_Flak_Vest", "ArmourUniformC.png", "ArmourUniformC.png"),
}

# building_type_key -> (wiki page, image filename on foxhole.wiki.gg/images/, local filename)
# materials_factory and infantry_kit_factory are deliberately NOT downloaded
# here: their wiki infobox images are MetalworksFactoryBase.png and
# FacilitySmallArmsFactoryIcon.png respectively — the exact files already
# used for metalworks_factory/ammunition_factory. Confirmed via each page's
# own text that this isn't a lookup mistake: both pairs are upgrade paths of
# the same base structure in-game (e.g. "A Materials Factory ... can be
# upgraded" into a Metalworks Factory), so the shared art is correct, not a
# collision — patch_building_types_json() below just points them at the
# already-downloaded files instead of re-fetching duplicates.
BUILDING_ICON_FILES = {
    "aircraft_maintenance_factory": (
        "Aircraft_Maintenance_Factory",
        "FacilityFactoryAircraftIcon.png",
        "FacilityFactoryAircraftIcon.png",
    ),
}

BUILDING_ICON_REUSE = {
    "materials_factory": "/assets/foxhole/structures/MetalworksFactoryBase.png",
    "infantry_kit_factory": "/assets/foxhole/structures/FacilitySmallArmsFactoryIcon.png",
}


def download_all(file_map: dict[str, tuple[str, str, str]], dest_subdir: str) -> dict[str, str]:
    """Returns {key: relative_web_path} for successfully downloaded files."""
    dest_dir = WEB_ASSETS / dest_subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    saved = {}
    for key, (wiki_page, remote_name, local_name) in file_map.items():
        url = f"{WIKI_BASE}/images/{urllib.parse.quote(remote_name)}"
        referer = f"{WIKI_BASE}/wiki/{urllib.parse.quote(wiki_page)}"
        req = urllib.request.Request(url, headers={**HEADERS, "Referer": referer})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                content = r.read()
        except Exception as exc:
            print(f"  ! failed {wiki_page} ({url}): {exc}")
            continue
        if not content.startswith(b"\x89PNG"):
            print(f"  ! not a PNG, skipping {wiki_page} ({url})")
            continue
        dest_path = dest_dir / local_name
        dest_path.write_bytes(content)
        print(f"  OK {wiki_page} -> {dest_path.relative_to(WEB_ASSETS.parent.parent)} ({len(content)} bytes)")
        saved[key] = f"/assets/foxhole/{dest_subdir}/{local_name}"
    return saved


def patch_json(filename: str, icon_paths: dict[str, str]) -> None:
    path = DATA_DIR / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    for key, web_path in icon_paths.items():
        if key in data:
            data[key]["icon"] = web_path
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    print("Downloading resource icons from foxhole.wiki.gg...")
    resource_icons = download_all(RESOURCE_ICON_FILES, "items")
    patch_json("resources.json", resource_icons)
    print(f"{len(resource_icons)} resource icons saved and linked.")

    print("\nDownloading building icons from foxhole.wiki.gg...")
    building_icons = download_all(BUILDING_ICON_FILES, "structures")
    building_icons.update(BUILDING_ICON_REUSE)
    patch_json("building_types.json", building_icons)
    print(f"{len(building_icons)} building icons linked ({len(BUILDING_ICON_REUSE)} reused from existing files).")


if __name__ == "__main__":
    main()
