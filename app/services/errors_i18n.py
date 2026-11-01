"""Shared translations for HTTPException detail messages, so API error toasts
respect the same `lang` query param as everything else instead of always
showing up in Portuguese regardless of the selected UI language.
"""

_STRINGS = {
    "pt-BR": {
        "facility_not_found": "Facility não encontrada.",
        "building_not_found": "Prédio não encontrado.",
        "resource_not_found": "Recurso não encontrado.",
        "report_not_found": "Relatório não encontrado.",
        "image_not_found": "Imagem não encontrada.",
        "need_name_or_type": "Informe um nome ou selecione um tipo do Foxhole.",
        "building_not_linked": "Este prédio não está vinculado a um tipo do Foxhole.",
        "queue_slots_exceeded": "Total de filas passa do limite de filas do prédio.",
        "liquid_tank_exceeded": "{name}: o tanque de líquido cabe no máximo {max} unidades (5000L).",
        "resource_name_exists": "Já existe um recurso com esse nome.",
        "resource_in_use": "Não é possível excluir: há lançamentos de estoque usando esse recurso. Apague os lançamentos primeiro.",
        "invalid_image_type": "Envie uma imagem PNG, JPEG ou WEBP.",
        "tunnel_not_found": "Túnel não encontrado.",
        "msupps_parser_missing": "Leitor do save não encontrado (foxhole-msupps-parser.exe). Rode scripts/prepare_msupps_parser_vendor.py.",
        "msupps_save_missing": "Save do Foxhole não encontrado em %LOCALAPPDATA%/Foxhole/Saved/SaveGames — abra o jogo pelo menos uma vez neste PC.",
        "msupps_parse_failed": "Não consegui ler o save do Foxhole (o formato pode ter mudado numa atualização do jogo).",
    },
    "en-US": {
        "facility_not_found": "Facility not found.",
        "building_not_found": "Building not found.",
        "resource_not_found": "Resource not found.",
        "report_not_found": "Report not found.",
        "image_not_found": "Image not found.",
        "need_name_or_type": "Enter a name or select a Foxhole type.",
        "building_not_linked": "This building isn't linked to a Foxhole type.",
        "queue_slots_exceeded": "Total queues exceed the building's queue limit.",
        "liquid_tank_exceeded": "{name}: the liquid tank holds at most {max} units (5000L).",
        "resource_name_exists": "A resource with that name already exists.",
        "resource_in_use": "Can't delete: there are stock entries using this resource. Delete those entries first.",
        "invalid_image_type": "Upload a PNG, JPEG, or WEBP image.",
        "tunnel_not_found": "Tunnel not found.",
        "msupps_parser_missing": "Save reader not found (foxhole-msupps-parser.exe). Run scripts/prepare_msupps_parser_vendor.py.",
        "msupps_save_missing": "Foxhole save not found in %LOCALAPPDATA%/Foxhole/Saved/SaveGames — launch the game at least once on this PC.",
        "msupps_parse_failed": "Couldn't read the Foxhole save (the format may have changed in a game update).",
    },
}


def err(key: str, lang: str = "pt-BR") -> str:
    table = _STRINGS.get(lang, _STRINGS["pt-BR"])
    return table.get(key, _STRINGS["pt-BR"][key])
