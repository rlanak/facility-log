from fastapi import APIRouter

from app.services import foxhole_data

router = APIRouter(prefix="/api/foxhole", tags=["foxhole"])


@router.get("/resources", response_model=list[dict])
def list_foxhole_resources():
    return [
        {
            "key": key,
            "name_en": data["name"]["en"],
            "name_pt": data["name"].get("pt"),
            "farmable": data["farmable"],
            "icon": data.get("icon"),
            "is_liquid": data.get("is_liquid", False),
            "liters_per_unit": data.get("liters_per_unit"),
        }
        for key, data in foxhole_data.get_resource_defs().items()
    ]


@router.get("/building-types", response_model=list[dict])
def list_foxhole_building_types():
    return [
        {
            "key": key,
            "name_en": data["name_en"],
            "name_pt": data.get("name_pt"),
            "queue_slots": data["queue_slots"],
            "wiki_url": data.get("wiki_url"),
            "icon": data.get("icon"),
            "recipes": data["recipes"],
        }
        for key, data in foxhole_data.get_building_type_defs().items()
    ]
