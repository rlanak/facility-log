from dataclasses import dataclass
from datetime import datetime

from app import models
from app.services import production as production_service

DISCORD_LIMIT = 2000


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


def build_header_block(facility: models.Facility, now: datetime) -> str:
    return f"**\U0001f4cb Relatório de Estoque — {facility.name}**\n\U0001f552 {now.strftime('%d/%m/%Y %H:%M')}"


def build_building_paragraph(building: models.Building, entries: list[models.StockEntry], now: datetime) -> str:
    title = f"**\U0001f3ed {building.name}**"
    if building.role:
        title += f" _({building.role})_"

    body = f"{title}\n_sem lançamentos_" if not entries else f"{title}\n" + " • ".join(
        f"{entry.resource.icon} {entry.resource.display_name}: {format_qty(entry.quantity)}".strip()
        for entry in sorted(entries, key=lambda e: e.resource.display_name)
    )

    if building.building_type_key and building.active_recipe_key and building.queue_count > 0:
        current_stock = {e.resource.resource_def_key: e.quantity for e in entries if e.resource.resource_def_key}
        estimate = production_service.estimate_production(
            building.building_type_key, building.active_recipe_key, building.queue_count, current_stock, now
        )
        if estimate:
            body += f"\n{format_production_line(building.queue_count, estimate)}"

    return body


def format_production_line(queue_count: int, estimate: dict) -> str:
    if estimate["cycles"] <= 0:
        needed = ", ".join(f"{format_qty(i['qty'] or 1)} {i['name']}" for i in estimate["inputs_consumed"])
        return f"⚙️ {queue_count}x em produção configurada — estoque insuficiente pra 1 ciclo (precisa de {needed} por ciclo)."

    outputs_text = ", ".join(f"{format_qty(o['qty'])} {o['name']}" for o in estimate["outputs"])
    line = (
        f"⚙️ {queue_count}x em produção — {estimate['cycles']} ciclos com o estoque atual,"
        f" pronto em {format_duration(estimate['time_seconds'])} (~{estimate['eta'].strftime('%H:%M')}): {outputs_text}"
    )
    leftovers = [l for l in estimate["leftovers"] if l["qty"] > 0]
    if leftovers:
        leftovers_text = ", ".join(f"{format_qty(l['qty'])} {l['name']}" for l in leftovers)
        line += f". Sobra: {leftovers_text}"
    return line


def build_stock_block(stock_by_building: dict[models.Building, list[models.StockEntry]], now: datetime) -> str:
    paragraphs = [
        build_building_paragraph(building, entries, now) for building, entries in stock_by_building.items()
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


def build_recommendation_block(totals: list[ResourceTotal]) -> str:
    title = "**\U0001f3af Foco de Farm Recomendado**"
    if not totals:
        return f"{title}\nSem dados de estoque suficientes pra recomendar."

    recommendations = compute_recommendations(totals)
    if not recommendations:
        return f"{title}\nNenhum recurso farmável cadastrado — marque os recursos que são matéria-prima no catálogo."

    lines = []
    for i, rec in enumerate(recommendations, start=1):
        resource: models.Resource = rec["resource"]
        qty_text = format_qty(rec["quantity"])
        if rec["pct"] is not None:
            pct_text = f"{rec['pct'] * 100:.0f}%"
            target_text = format_qty(resource.target_max)
            justification = f"{qty_text} em estoque, só {pct_text} da meta de {target_text}. Prioridade alta."
        else:
            justification = f"{qty_text} em estoque, o mais baixo sem meta cadastrada."
        icon_prefix = f"{resource.icon} " if resource.icon else ""
        lines.append(f"{i}. {icon_prefix}**{resource.display_name}** — {justification}")
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


def split_for_discord(paragraphs: list[str], limit: int = DISCORD_LIMIT) -> list[str]:
    parts = _pack_paragraphs(paragraphs, limit)
    if len(parts) <= 1:
        return parts

    part_count = len(parts)
    for _ in range(3):
        prefix_len = len(f"**Parte {part_count}/{part_count}**\n\n")
        parts = _pack_paragraphs(paragraphs, limit - prefix_len)
        if len(parts) == part_count:
            break
        part_count = len(parts)

    return [f"**Parte {i}/{len(parts)}**\n\n{part}" for i, part in enumerate(parts, start=1)]


def generate_report(
    facility: models.Facility,
    stock_by_building: dict[models.Building, list[models.StockEntry]],
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now()
    totals = _aggregate_resource_totals(stock_by_building)

    header_block = build_header_block(facility, now)
    stock_block = build_stock_block(stock_by_building, now)
    recommendation_block = build_recommendation_block(totals)

    markdown_content = "\n\n".join([header_block, stock_block, recommendation_block])

    building_paragraphs = [
        build_building_paragraph(building, entries, now) for building, entries in stock_by_building.items()
    ]
    paragraphs = [header_block, *building_paragraphs, recommendation_block]
    parts = split_for_discord(paragraphs)

    snapshot = {
        "facility": facility.name,
        "generated_at": now.isoformat(),
        "buildings": [
            {
                "name": building.name,
                "role": building.role,
                "entries": [
                    {
                        "resource": entry.resource.display_name,
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
