from dataclasses import dataclass
from datetime import datetime

from app import models

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


def build_building_paragraph(building: models.Building, entries: list[models.StockEntry]) -> str:
    title = f"**\U0001f3ed {building.name}**"
    if building.role:
        title += f" _({building.role})_"
    if not entries:
        return f"{title}\n_sem lançamentos_"
    items = " • ".join(
        f"{entry.resource.icon} {entry.resource.name}: {format_qty(entry.quantity)}".strip()
        for entry in sorted(entries, key=lambda e: e.resource.name)
    )
    return f"{title}\n{items}"


def build_stock_block(stock_by_building: dict[models.Building, list[models.StockEntry]]) -> str:
    paragraphs = [
        build_building_paragraph(building, entries) for building, entries in stock_by_building.items()
    ]
    return "\n\n".join(paragraphs)


def compute_recommendations(totals: list[ResourceTotal], max_items: int = 3) -> list[dict]:
    scored = []
    for total in totals:
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
        lines.append(f"{i}. {icon_prefix}**{resource.name}** — {justification}")
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
    stock_block = build_stock_block(stock_by_building)
    recommendation_block = build_recommendation_block(totals)

    markdown_content = "\n\n".join([header_block, stock_block, recommendation_block])

    building_paragraphs = [
        build_building_paragraph(building, entries) for building, entries in stock_by_building.items()
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
                        "resource": entry.resource.name,
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
