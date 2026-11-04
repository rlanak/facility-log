"""Shared translations for HTTPException detail messages, so API error toasts
respect the same `lang` query param as everything else instead of always
showing up in Portuguese regardless of the selected UI language.
"""

_STRINGS = {
    "pt-BR": {
        "facility_not_found": "Facility não encontrada.",
        "owner_only": "Só o dono da facility ({owner}) pode fazer isso.",
        "owner_web_only": "Dono de facility só existe no modo web (login pelo Discord).",
        "user_not_found": "Usuário não encontrado (a pessoa precisa ter entrado no app pelo menos uma vez).",
        "invalid_thread": "Tópico inválido: cole o link do tópico (botão direito no tópico → Copiar link) ou o ID dele.",
        "invalid_webhook_url": "URL de webhook inválida. Copie em Editar canal → Integrações → Webhooks → Copiar URL do webhook.",
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
        "save_parser_missing": "Leitor do save não encontrado (foxhole-save-parser). Rode scripts/build_save_parser.py.",
        "save_missing": "Save do Foxhole não encontrado neste computador — envie o arquivo *_MapData.sav manualmente.",
        "save_invalid_file": "Esse arquivo não parece um save do Foxhole (*_MapData.sav).",
        "save_parse_failed": "Não consegui ler o save do Foxhole (o formato pode ter mudado numa atualização do jogo).",
    },
    "en-US": {
        "facility_not_found": "Facility not found.",
        "owner_only": "Only the facility's owner ({owner}) can do that.",
        "owner_web_only": "Facility owners only exist in web mode (Discord login).",
        "user_not_found": "User not found (they need to have logged in to the app at least once).",
        "invalid_thread": "Invalid thread: paste the thread link (right-click the thread → Copy Link) or its ID.",
        "invalid_webhook_url": "Invalid webhook URL. Copy it from Edit Channel → Integrations → Webhooks → Copy Webhook URL.",
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
        "save_parser_missing": "Save reader not found (foxhole-save-parser). Run scripts/build_save_parser.py.",
        "save_missing": "Foxhole save not found on this computer — upload your *_MapData.sav file manually.",
        "save_invalid_file": "That file doesn't look like a Foxhole save (*_MapData.sav).",
        "save_parse_failed": "Couldn't read the Foxhole save (the format may have changed in a game update).",
    },
}


def err(key: str, lang: str = "pt-BR", **kwargs) -> str:
    table = _STRINGS.get(lang, _STRINGS["pt-BR"])
    text = table.get(key, _STRINGS["pt-BR"][key])
    return text.format(**kwargs) if kwargs else text
