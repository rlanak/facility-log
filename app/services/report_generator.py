from dataclasses import dataclass
from datetime import datetime

from app import crud, models
from app.services import foxhole_data
from app.services import material_chain
from app.services import msupps
from app.services.msupps_save import hex_display_name
from app.services import production as production_service

DISCORD_LIMIT = 2000

_STRINGS = {
    "pt-BR": {
        "header": "**\U0001f4cb Relatório de Estoque — {name}**\n\U0001f552 {date}",
        "no_entries": "_sem lançamentos_",
        "production_insufficient": "⚙️ {queue}x em produção configurada — estoque insuficiente pra 1 ciclo. Faltando: {needed}.",
        "production_missing_item": "{qty} {name} (tem {available})",
        "production_line": "⚙️ {queue}x em produção — {cycles} ciclos com o estoque atual, pronto em {duration} (~{eta}): {outputs}",
        "production_leftover": ". Sobra: {leftovers}",
        "liquid_tank": "🧪 Tanque:",
        "recommendation_title": "**\U0001f3af Foco de Produção** _(o que falta pra bater as Metas cadastradas)_",
        "recommendation_no_targets": "Nenhuma Meta cadastrada ainda — defina uma meta de estoque num recurso do catálogo pra ver aqui o que falta produzir/farmar pra chegar nela.",
        "recommendation_all_met": "Todas as Metas cadastradas já estão em dia. ✅",
        "meta_line": "{icon}**{name}**: {current}/{target} — faltam {missing}",
        "total_time_line": "⏱️ Tempo total estimado: {duration}",
        "total_time_assumed_note": " _(assumindo 1 fila pras receitas ainda sem produção configurada — configure a fila pra um número mais preciso)_",
        "production_needed_title": "🏭 Produção necessária:",
        "production_needed_item": "{cycles} ciclos de {name} ({building})",
        "import_needed_title": "📦 Importar (produção externa):",
        "farm_needed_title": "🌾 Farm necessário:",
        "totals_title": "Total da Facility",
        "totals_production_title": "⚙️ Produção ativa (total):",
        "totals_production_item": "{queue} filas de {outputs} ({building})",
        "discord_part": "**Parte {i}/{n}**",
        "msupps_title": "**🛠️ Túneis de Manutenção (mSupps)**",
        "msupps_line": "{dot} **{name}**: ~{qty} mSupps — {rate}/h, acaba em {duration} ({pct}%)",
        "msupps_line_no_rate": "⚪ **{name}**: {qty} mSupps (lido há {ago}) — consumo ainda desconhecido",
        "msupps_unpinned": " _(fora dos pins do mapa — dado antigo)_",
    },
    "en-US": {
        "header": "**\U0001f4cb Stock Report — {name}**\n\U0001f552 {date}",
        "no_entries": "_no entries_",
        "production_insufficient": "⚙️ {queue}x production set up — not enough stock for 1 cycle. Missing: {needed}.",
        "production_missing_item": "{qty} {name} (have {available})",
        "production_line": "⚙️ {queue}x in production — {cycles} cycles with current stock, ready in {duration} (~{eta}): {outputs}",
        "production_leftover": ". Leftover: {leftovers}",
        "liquid_tank": "🧪 Tank:",
        "recommendation_title": "**\U0001f3af Production Focus** _(what's missing to hit your registered Targets)_",
        "recommendation_no_targets": "No Target registered yet — set a stock target on a catalog resource to see what's missing to reach it here.",
        "recommendation_all_met": "All registered Targets are already met. ✅",
        "meta_line": "{icon}**{name}**: {current}/{target} — {missing} short",
        "total_time_line": "⏱️ Estimated total time: {duration}",
        "total_time_assumed_note": " _(assuming 1 queue for recipes not yet configured in production — set one up for a more accurate number)_",
        "production_needed_title": "🏭 Production needed:",
        "production_needed_item": "{cycles} cycles of {name} ({building})",
        "import_needed_title": "📦 Import (outside production):",
        "farm_needed_title": "🌾 Farming needed:",
        "totals_title": "Facility Total",
        "totals_production_title": "⚙️ Active production (total):",
        "totals_production_item": "{queue} queues of {outputs} ({building})",
        "discord_part": "**Part {i}/{n}**",
        "msupps_title": "**🛠️ Maintenance Tunnels (mSupps)**",
        "msupps_line": "{dot} **{name}**: ~{qty} mSupps — {rate}/h, runs out in {duration} ({pct}%)",
        "msupps_line_no_rate": "⚪ **{name}**: {qty} mSupps (read {ago} ago) — consumption not known yet",
        "msupps_unpinned": " _(no longer pinned on the map — stale data)_",
    },
}


def _t(key: str, lang: str, **kwargs) -> str:
    table = _STRINGS.get(lang, _STRINGS["pt-BR"])
    template = table.get(key, _STRINGS["pt-BR"][key])
    return template.format(**kwargs)


def _format_list(title: str, items: list[str], bulleted: bool) -> str:
    """A titled list of items — one bullet per line for Discord (much
    easier to scan than a long " • "-joined run-on line), or the old
    compact single-line join for the in-app blocks, which stay as they
    were since that's not what needed the readability fix."""
    if bulleted:
        return f"{title}\n" + "\n".join(f"• {item}" for item in items)
    return f"{title} " + " • ".join(items)


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


def _display_qty(quantity: float, resource_def_key: str | None) -> str:
    """Liquids are shown in Liters everywhere in the report, not their raw
    Foxhole "unit"/gallon count — the tank is already framed in Liters
    (5000L cap) and that's how players think about liquids in-game, so keep
    that framing consistent even for crate/"normal" liquid stock instead of
    switching back to a raw unit count there."""
    liters_per_unit = foxhole_data.liquid_liters_per_unit(resource_def_key) if resource_def_key else None
    if liters_per_unit:
        return f"{format_qty(round(quantity * liters_per_unit))}L"
    return format_qty(quantity)


def format_duration(seconds: int) -> str:
    seconds = int(seconds)
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d{hours:02d}h"
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
    building: models.Building,
    entries: list[models.StockEntry],
    now: datetime,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
) -> str:
    catalog_lang = catalog_lang or lang
    title = f"**\U0001f3ed {crud.resolve_building_name(building, catalog_lang)}**"
    if building.role:
        title += f" _({building.role})_"

    liquid_keys = (
        set(foxhole_data.active_liquid_keys(building.building_type_key, building.production_slots))
        if building.building_type_key
        else set()
    )
    # Only the tank entry is pulled out into its own "Tanque de Líquido" line
    # below — a liquid's crate/"normal" stock (overflow once the tank's
    # full) is shown right alongside solids like any other resource.
    solid_entries = [e for e in entries if not (e.resource.resource_def_key in liquid_keys and e.storage == "tank")]

    body = f"{title}\n{_t('no_entries', lang)}" if not solid_entries else f"{title}\n" + " • ".join(
        f"{entry.resource.icon} {crud.resolve_resource_name(entry.resource, catalog_lang)}: {_display_qty(entry.quantity, entry.resource.resource_def_key)}".strip()
        for entry in sorted(solid_entries, key=lambda e: crud.resolve_resource_name(e.resource, catalog_lang))
    )

    # Production math draws on a liquid's tank *and* crate stock combined —
    # the tank display below stays tank-only, but the estimate needs both.
    combined_stock: dict[str, float] = {}
    for e in entries:
        if e.resource.resource_def_key:
            combined_stock[e.resource.resource_def_key] = combined_stock.get(e.resource.resource_def_key, 0) + e.quantity

    if liquid_keys:
        tank_stock = {e.resource.resource_def_key: e.quantity for e in entries if e.resource.resource_def_key and e.storage == "tank"}
        tank_lines = []
        for key in liquid_keys:
            units = tank_stock.get(key, 0)
            liters = round(units * foxhole_data.liquid_liters_per_unit(key))
            name = foxhole_data.resource_display_name(key, catalog_lang)
            tank_lines.append(f"{name}: {liters}L/{foxhole_data.LIQUID_TANK_CAPACITY_LITERS}L")
        body += f"\n{_t('liquid_tank', lang)} " + " • ".join(tank_lines)

    if building.building_type_key and building.production_slots:
        estimates = production_service.estimate_building_slots(
            building.building_type_key, building.production_slots, combined_stock, now, catalog_lang
        )
        for estimate in estimates:
            body += f"\n{format_production_line(estimate['queue_count'], estimate, lang)}"

    return body


def format_production_line(queue_count: int, estimate: dict, lang: str = "pt-BR") -> str:
    if estimate["cycles"] <= 0:
        missing_items = [i for i in estimate["inputs_per_cycle"] if i.get("available", 0) < i["qty"]]
        needed = ", ".join(
            _t(
                "production_missing_item",
                lang,
                qty=_display_qty(i["qty"], i.get("resource")),
                name=i["name"],
                available=_display_qty(i["available"], i.get("resource")),
            )
            for i in missing_items
        )
        return _t("production_insufficient", lang, queue=queue_count, needed=needed)

    outputs_text = ", ".join(f"{_display_qty(o['qty'], o.get('resource'))} {o['name']}" for o in estimate["outputs"])
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
        leftovers_text = ", ".join(f"{_display_qty(l['qty'], l.get('resource'))} {l['name']}" for l in leftovers)
        line += _t("production_leftover", lang, leftovers=leftovers_text)
    return line


def build_stock_block(
    stock_by_building: dict[models.Building, list[models.StockEntry]],
    now: datetime,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
) -> str:
    paragraphs = [
        build_building_paragraph(building, entries, now, lang, catalog_lang)
        for building, entries in stock_by_building.items()
    ]
    return "\n\n".join(paragraphs)


def _totals_by_def_key(totals: list[ResourceTotal]) -> dict[str, float]:
    result: dict[str, float] = {}
    for t in totals:
        if t.resource.resource_def_key:
            result[t.resource.resource_def_key] = result.get(t.resource.resource_def_key, 0) + t.quantity
    return result


def _resource_key_flags(all_resources: list[models.Resource]) -> tuple[set[str], set[str]]:
    """farmable_keys / imported_keys for every Foxhole catalog resource — the
    app's own Resource row wins when the player has customized it (via the
    Catálogo de Recursos checkboxes), else falls back to the static
    catalog's own farmable default (same default used when a resource is
    first imported — see crud.get_or_create_resource)."""
    by_key = {r.resource_def_key: r for r in all_resources if r.resource_def_key}
    farmable_keys: set[str] = set()
    imported_keys: set[str] = set()
    for key, res_def in foxhole_data.get_resource_defs().items():
        resource = by_key.get(key)
        if resource:
            if resource.imported:
                imported_keys.add(key)
            elif resource.farmable:
                farmable_keys.add(key)
        elif res_def.get("farmable", True):
            farmable_keys.add(key)
    return farmable_keys, imported_keys


def build_recommendation_block(
    stock_by_building: dict[models.Building, list[models.StockEntry]],
    totals: list[ResourceTotal],
    all_resources: list[models.Resource],
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    bulleted: bool = False,
) -> str:
    """What's missing, all the way down the production chain, to hit every
    Target (Meta) currently registered on a resource — replaces the old
    "go farm the lowest-stock item" suggestion, which used to only ever
    consider farmable resources and ignored Targets set on produced/
    intermediate ones (see memory/... or CLAUDE.md — this is the fix for
    that). Catalog-linked resources get the full recipe-chain breakdown;
    resources with no Foxhole catalog link (free-typed) just report their
    own shortfall as-is, since there's no recipe data to explode them with.
    """
    catalog_lang = catalog_lang or lang
    title = _t("recommendation_title", lang)

    any_target = any(r.target_max and r.target_max > 0 for r in all_resources)
    if not any_target:
        return f"{title}\n{_t('recommendation_no_targets', lang)}"

    stock_by_def_key = _totals_by_def_key(totals)
    totals_by_resource_id = {t.resource.id: t.quantity for t in totals}

    catalog_targets: list[tuple[models.Resource, float, float]] = []
    freeform_targets: list[tuple[models.Resource, float, float]] = []
    for resource in all_resources:
        if not resource.target_max or resource.target_max <= 0:
            continue
        current = (
            stock_by_def_key.get(resource.resource_def_key, 0)
            if resource.resource_def_key
            else totals_by_resource_id.get(resource.id, 0)
        )
        deficit = resource.target_max - current
        if deficit <= 0:
            continue
        (catalog_targets if resource.resource_def_key else freeform_targets).append((resource, current, deficit))

    if not catalog_targets and not freeform_targets:
        return f"{title}\n{_t('recommendation_all_met', lang)}"

    preferred_recipes = material_chain.active_recipes_by_output(stock_by_building.keys())
    farmable_keys, imported_keys = _resource_key_flags(all_resources)
    stock_pool = dict(stock_by_def_key)
    chain_targets = sorted(catalog_targets, key=lambda x: crud.resolve_resource_name(x[0], catalog_lang))
    # Pass the full target_max here, not the already-subtracted `deficit` —
    # stock_pool still holds this resource's full current stock, and
    # resolve_requirements() does its own have-vs-needed netting against
    # that same pool. Passing `deficit` would net the current stock a
    # second time, so a Meta on a resource that already has some stock
    # under-counted (or even zeroed out) the real production need.
    result = material_chain.resolve_requirements(
        [(r.resource_def_key, r.target_max) for r, _current, _deficit in chain_targets],
        stock_pool,
        preferred_recipes,
        farmable_keys,
        imported_keys,
    )

    lines = [title]

    meta_lines = [
        _t(
            "meta_line",
            lang,
            icon=f"{r.icon} " if r.icon else "",
            name=crud.resolve_resource_name(r, catalog_lang),
            current=_display_qty(current, r.resource_def_key),
            target=_display_qty(r.target_max, r.resource_def_key),
            missing=_display_qty(deficit, r.resource_def_key),
        )
        for r, current, deficit in sorted(
            catalog_targets + freeform_targets, key=lambda x: crud.resolve_resource_name(x[0], catalog_lang)
        )
    ]
    lines.append("\n".join(f"• {m}" if bulleted else m for m in meta_lines))

    if result["production"]:
        time_estimate = material_chain.compute_production_time(result["production"], preferred_recipes)
        time_line = _t("total_time_line", lang, duration=format_duration(time_estimate["total_seconds"]))
        if time_estimate["any_assumed_single_queue"]:
            time_line += _t("total_time_assumed_note", lang)
        lines.append(time_line)

    if result["production"]:
        prod_lines = []
        for (bt_key, recipe_key), cycles in sorted(result["production"].items(), key=lambda kv: -kv[1]):
            recipe = foxhole_data.get_recipe(bt_key, recipe_key)
            output_keys = [o["resource"] for o in recipe["outputs"] if o.get("resource")] if recipe else []
            output_name = (
                ", ".join(foxhole_data.resource_display_name(k, catalog_lang) for k in output_keys)
                if output_keys
                else recipe_key
            )
            prod_lines.append(
                _t(
                    "production_needed_item",
                    lang,
                    cycles=format_qty(cycles),
                    name=output_name,
                    building=foxhole_data.building_display_name(bt_key, catalog_lang),
                )
            )
        lines.append(_format_list(_t("production_needed_title", lang), prod_lines, bulleted))

    if result["imports"]:
        import_lines = [
            f"{foxhole_data.resource_display_name(key, catalog_lang)}: {_display_qty(qty, key)}"
            for key, qty in sorted(result["imports"].items(), key=lambda kv: -kv[1])
        ]
        lines.append(_format_list(_t("import_needed_title", lang), import_lines, bulleted))

    farm_lines = [
        f"{foxhole_data.resource_display_name(key, catalog_lang)}: {_display_qty(qty, key)}"
        for key, qty in sorted(result["farm"].items(), key=lambda kv: -kv[1])
    ]
    farm_lines += [
        f"{crud.resolve_resource_name(r, catalog_lang)}: {_display_qty(deficit, r.resource_def_key)}"
        for r, _current, deficit in freeform_targets
    ]
    if farm_lines:
        lines.append(_format_list(_t("farm_needed_title", lang), farm_lines, bulleted))

    return "\n".join(lines)


def build_totals_block(
    stock_by_building: dict[models.Building, list[models.StockEntry]],
    totals: list[ResourceTotal],
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
) -> str:
    """Facility-wide resource + production totals, consolidated across every
    building — used for the Discord message instead of the building-by-
    building breakdown (that level of detail already lives in the "Estoque
    Atual" block/tab; repeating it made the Discord message balloon)."""
    catalog_lang = catalog_lang or lang
    title = f"**\U0001f4e6 {_t('totals_title', lang)}**"
    if not totals:
        return f"{title}\n{_t('no_entries', lang)}"

    resource_lines = [
        f"{t.resource.icon} {crud.resolve_resource_name(t.resource, catalog_lang)}: {_display_qty(t.quantity, t.resource.resource_def_key)}".strip()
        for t in sorted(totals, key=lambda t: crud.resolve_resource_name(t.resource, catalog_lang))
    ]
    body = _format_list(title, resource_lines, bulleted=True)

    queue_totals: dict[tuple[str, str], int] = {}
    for building in stock_by_building:
        if not building.building_type_key or not building.production_slots:
            continue
        for slot in building.production_slots:
            key = (building.building_type_key, slot["recipe_key"])
            queue_totals[key] = queue_totals.get(key, 0) + slot["queue_count"]

    if queue_totals:
        prod_lines = []
        for (bt_key, recipe_key), total_queue in sorted(queue_totals.items(), key=lambda kv: -kv[1]):
            recipe = foxhole_data.get_recipe(bt_key, recipe_key)
            if not recipe:
                continue
            outputs_text = ", ".join(
                foxhole_data.resource_display_name(o["resource"], catalog_lang) for o in recipe["outputs"] if o.get("resource")
            ) or recipe_key
            prod_lines.append(
                _t(
                    "totals_production_item",
                    lang,
                    queue=total_queue,
                    outputs=outputs_text,
                    building=foxhole_data.building_display_name(bt_key, catalog_lang),
                )
            )
        body += "\n\n" + _format_list(_t("totals_production_title", lang), prod_lines, bulleted=True)

    return body


def _health_dot(pct: int) -> str:
    # Same tiers as the tray app's status dot.
    if pct < 15:
        return "🔴"
    if pct < 35:
        return "🟠"
    if pct < 70:
        return "🟡"
    return "🟢"


def build_msupps_block(tunnels: list[models.MaintenanceTunnel], now: datetime, lang: str = "pt-BR") -> str:
    """mSupps of the Maintenance Tunnels linked to this facility, read from
    the game's save (not typed in). The quantity is projected to `now` from
    the last in-game reading, so it reads "~N" — see services/msupps.py."""
    now_unix = now.timestamp()
    lines = []
    for tunnel in tunnels:
        status = msupps.tunnel_status(tunnel, now_unix)
        if status["quantity"] is None:
            continue
        name = tunnel.label or f"{hex_display_name(tunnel.map_id)} {tunnel.grid}".strip()
        if status["rate_per_hour"]:
            line = _t(
                "msupps_line",
                lang,
                dot=_health_dot(status["health_pct"]),
                name=name,
                qty=format_qty(round(status["estimated_now"])),
                rate=_trim(round(status["rate_per_hour"])),
                duration=format_duration(status["seconds_left"]),
                pct=status["health_pct"],
            )
        else:
            line = _t(
                "msupps_line_no_rate",
                lang,
                name=name,
                qty=format_qty(status["quantity"]),
                ago=format_duration(max(0, int(now_unix - status["game_updated_unix"]))),
            )
        if not tunnel.pinned:
            line += _t("msupps_unpinned", lang)
        lines.append(line)
    if not lines:
        return ""
    return _t("msupps_title", lang) + "\n" + "\n".join(lines)


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
    all_resources: list[models.Resource],
    now: datetime | None = None,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    tunnels: list[models.MaintenanceTunnel] | None = None,
) -> dict:
    now = now or datetime.now()
    catalog_lang = catalog_lang or lang
    totals = _aggregate_resource_totals(stock_by_building)

    header_block = build_header_block(facility, now, lang)
    msupps_block = build_msupps_block(tunnels or [], now, lang)
    stock_block = build_stock_block(stock_by_building, now, lang, catalog_lang)
    recommendation_block = build_recommendation_block(stock_by_building, totals, all_resources, lang, catalog_lang)

    # extract_blocks() treats everything between the header and the last
    # paragraph as "stock", so the mSupps block lands at the top of the
    # in-app "Estoque Atual" block without needing a block of its own.
    markdown_content = "\n\n".join(p for p in [header_block, msupps_block, stock_block, recommendation_block] if p)

    # The Discord version consolidates every building into one facility-wide
    # total instead of repeating the per-building breakdown already shown in
    # "Estoque Atual" — kept as separate paragraphs (not folded into
    # markdown_content) so it can be persisted and re-split independently.
    # It also re-renders the recommendation with one bullet per line instead
    # of the dense " • "-joined run-on — much easier to read on Discord —
    # while leaving the in-app "Recomendação de Farm" block above untouched.
    totals_block = build_totals_block(stock_by_building, totals, lang, catalog_lang)
    discord_recommendation_block = build_recommendation_block(
        stock_by_building, totals, all_resources, lang, catalog_lang, bulleted=True
    )
    discord_paragraphs = [p for p in [header_block, msupps_block, totals_block, discord_recommendation_block] if p]
    parts = split_for_discord(discord_paragraphs, lang=lang)

    snapshot = {
        "facility": facility.name,
        "generated_at": now.isoformat(),
        "buildings": [
            {
                "name": building.name,
                "role": building.role,
                "entries": [
                    {
                        "resource": crud.resolve_resource_name(entry.resource, catalog_lang),
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
        "discord_content": "\n\n".join(discord_paragraphs),
        "blocks": {
            "header": header_block,
            # Same shape extract_blocks() rebuilds from markdown_content when
            # the report is reopened from history.
            "stock": "\n\n".join(p for p in [msupps_block, stock_block] if p),
            "recommendation": recommendation_block,
        },
        "parts": parts,
        "snapshot": snapshot,
    }
