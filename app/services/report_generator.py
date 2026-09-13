from dataclasses import dataclass
from datetime import datetime

from app import crud, models
from app.services import production as production_service

DISCORD_LIMIT = 2000

_STRINGS = {
    "pt-BR": {
        "header": "**\U0001f4cb Relatório de Estoque — {name}**\n\U0001f552 {date}",
        "no_entries": "_sem lançamentos_",
        "production_insufficient": "⚙️ {queue}x em produção configurada — estoque insuficiente pra 1 ciclo (precisa de {needed} por ciclo).",
        "production_line": "⚙️ {queue}x em produção — {cycles} ciclos com o estoque atual, pronto em {duration} (~{eta}): {outputs}",
        "production_leftover": ". Sobra: {leftovers}",
        "recommendation_title": "**\U0001f3af Foco de Farm Recomendado**",
        "recommendation_no_data": "Sem dados de estoque suficientes pra recomendar.",
        "recommendation_no_farmable": "Nenhum recurso farmável cadastrado — marque os recursos que são matéria-prima no catálogo.",
        "justification_with_target": "{qty} em estoque, só {pct} da meta de {target}. Prioridade alta.",
        "justification_no_target": "{qty} em estoque, o mais baixo sem meta cadastrada.",
        "discord_part": "**Parte {i}/{n}**",
    },
    "en-US": {
        "header": "**\U0001f4cb Stock Report — {name}**\n\U0001f552 {date}",
        "no_entries": "_no entries_",
        "production_insufficient": "⚙️ {queue}x production set up — not enough stock for 1 cycle (needs {needed} per cycle).",
        "production_line": "⚙️ {queue}x in production — {cycles} cycles with current stock, ready in {duration} (~{eta}): {outputs}",
        "production_leftover": ". Leftover: {leftovers}",
        "recommendation_title": "**\U0001f3af Recommended Farm Focus**",
        "recommendation_no_data": "Not enough stock data to make a recommendation.",
        "recommendation_no_farmable": "No farmable resource registered — mark resources that are raw materials in the catalog.",
        "justification_with_target": "{qty} in stock, only {pct} of the {target} target. High priority.",
        "justification_no_target": "{qty} in stock, the lowest without a registered target.",
        "discord_part": "**Part {i}/{n}**",
    },
}


def _t(key: str, lang: str, **kwargs) -> str:
    table = _STRINGS.get(lang, _STRINGS["pt-BR"])
    template = table.get(key, _STRINGS["pt-BR"][key])
    return template.format(**kwargs)


# Plain strftime formats instead of the stdlib locale module — locale names
# need to be installed on the OS to work (unreliable on Windows), and this is
# the only date formatting this module needs.
_DATE_FORMATS = {"pt-BR": "%d/%m/%Y %H:%M", "en-US": "%m/%d/%Y %I:%M %p"}
_TIME_FORMATS = {"pt-BR": "%H:%M", "en-US": "%I:%M %p"}


def _format_date(dt: datetime, lang: str) -> str:
    return dt.strftime(_DATE_FORMATS.get(lang, _DATE_FORMATS["pt-BR"]))


def _format_time(dt: datetime, lang: str) -> str:
    return dt.strftime(_TIME_FORMATS.get(lang, _TIME_FORMATS["pt-BR"]))


def format_qty(value: float) -> str:
    if value >= 1_000_000:
        return _trim(value / 1_000_000) + "M"
    if value >= 1_000:
        return _trim(value / 1_000) + "k"
    return _trim(value)


def _trim(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def format_duration(seconds: int) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h{minutes:02d}"
    if minutes:
        return f"{minutes}min"
    return f"{secs}s"


@dataclass
class ResourceTotal:
    resource: models.Resource
    quantity: float


def _aggregate_resource_totals(stock_by_building: dict[models.Building, list[models.StockEntry]]) -> list[ResourceTotal]:
    totals: dict[int, ResourceTotal] = {}
    for entries in stock_by_building.values():
        for entry in entries:
            if entry.resource_id not in totals:
                totals[entry.resource_id] = ResourceTotal(resource=entry.resource, quantity=0)
            totals[entry.resource_id].quantity += entry.quantity
    return list(totals.values())


def build_header_block(facility: models.Facility, now: datetime, lang: str = "pt-BR") -> str:
    return _t("header", lang, name=facility.name, date=_format_date(now, lang))


def build_building_paragraph(
    building: models.Building, entries: list[models.StockEntry], now: datetime, lang: str = "pt-BR"
) -> str:
    title = f"**\U0001f3ed {crud.resolve_building_name(building, lang)}**"
    if building.role:
        title += f" _({building.role})_"

    body = f"{title}\n{_t('no_entries', lang)}" if not entries else f"{title}\n" + " • ".join(
        f"{entry.resource.icon} {crud.resolve_resource_name(entry.resource, lang)}: {format_qty(entry.quantity)}".strip()
        for entry in sorted(entries, key=lambda e: crud.resolve_resource_name(e.resource, lang))
    )

    if building.building_type_key and building.active_recipe_key and building.queue_count > 0:
        current_stock = {e.resource.resource_def_key: e.quantity for e in entries if e.resource.resource_def_key}
        estimate = production_service.estimate_production(
            building.building_type_key, building.active_recipe_key, building.queue_count, current_stock, now, lang
        )
        if estimate:
            body += f"\n{format_production_line(building.queue_count, estimate, lang)}"

    return body


def format_production_line(queue_count: int, estimate: dict, lang: str = "pt-BR") -> str:
    if estimate["cycles"] <= 0:
        needed = ", ".join(f"{format_qty(i['qty'])} {i['name']}" for i in estimate["inputs_per_cycle"])
        return _t("production_insufficient", lang, queue=queue_count, needed=needed)

    outputs_text = ", ".join(f"{format_qty(o['qty'])} {o['name']}" for o in estimate["outputs"])
    line = _t(
        "production_line",
        lang,
        queue=queue_count,
        cycles=estimate["cycles"],
        duration=format_duration(estimate["time_seconds"]),
        eta=_format_time(estimate["eta"], lang),
        outputs=outputs_text,
    )
    leftovers = [l for l in estimate["leftovers"] if l["qty"] > 0]
    if leftovers:
        leftovers_text = ", ".join(f"{format_qty(l['qty'])} {l['name']}" for l in leftovers)
        line += _t("production_leftover", lang, leftovers=leftovers_text)
    return line


def build_stock_block(
    stock_by_building: dict[models.Building, list[models.StockEntry]], now: datetime, lang: str = "pt-BR"
) -> str:
    paragraphs = [
        build_building_paragraph(building, entries, now, lang) for building, entries in stock_by_building.items()
    ]
    return "\n\n".join(paragraphs)


def compute_recommendations(totals: list[ResourceTotal], max_items: int = 3) -> list[dict]:
    farmable_totals = [t for t in totals if t.resource.farmable]

    scored = []
    for total in farmable_totals:
        resource = total.resource
        if resource.target_max and resource.target_max > 0:
            pct = total.quantity / resource.target_max
            scored.append({"resource": resource, "quantity": total.quantity, "pct": pct})
        else:
            scored.append({"resource": resource, "quantity": total.quantity, "pct": None})

    with_pct = sorted((s for s in scored if s["pct"] is not None), key=lambda s: s["pct"])
    without_pct = sorted((s for s in scored if s["pct"] is None), key=lambda s: s["quantity"])
    return (with_pct + without_pct)[:max_items]


def build_recommendation_block(totals: list[ResourceTotal], lang: str = "pt-BR") -> str:
    title = _t("recommendation_title", lang)
    if not totals:
        return f"{title}\n{_t('recommendation_no_data', lang)}"

    recommendations = compute_recommendations(totals)
    if not recommendations:
        return f"{title}\n{_t('recommendation_no_farmable', lang)}"

    lines = []
    for i, rec in enumerate(recommendations, start=1):
        resource: models.Resource = rec["resource"]
        qty_text = format_qty(rec["quantity"])
        if rec["pct"] is not None:
            pct_text = f"{rec['pct'] * 100:.0f}%"
            target_text = format_qty(resource.target_max)
            justification = _t("justification_with_target", lang, qty=qty_text, pct=pct_text, target=target_text)
        else:
            justification = _t("justification_no_target", lang, qty=qty_text)
        icon_prefix = f"{resource.icon} " if resource.icon else ""
        display_name = crud.resolve_resource_name(resource, lang)
        lines.append(f"{i}. {icon_prefix}**{display_name}** — {justification}")
    return f"{title}\n" + "\n".join(lines)


def _pack_paragraphs(paragraphs: list[str], limit: int) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        add_len = len(paragraph) + (2 if current else 0)
        if current and current_len + add_len > limit:
            parts.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += add_len
    if current:
        parts.append("\n\n".join(current))
    return parts


def extract_blocks(markdown_content: str) -> dict[str, str]:
    paragraphs = markdown_content.split("\n\n")
    return {
        "header": paragraphs[0],
        "stock": "\n\n".join(paragraphs[1:-1]),
        "recommendation": paragraphs[-1],
    }


def split_for_discord(paragraphs: list[str], limit: int = DISCORD_LIMIT, lang: str = "pt-BR") -> list[str]:
    parts = _pack_paragraphs(paragraphs, limit)
    if len(parts) <= 1:
        return parts

    part_count = len(parts)
    for _ in range(3):
        prefix_len = len(f"{_t('discord_part', lang, i=part_count, n=part_count)}\n\n")
        parts = _pack_paragraphs(paragraphs, limit - prefix_len)
        if len(parts) == part_count:
            break
        part_count = len(parts)

    return [f"{_t('discord_part', lang, i=i, n=len(parts))}\n\n{part}" for i, part in enumerate(parts, start=1)]


def generate_report(
    facility: models.Facility,
    stock_by_building: dict[models.Building, list[models.StockEntry]],
    now: datetime | None = None,
    lang: str = "pt-BR",
) -> dict:
    now = now or datetime.now()
    totals = _aggregate_resource_totals(stock_by_building)

    header_block = build_header_block(facility, now, lang)
    stock_block = build_stock_block(stock_by_building, now, lang)
    recommendation_block = build_recommendation_block(totals, lang)

    markdown_content = "\n\n".join([header_block, stock_block, recommendation_block])

    building_paragraphs = [
        build_building_paragraph(building, entries, now, lang) for building, entries in stock_by_building.items()
    ]
    paragraphs = [header_block, *building_paragraphs, recommendation_block]
    parts = split_for_discord(paragraphs, lang=lang)

    snapshot = {
        "facility": facility.name,
        "generated_at": now.isoformat(),
        "buildings": [
            {
                "name": building.name,
                "role": building.role,
                "entries": [
                    {
                        "resource": crud.resolve_resource_name(entry.resource, lang),
                        "icon": entry.resource.icon,
                        "quantity": entry.quantity,
                    }
                    for entry in entries
                ],
            }
            for building, entries in stock_by_building.items()
        ],
    }

    return {
        "markdown_content": markdown_content,
        "blocks": {
            "header": header_block,
            "stock": stock_block,
            "recommendation": recommendation_block,
        },
        "parts": parts,
        "snapshot": snapshot,
    }
