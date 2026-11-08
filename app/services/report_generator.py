from dataclasses import dataclass
from datetime import datetime

from app import crud, models
from app.services import foxhole_data
from app.services import material_chain
from app.services import production as production_service

DISCORD_LIMIT = 2000

_STRINGS = {
    "pt-BR": {
        "header": "**\U0001f4cb Relatório de Estoque — {name}**\n\U0001f552 {date}",
        "no_entries": "_sem lançamentos_",
        "production_insufficient": "⚙️ {queues} em produção — estoque insuficiente pra 1 ciclo. Faltando: {needed}.",
        "production_missing_item": "{qty} {name} (tem {available})",
        "production_line": "⚙️ {queues} → {cycles} ciclos com o estoque atual ({per_queue} × {cycle}) = {duration}, pronto ~{eta}: {outputs}",
        "queues_one": "{n} fila",
        "queues_many": "{n} filas",
        "per_queue_exact": "{rounds} por fila",
        "per_queue_upto": "até {rounds} por fila",
        "production_leftover": ". Sobra: {leftovers}",
        "liquid_tank": "🧪 Tanque:",
        "recommendation_title": "**\U0001f3af Foco de Produção** _(o que falta pra bater as Metas cadastradas)_",
        "recommendation_no_targets": "Nenhuma Meta cadastrada ainda — adicione metas na aba Metas desta facility pra ver aqui o que falta produzir/farmar pra chegar nelas.",
        "recommendation_all_met": "Todas as Metas cadastradas já estão em dia. ✅",
        "meta_line": "{icon}**{name}**: {current}/{target} — faltam {missing}",
        "total_time_line": "⏱️ Tempo total com 5 filas: **{duration}**{current} — caminho mais longo: {path} _(o resto roda em paralelo)_",
        "total_time_current": " (com as filas atuais: **{duration}**)",
        "production_needed_title": "🏭 Produção necessária:",
        "production_needed_item": "{name}: {cycles} ciclos em {building} — {timing}",
        "timing_current": "fila atual ({queues}) → {per_queue} × {cycle} = {duration}",
        "timing_full": "Estimativa com {queues} → {per_queue} × {cycle} = {duration}",
        "cycles_legend": "_ℹ️ 1 ciclo = 1 execução da receita (consome os insumos, entrega o produto). Filas do mesmo prédio rodam em paralelo: tempo = ciclos ÷ filas × tempo de 1 ciclo._",
        "import_needed_title": "📦 Importar (produção externa):",
        "farm_needed_title": "🌾 Farm necessário:",
        "totals_title": "Total da Facility",
        "totals_production_title": "⚙️ Produção ativa (total):",
        "totals_production_item": "{queue} filas de {outputs} ({building})",
        "discord_part": "**Parte {i}/{n}**",
    },
    "en-US": {
        "header": "**\U0001f4cb Stock Report — {name}**\n\U0001f552 {date}",
        "no_entries": "_no entries_",
        "production_insufficient": "⚙️ {queues} set up — not enough stock for 1 cycle. Missing: {needed}.",
        "production_missing_item": "{qty} {name} (have {available})",
        "production_line": "⚙️ {queues} → {cycles} cycles with current stock ({per_queue} × {cycle}) = {duration}, ready ~{eta}: {outputs}",
        "queues_one": "{n} queue",
        "queues_many": "{n} queues",
        "per_queue_exact": "{rounds} per queue",
        "per_queue_upto": "up to {rounds} per queue",
        "production_leftover": ". Leftover: {leftovers}",
        "liquid_tank": "🧪 Tank:",
        "recommendation_title": "**\U0001f3af Production Focus** _(what's missing to hit your registered Targets)_",
        "recommendation_no_targets": "No Target registered yet — add targets in this facility's Targets tab to see what's missing to reach them here.",
        "recommendation_all_met": "All registered Targets are already met. ✅",
        "meta_line": "{icon}**{name}**: {current}/{target} — {missing} short",
        "total_time_line": "⏱️ Total time with 5 queues: **{duration}**{current} — longest chain: {path} _(everything else runs in parallel)_",
        "total_time_current": " (with the current queues: **{duration}**)",
        "production_needed_title": "🏭 Production needed:",
        "production_needed_item": "{name}: {cycles} cycles at {building} — {timing}",
        "timing_current": "current queues ({queues}) → {per_queue} × {cycle} = {duration}",
        "timing_full": "Estimate with {queues} → {per_queue} × {cycle} = {duration}",
        "cycles_legend": "_ℹ️ 1 cycle = 1 run of the recipe (uses up the inputs, delivers the output). Queues in the same building run in parallel: time = cycles ÷ queues × time of 1 cycle._",
        "import_needed_title": "📦 Import (outside production):",
        "farm_needed_title": "🌾 Farming needed:",
        "totals_title": "Facility Total",
        "totals_production_title": "⚙️ Active production (total):",
        "totals_production_item": "{queue} queues of {outputs} ({building})",
        "discord_part": "**Part {i}/{n}**",
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
    unlimited_keys: set = frozenset(),
) -> str:
    catalog_lang = catalog_lang or lang
    title = f"**\U0001f3ed {crud.resolve_building_name(building, catalog_lang)}**"
    if building.role:
        title += f" _({building.role})_"

    liquid_keys = (
        set(foxhole_data.active_liquid_keys(building.building_type_key, building.production_slots)) - set(unlimited_keys)
        if building.building_type_key
        else set()
    )
    # Only the tank entry is pulled out into its own "Tanque de Líquido" line
    # below — a liquid's crate/"normal" stock (overflow once the tank's
    # full) is shown right alongside solids like any other resource.
    # 0 entries (an item that ran out, e.g. zeroed by a print) stay out of
    # the listing; the production math below still sees every entry.
    solid_entries = [
        e for e in entries if e.quantity > 0 and not (e.resource.resource_def_key in liquid_keys and e.storage == "tank")
    ]

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
            building.building_type_key, building.production_slots, combined_stock, now, catalog_lang, unlimited_keys
        )
        for estimate in estimates:
            body += f"\n{format_production_line(estimate['queue_count'], estimate, lang)}"

    return body


def _queues_text(n: int, lang: str) -> str:
    return _t("queues_one" if n == 1 else "queues_many", lang, n=n)


def _per_queue_text(cycles: float, queue_count: int, rounds: int, lang: str) -> str:
    # Cycles that don't split evenly leave some queues one cycle short —
    # "up to N per queue" keeps "N × cycle time = total" honest.
    if queue_count == 1:
        return str(rounds)
    exact = cycles == rounds * queue_count
    return _t("per_queue_exact" if exact else "per_queue_upto", lang, rounds=rounds)


def format_cycle_time(seconds: int) -> str:
    """One recipe cycle's time, with its seconds kept (a 90s recipe is
    "1min30", not format_duration's rounded "1min") — it's the multiplier in
    the "N × cycle = total" math shown to the user, so it has to be exact."""
    minutes, secs = divmod(int(seconds), 60)
    if minutes >= 60:
        return format_duration(seconds)
    if minutes and secs:
        return f"{minutes}min{secs:02d}"
    if minutes:
        return f"{minutes}min"
    return f"{secs}s"


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
        return _t("production_insufficient", lang, queues=_queues_text(queue_count, lang), needed=needed)

    outputs_text = ", ".join(f"{_display_qty(o['qty'], o.get('resource'))} {o['name']}" for o in estimate["outputs"])
    line = _t(
        "production_line",
        lang,
        queues=_queues_text(queue_count, lang),
        cycles=estimate["cycles"],
        per_queue=_per_queue_text(estimate["cycles"], queue_count, estimate["rounds"], lang),
        cycle=format_cycle_time(estimate["cycle_seconds"]),
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
    unlimited_keys: set = frozenset(),
) -> str:
    paragraphs = [
        build_building_paragraph(building, entries, now, lang, catalog_lang, unlimited_keys)
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
    item panel's Origin choice), else falls back to the static
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
    targets: dict[int, float],
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
    bulleted: bool = False,
) -> str:
    """What's missing, all the way down the production chain, to hit every
    Target (Meta) registered for this facility (`targets`: resource_id →
    target) — replaces the old
    "go farm the lowest-stock item" suggestion, which used to only ever
    consider farmable resources and ignored Targets set on produced/
    intermediate ones (see memory/... or CLAUDE.md — this is the fix for
    that). Catalog-linked resources get the full recipe-chain breakdown;
    resources with no Foxhole catalog link (free-typed) just report their
    own shortfall as-is, since there's no recipe data to explode them with.
    """
    catalog_lang = catalog_lang or lang
    title = _t("recommendation_title", lang)
    # Explained once, at the end of this block, since both it and the
    # per-building production lines talk in "cycles" and "queues".
    legend = f"\n{_t('cycles_legend', lang)}" if any(b.production_slots for b in stock_by_building) else ""

    any_target = any(t > 0 for t in targets.values())
    if not any_target:
        return f"{title}\n{_t('recommendation_no_targets', lang)}{legend}"

    stock_by_def_key = _totals_by_def_key(totals)
    totals_by_resource_id = {t.resource.id: t.quantity for t in totals}

    unlimited_keys = crud.unlimited_resource_keys(all_resources)
    catalog_targets: list[tuple[models.Resource, float, float]] = []
    freeform_targets: list[tuple[models.Resource, float, float]] = []
    for resource in all_resources:
        target = targets.get(resource.id)
        if not target or target <= 0 or resource.resource_def_key in unlimited_keys:
            continue
        current = (
            stock_by_def_key.get(resource.resource_def_key, 0)
            if resource.resource_def_key
            else totals_by_resource_id.get(resource.id, 0)
        )
        deficit = target - current
        if deficit <= 0:
            continue
        (catalog_targets if resource.resource_def_key else freeform_targets).append((resource, current, deficit))

    if not catalog_targets and not freeform_targets:
        return f"{title}\n{_t('recommendation_all_met', lang)}{legend}"

    preferred_recipes = material_chain.active_recipes_by_output(stock_by_building.keys())
    farmable_keys, imported_keys = _resource_key_flags(all_resources)
    # Per building: a recipe's inputs only come from the buildings running
    # it (see material_chain.resolve_requirements).
    stock_pool = {
        b.id: _totals_by_def_key([ResourceTotal(e.resource, e.quantity) for e in entries])
        for b, entries in stock_by_building.items()
    }
    chain_targets = sorted(catalog_targets, key=lambda x: crud.resolve_resource_name(x[0], catalog_lang))
    # Pass the full target here, not the already-subtracted `deficit` —
    # stock_pool still holds this resource's full current stock, and
    # resolve_requirements() does its own have-vs-needed netting against
    # that same pool. Passing `deficit` would net the current stock a
    # second time, so a Meta on a resource that already has some stock
    # under-counted (or even zeroed out) the real production need.
    result = material_chain.resolve_requirements(
        [(r.resource_def_key, targets[r.id]) for r, _current, _deficit in chain_targets],
        stock_pool,
        stock_by_building.keys(),
        preferred_recipes,
        farmable_keys,
        imported_keys,
        unlimited_keys,
    )

    lines = [title]

    meta_lines = [
        _t(
            "meta_line",
            lang,
            icon=f"{r.icon} " if r.icon else "",
            name=crud.resolve_resource_name(r, catalog_lang),
            current=_display_qty(current, r.resource_def_key),
            target=_display_qty(targets[r.id], r.resource_def_key),
            missing=_display_qty(deficit, r.resource_def_key),
        )
        for r, current, deficit in sorted(
            catalog_targets + freeform_targets, key=lambda x: crud.resolve_resource_name(x[0], catalog_lang)
        )
    ]
    lines.append("\n".join(f"• {m}" if bulleted else m for m in meta_lines))

    def output_name(bt_key: str, recipe_key: str) -> str:
        recipe = foxhole_data.get_recipe(bt_key, recipe_key)
        output_keys = [o["resource"] for o in recipe["outputs"] if o.get("resource")] if recipe else []
        if not output_keys:
            return recipe_key
        return ", ".join(foxhole_data.resource_display_name(k, catalog_lang) for k in output_keys)

    if result["production"]:
        time_estimate = material_chain.compute_production_time(result["production"], preferred_recipes)
        full, current = time_estimate["full"], time_estimate["current"]
        path_text = " → ".join(output_name(bt, rk) for bt, rk in full["critical_path"])
        current_text = (
            _t("total_time_current", lang, duration=format_duration(current["total_seconds"]))
            if time_estimate["has_current"] and current["total_seconds"] != full["total_seconds"]
            else ""
        )
        lines.append(
            _t(
                "total_time_line",
                lang,
                duration=format_duration(full["total_seconds"]),
                current=current_text,
                path=path_text,
            )
        )

        def timing(key: str, cycles: float, run: dict, cycle_seconds: int) -> str:
            return _t(
                key,
                lang,
                queues=_queues_text(run["queue_count"], lang),
                per_queue=_per_queue_text(cycles, run["queue_count"], run["rounds"], lang),
                cycle=format_cycle_time(cycle_seconds),
                duration=format_duration(run["seconds"]),
            )

        prod_lines = []
        for node, cycles in sorted(result["production"].items(), key=lambda kv: -kv[1]):
            bt_key, recipe_key = node
            info = time_estimate["nodes"][node]
            # Configured queues: show them, then the 5-queue estimate (the
            # reference) unless they already are 5 or more. Nothing
            # configured: just the 5-queue estimate.
            parts = []
            if info["configured"]:
                parts.append(timing("timing_current", cycles, info["current"], info["cycle_seconds"]))
            if not info["configured"] or info["configured"] < material_chain.FULL_QUEUES:
                parts.append(timing("timing_full", cycles, info["full"], info["cycle_seconds"]))
            prod_lines.append(
                _t(
                    "production_needed_item",
                    lang,
                    name=output_name(bt_key, recipe_key),
                    cycles=format_qty(cycles),
                    building=foxhole_data.building_display_name(bt_key, catalog_lang),
                    timing=" · ".join(parts),
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

    if result["production"] and not legend:
        legend = f"\n{_t('cycles_legend', lang)}"
    return "\n".join(lines) + legend


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
    totals = [t for t in totals if t.quantity > 0]
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
    targets: dict[int, float],
    now: datetime | None = None,
    lang: str = "pt-BR",
    catalog_lang: str | None = None,
) -> dict:
    now = now or datetime.now().astimezone()
    catalog_lang = catalog_lang or lang
    # Unlimited resources (Resource.unlimited, e.g. Water) are left out of the
    # report entirely: no stock line, no tank line, no total, no Meta — they
    # only matter as "always available" to the production math below.
    unlimited_keys = crud.unlimited_resource_keys(all_resources)
    stock_by_building = {
        building: [e for e in entries if e.resource.resource_def_key not in unlimited_keys]
        for building, entries in stock_by_building.items()
    }
    totals = _aggregate_resource_totals(stock_by_building)

    header_block = build_header_block(facility, now, lang)
    stock_block = build_stock_block(stock_by_building, now, lang, catalog_lang, unlimited_keys)
    recommendation_block = build_recommendation_block(
        stock_by_building, totals, all_resources, targets, lang, catalog_lang
    )

    markdown_content = "\n\n".join([header_block, stock_block, recommendation_block])

    # The Discord version consolidates every building into one facility-wide
    # total instead of repeating the per-building breakdown already shown in
    # "Estoque Atual" — kept as separate paragraphs (not folded into
    # markdown_content) so it can be persisted and re-split independently.
    # It also re-renders the recommendation with one bullet per line instead
    # of the dense " • "-joined run-on — much easier to read on Discord —
    # while leaving the in-app "Recomendação de Farm" block above untouched.
    totals_block = build_totals_block(stock_by_building, totals, lang, catalog_lang)
    discord_recommendation_block = build_recommendation_block(
        stock_by_building, totals, all_resources, targets, lang, catalog_lang, bulleted=True
    )
    discord_paragraphs = [header_block, totals_block, discord_recommendation_block]
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
            "stock": stock_block,
            "recommendation": recommendation_block,
        },
        "parts": parts,
        "snapshot": snapshot,
    }
