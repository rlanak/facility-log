window.views = window.views || {};

views.facilityDetail = (() => {
  let facilityId;
  let allResources = [];
  let foxholeBuildingTypes = [];
  let foxholeResourceDefs = {};

  function getFoxholeType(key) {
    return foxholeBuildingTypes.find((t) => t.key === key);
  }

  function resourcesForBuildingType(foxholeType) {
    const seen = new Map();
    for (const recipe of foxholeType.recipes) {
      for (const io of [...recipe.inputs, ...recipe.outputs]) {
        if (!io.resource || seen.has(io.resource)) continue;
        const def = foxholeResourceDefs[io.resource];
        // Liquids get BOTH the Tanque de Líquido section (tank storage, capped
        // at 5000L) AND a normal-form row here (crate storage, unlimited) —
        // once a liquid's tank is full, further production stacks as crates
        // on the shelf just like any other resource. See memory/liquid_tank_system.md.
        seen.set(io.resource, { key: io.resource, name: def ? i18n.catalogName(def) : io.resource, icon: def ? def.icon : null });
      }
    }
    return [...seen.values()].sort((a, b) => a.name.localeCompare(b.name));
  }

  // Which liquids a building currently has a tank for: derived from the
  // liquid resources used by whichever recipes the user has active in
  // production — not a separate setting. See memory/liquid_tank_system.md.
  function activeLiquidKeys(building, foxholeType) {
    if (!foxholeType) return [];
    const activeRecipeKeys = new Set((building.production_slots || []).map((s) => s.recipe_key));
    const keys = new Map();
    for (const recipe of foxholeType.recipes) {
      if (!activeRecipeKeys.has(recipe.key)) continue;
      for (const io of [...recipe.inputs, ...recipe.outputs]) {
        const def = io.resource && foxholeResourceDefs[io.resource];
        if (def && def.is_liquid && !keys.has(io.resource)) keys.set(io.resource, def);
      }
    }
    return [...keys.entries()];
  }

  function resourceThumb(resourceId) {
    const resource = allResources.find((r) => r.id === resourceId);
    const def = resource && foxholeResourceDefs[resource.resource_def_key];
    return def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="h-8 w-8 inline-block object-contain align-middle" />` : "";
  }

  function formatDuration(seconds) {
    seconds = Math.round(seconds);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours) return `${hours}h${String(minutes).padStart(2, "0")}`;
    if (minutes) return `${minutes}min`;
    return `${secs}s`;
  }

  function tabLink(tab, label, activeTab) {
    const isActive = tab === activeTab;
    const href = tab === "buildings" ? `#/facilities/${facilityId}` : `#/facilities/${facilityId}/${tab}`;
    return `<a href="${href}" class="px-3 py-1.5 rounded text-sm font-medium ${
      isActive ? "bg-emerald-700 text-white" : "bg-zinc-900 text-zinc-400 hover:text-zinc-200"
    }">${label}</a>`;
  }

  async function render(app, id, activeTab = "buildings") {
    facilityId = id;
    let facility;
    try {
      facility = await api.getFacility(facilityId);
    } catch (err) {
      app.innerHTML = `<p class="text-red-400">${i18n.t("facilityDetail.notFound")}</p>`;
      return;
    }

    app.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <h1 class="text-xl font-bold">${ui.escapeHtml(facility.name)}</h1>
        <div class="flex gap-2">
          <button id="rename-facility" class="text-xs text-zinc-300 hover:text-white border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1">${i18n.t("facilityDetail.rename")}</button>
          <button id="delete-facility" class="text-xs text-red-400 hover:text-red-300 border border-red-900 hover:border-red-600 rounded px-2 py-1">${i18n.t("facilityDetail.deleteFacility")}</button>
        </div>
      </div>
      <div class="flex gap-2 mb-6">
        ${tabLink("buildings", i18n.t("facilityDetail.tabBuildings"), activeTab)}
        ${tabLink("report", i18n.t("facilityDetail.tabReport"), activeTab)}
        ${tabLink("history", i18n.t("facilityDetail.tabHistory"), activeTab)}
      </div>
      <div id="tab-content"></div>
    `;

    document.getElementById("rename-facility").addEventListener("click", async () => {
      const name = prompt(i18n.t("facilityDetail.renamePrompt"), facility.name);
      if (!name || !name.trim()) return;
      await api.updateFacility(facilityId, { name: name.trim() });
      render(app, facilityId, activeTab);
    });

    document.getElementById("delete-facility").addEventListener("click", async () => {
      if (!confirm(i18n.t("facilityDetail.deleteConfirm"))) return;
      await api.deleteFacility(facilityId);
      location.hash = "#/";
    });

    allResources = await api.listResources();
    foxholeBuildingTypes = await api.listFoxholeBuildingTypes();
    if (Object.keys(foxholeResourceDefs).length === 0) {
      const foxholeResources = await api.listFoxholeResources();
      foxholeResourceDefs = Object.fromEntries(foxholeResources.map((r) => [r.key, r]));
    }

    const tabContent = document.getElementById("tab-content");
    if (activeTab === "buildings") await renderBuildingsTab(tabContent);
    else if (activeTab === "report") await views.report.renderReportTab(tabContent, facilityId);
    else if (activeTab === "history") await views.report.renderHistoryTab(tabContent, facilityId);
  }

  async function renderBuildingsTab(container) {
    container.innerHTML = `
      <datalist id="resources-datalist">
        ${allResources.map((r) => `<option value="${ui.escapeHtml(r.name)}"></option>`).join("")}
      </datalist>
      <form id="new-building-form" class="grid grid-cols-[220px_1fr_auto] gap-2 mb-6">
        <select id="b-type" class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500">
          <option value="">${i18n.t("facilityDetail.freeBuilding")}</option>
          ${foxholeBuildingTypes.map((t) => `<option value="${t.key}">📖 ${ui.escapeHtml(i18n.catalogName(t))}</option>`).join("")}
        </select>
        <input id="b-name" placeholder="${i18n.t("facilityDetail.buildingNamePlaceholder")}"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">${i18n.t("facilityDetail.addBuilding")}</button>
      </form>
      <div id="buildings-list" class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(320px,1fr))] items-start"></div>
    `;

    const typeSelect = document.getElementById("b-type");
    const nameInput = document.getElementById("b-name");

    document.getElementById("new-building-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim() || null;
      const building_type_key = typeSelect.value || null;
      if (!name && !building_type_key) {
        ui.toast(i18n.t("facilityDetail.needNameOrType"), true);
        return;
      }
      try {
        await api.createBuilding(facilityId, { name, building_type_key });
        e.target.reset();
        renderBuildingsList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    async function renderBuildingsList() {
      allResources = await api.listResources();
      const listEl = document.getElementById("buildings-list");
      const buildings = await api.listBuildings(facilityId);
      if (buildings.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("facilityDetail.noBuildings")}</p>`;
        return;
      }
      listEl.innerHTML = "";
      for (const building of buildings) {
        const card = await buildingCard(building, renderBuildingsList);
        makeCardDraggable(listEl, card, building.id);
        listEl.appendChild(card);
      }
    }

    function makeCardDraggable(listEl, card, buildingId) {
      card.dataset.buildingId = buildingId;
      const handle = card.querySelector(".drag-handle");
      if (handle) {
        handle.draggable = true;
        handle.addEventListener("dragstart", (e) => {
          e.dataTransfer.setData("text/plain", String(buildingId));
          e.dataTransfer.effectAllowed = "move";
          card.classList.add("opacity-40");
        });
        handle.addEventListener("dragend", () => card.classList.remove("opacity-40"));
      }
      card.addEventListener("dragover", (e) => e.preventDefault());
      card.addEventListener("drop", async (e) => {
        e.preventDefault();
        const draggedId = e.dataTransfer.getData("text/plain");
        if (!draggedId || draggedId === String(buildingId)) return;
        const draggedEl = listEl.querySelector(`[data-building-id="${draggedId}"]`);
        if (!draggedEl) return;
        const rect = card.getBoundingClientRect();
        const insertBefore = e.clientY - rect.top < rect.height / 2;
        listEl.insertBefore(draggedEl, insertBefore ? card : card.nextSibling);
        const cards = [...listEl.children];
        await Promise.all(cards.map((el, idx) => api.updateBuilding(el.dataset.buildingId, { position: idx })));
      });
    }

    renderBuildingsList();
  }

  async function buildingCard(building, onChange) {
    // No overflow-hidden here: it used to silently clip the header buttons
    // and stock-form rows whenever the card ended up narrower than their
    // content (any grid with 2+ cards) instead of letting them wrap. The
    // icon panel gets its own rounded-l-lg + overflow-hidden below so the
    // card's rounded corners still look right without relying on this.
    const card = ui.el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg flex flex-wrap" });
    const stock = await api.getBuildingStock(building.id);
    const foxholeType = building.building_type_key ? getFoxholeType(building.building_type_key) : null;
    const liquidKeys = activeLiquidKeys(building, foxholeType);
    const liquidResourceIds = new Set(
      liquidKeys
        .map(([key]) => allResources.find((r) => r.resource_def_key === key)?.id)
        .filter((id) => id != null)
    );
    // Only the tank row is pulled into its own section below — a liquid's
    // crate/"normal" stock (overflow once the tank's full) shows here like
    // any other resource.
    const nonLiquidStock = stock.filter((s) => !(liquidResourceIds.has(s.resource_id) && s.storage === "tank"));

    const iconPanel =
      foxholeType && foxholeType.icon
        ? `<div class="w-28 shrink-0 rounded-l-lg overflow-hidden bg-zinc-950 border-r border-zinc-800 flex items-center justify-center p-3">
             <img src="${ui.escapeHtml(foxholeType.icon)}" class="w-full h-auto max-h-24 object-contain" />
           </div>`
        : "";
    const showTypeBadge = foxholeType && building.name !== foxholeType.name_en;
    const buildingDisplayName = i18n.buildingName(building, foxholeType);

    card.innerHTML = `
      ${iconPanel}
      <div class="flex-1 min-w-0 p-4">
        <div class="flex items-start justify-between gap-2 flex-wrap">
          <div class="flex items-center flex-wrap min-w-0">
            <span class="font-semibold break-words">${ui.escapeHtml(buildingDisplayName)}</span>
            ${showTypeBadge ? `<span class="text-xs text-zinc-600 ml-2" title="${i18n.t("facilityDetail.foxholeType")}">📖 ${ui.escapeHtml(i18n.catalogName(foxholeType))}</span>` : ""}
          </div>
          <div class="flex items-center gap-2 flex-wrap shrink-0">
            <span class="drag-handle cursor-move text-zinc-600 hover:text-zinc-400 px-1" title="${i18n.t("facilityDetail.dragToReorder")}">⠿</span>
            <button class="edit-building text-xs text-zinc-300 hover:text-white border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1">${i18n.t("common.edit")}</button>
            <button class="delete-building text-xs text-red-400 hover:text-red-300 border border-red-900 hover:border-red-600 rounded px-2 py-1">${i18n.t("common.delete")}</button>
          </div>
        </div>
        <div class="text-sm text-zinc-300 mt-2">
          ${
            nonLiquidStock.length === 0
              ? `<span class="text-zinc-600">${i18n.t("facilityDetail.noEntries")}</span>`
              : nonLiquidStock
                  .map(
                    (s) =>
                      `<span class="mr-4 inline-flex items-center gap-1.5">${resourceThumb(s.resource_id) || ui.escapeHtml(s.resource_icon)} ${ui.escapeHtml(s.resource_name)}: <strong>${s.quantity}</strong></span>`
                  )
                  .join("")
          }
        </div>
        <div class="production-status text-sm text-zinc-400 mt-2"></div>
        ${
          liquidKeys.length > 0
            ? `<div class="liquid-tank-section border border-zinc-800 rounded p-2 mt-2">
                 <p class="text-xs text-zinc-500 mb-1.5">${i18n.t("facilityDetail.liquidTankTitle")}</p>
                 ${liquidKeys
                   .map(([key, def]) => {
                     const resource = allResources.find((r) => r.resource_def_key === key);
                     const entry = resource ? stock.find((s) => s.resource_id === resource.id && s.storage === "tank") : null;
                     const units = entry ? entry.quantity : 0;
                     const liters = Math.round(units * def.liters_per_unit);
                     const pct = Math.min(100, (liters / 5000) * 100);
                     return `
                     <div class="flex items-center gap-2 mb-1 text-sm">
                       <span class="w-28 truncate">${ui.escapeHtml(i18n.catalogName(def))}</span>
                       <div class="flex-1 bg-zinc-800 rounded h-3 overflow-hidden">
                         <div class="bg-sky-600 h-full" style="width:${pct}%"></div>
                       </div>
                       <span class="text-xs text-zinc-500 w-24 text-right">${liters}L / 5000L</span>
                       <button class="add-liquid text-emerald-400 hover:text-emerald-300 px-1 font-bold" data-key="${key}" data-current="${units}">+</button>
                     </div>`;
                   })
                   .join("")}
               </div>`
            : ""
        }
        <div class="flex gap-2 mt-3 flex-wrap">
          <button class="open-stock-modal text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800 hover:border-emerald-600 rounded px-2 py-1">${i18n.t("facilityDetail.launchStock")}</button>
          <button class="open-print-modal text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800 hover:border-emerald-600 rounded px-2 py-1">${i18n.t("facilityDetail.sendPrint")}</button>
          ${
            foxholeType
              ? `<button class="open-production-modal text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-800 hover:border-emerald-600 rounded px-2 py-1">${i18n.t("facilityDetail.production")}</button>`
              : ""
          }
        </div>
      </div>
    `;

    if (foxholeType && building.production_slots && building.production_slots.length > 0) {
      renderProductionStatus(card.querySelector(".production-status"), building);
    }

    card.querySelectorAll(".add-liquid").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const key = btn.dataset.key;
        const def = foxholeResourceDefs[key];
        const maxUnits = Math.floor(5000 / def.liters_per_unit);
        const raw = prompt(
          i18n.t("facilityDetail.liquidPrompt", { name: i18n.catalogName(def), max: maxUnits }),
          btn.dataset.current || ""
        );
        if (raw === null) return;
        let qty = raw.trim();
        if (!qty) return;

        // Tanks are shown/thought of in liters, but stock is tracked in
        // resource units (galões) — accept a trailing L and convert so the
        // user doesn't have to do that math by hand (e.g. "5000L" for a
        // full 50L/unit tank instead of typing "100").
        const litersMatch = qty.match(/^([\d.,]+)\s*[lL]$/);
        if (litersMatch) {
          const liters = parseFloat(litersMatch[1].replace(",", "."));
          if (isNaN(liters)) {
            ui.toast(i18n.t("resources.invalidNumber"), true);
            return;
          }
          qty = String(Math.round((liters / def.liters_per_unit) * 100) / 100);
        }

        try {
          await api.addBuildingStock(building.id, [
            { resource_name: def.name_en, quantity_raw: qty, resource_def_key: key, storage: "tank" },
          ]);
          onChange();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    });

    card.querySelector(".delete-building").addEventListener("click", async () => {
      if (!confirm(i18n.t("facilityDetail.deleteBuildingConfirm", { name: buildingDisplayName }))) return;
      await api.deleteBuilding(building.id);
      onChange();
    });

    card.querySelector(".edit-building").addEventListener("click", async () => {
      const label = foxholeType ? i18n.t("facilityDetail.editNicknamePrompt") : i18n.t("facilityDetail.editNamePrompt");
      const name = prompt(label, building.name);
      if (name === null) return;
      await api.updateBuilding(building.id, { name: name.trim() || null });
      onChange();
    });

    card.querySelector(".open-stock-modal").addEventListener("click", () => {
      ui.openModal(`${i18n.t("facilityDetail.launchStock")} — ${buildingDisplayName}`, (body, close) => {
        buildStockForm(body, building, foxholeType, () => {
          onChange();
          close();
        });
      });
    });

    card.querySelector(".open-print-modal").addEventListener("click", () => {
      ui.openModal(
        `${i18n.t("facilityDetail.sendPrint")} — ${buildingDisplayName}`,
        (body, close) => {
          views.print.renderCaptureUI(body, building, () => {
            onChange();
            close();
          });
        },
        { maxWidth: "max-w-3xl" }
      );
    });

    const productionBtn = card.querySelector(".open-production-modal");
    if (productionBtn) {
      productionBtn.addEventListener("click", () => {
        ui.openModal(`${i18n.t("facilityDetail.production")} — ${buildingDisplayName}`, (body, close) => {
          buildProductionForm(body, building, foxholeType, () => {
            onChange();
            close();
          });
        });
      });
    }

    return card;
  }

  async function renderProductionStatus(container, building) {
    let estimates;
    try {
      estimates = await api.getProductionEstimate(building.id);
    } catch (err) {
      return;
    }
    if (!estimates || estimates.length === 0) return;
    container.innerHTML = "";
    for (const estimate of estimates) {
      container.appendChild(ui.el("div", {}, formatProductionLine(estimate)));
    }
  }

  function formatProductionLine(estimate) {
    if (estimate.cycles <= 0) {
      const missing = estimate.inputs_per_cycle.filter((i) => (i.available ?? 0) < i.qty);
      const needed = missing
        .map((i) => i18n.t("facilityDetail.production.missingItem", { qty: i.qty, name: i.name, available: i.available ?? 0 }))
        .join(", ");
      return i18n.t("facilityDetail.production.insufficient", { queue: estimate.queue_count, needed });
    }
    const eta = new Date(estimate.eta).toLocaleTimeString(i18n.getLang(), { hour: "2-digit", minute: "2-digit" });
    const outputs = estimate.outputs.map((o) => `${o.qty} ${o.name}`).join(", ");
    let line = i18n.t("facilityDetail.production.line", {
      queue: estimate.queue_count,
      cycles: estimate.cycles,
      duration: formatDuration(estimate.time_seconds),
      eta,
      outputs,
    });
    const leftovers = estimate.leftovers.filter((l) => l.qty > 0);
    if (leftovers.length > 0) {
      line += i18n.t("facilityDetail.production.leftover", { leftovers: leftovers.map((l) => `${l.qty} ${l.name}`).join(", ") });
    }
    return line;
  }

  function buildProductionForm(container, building, foxholeType, onChange) {
    const recipesByModule = {};
    for (const recipe of foxholeType.recipes) {
      const mod = recipe.module || "Base";
      (recipesByModule[mod] = recipesByModule[mod] || []).push(recipe);
    }

    function recipeLabel(recipe) {
      const outputs = recipe.outputs
        .map((o) => `${o.qty ?? 1}x ${i18n.catalogName(foxholeResourceDefs[o.resource]) || o.resource}`)
        .join(" + ");
      return `${outputs} (${formatDuration(recipe.time_seconds)})`;
    }

    function recipeOptionsHtml(selectedKey) {
      return (
        `<option value="">${i18n.t("facilityDetail.noRecipe")}</option>` +
        Object.entries(recipesByModule)
          .map(
            ([mod, recipes]) => `
          <optgroup label="${ui.escapeHtml(mod)}">
            ${recipes
              .map(
                (r) =>
                  `<option value="${r.key}" ${r.key === selectedKey ? "selected" : ""}>${ui.escapeHtml(recipeLabel(r))}${r.note ? " ⚠" : ""}</option>`
              )
              .join("")}
          </optgroup>`
          )
          .join("")
      );
    }

    container.innerHTML = `
      <div class="border border-zinc-800 rounded p-3 bg-zinc-950">
        <div class="production-slot-rows grid gap-2 mb-2"></div>
        <button type="button" class="add-slot text-xs text-zinc-400 hover:text-zinc-200 mb-2">${i18n.t("facilityDetail.addQueue")}</button>
        <p class="slot-total text-xs text-zinc-500 mb-3"></p>
        <div>
          <button type="button" class="save-production bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-xs font-semibold">${i18n.t("facilityDetail.saveProduction")}</button>
        </div>
        <p class="text-xs text-zinc-500 mt-2">${i18n.t("facilityDetail.productionHint")}</p>
      </div>
    `;

    const rowsEl = container.querySelector(".production-slot-rows");
    const totalEl = container.querySelector(".slot-total");

    function updateTotal() {
      const total = [...rowsEl.querySelectorAll(".slot-queue")].reduce((sum, input) => sum + (parseInt(input.value, 10) || 0), 0);
      totalEl.textContent = i18n.t("facilityDetail.queueTotal", { total, max: foxholeType.queue_slots });
      totalEl.classList.toggle("text-red-400", total > foxholeType.queue_slots);
      totalEl.classList.toggle("text-zinc-500", total <= foxholeType.queue_slots);
    }

    function addSlotRow(recipeKey, queueCount) {
      const row = ui.el("div", { class: "flex gap-2 items-center" });
      row.innerHTML = `
        <select class="slot-recipe flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500">
          ${recipeOptionsHtml(recipeKey)}
        </select>
        <input type="number" min="1" max="${foxholeType.queue_slots}" value="${queueCount || 1}"
          class="slot-queue w-16 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500" />
        <button type="button" class="remove-slot text-zinc-500 hover:text-red-400 px-1">✕</button>
      `;
      row.querySelector(".remove-slot").addEventListener("click", () => {
        row.remove();
        updateTotal();
      });
      row.querySelector(".slot-queue").addEventListener("input", updateTotal);
      rowsEl.appendChild(row);
    }

    if (building.production_slots && building.production_slots.length > 0) {
      building.production_slots.forEach((slot) => addSlotRow(slot.recipe_key, slot.queue_count));
    } else {
      addSlotRow("", 1);
    }
    updateTotal();

    container.querySelector(".add-slot").addEventListener("click", () => {
      addSlotRow("", 1);
      updateTotal();
    });

    container.querySelector(".save-production").addEventListener("click", async () => {
      const slots = [...rowsEl.querySelectorAll(":scope > div")]
        .map((row) => ({
          recipe_key: row.querySelector(".slot-recipe").value,
          queue_count: parseInt(row.querySelector(".slot-queue").value, 10) || 0,
        }))
        .filter((slot) => slot.recipe_key && slot.queue_count > 0);
      try {
        await api.setBuildingProduction(building.id, { slots });
        ui.toast(i18n.t("facilityDetail.productionUpdated"));
        onChange();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  function buildStockForm(container, building, foxholeType, onChange) {
    if (foxholeType) {
      buildPredefinedStockForm(container, building, foxholeType, onChange);
    } else {
      buildFreeformStockForm(container, building, onChange);
    }
  }

  function buildPredefinedStockForm(container, building, foxholeType, onChange) {
    const resources = resourcesForBuildingType(foxholeType);
    const currentByKey = Object.fromEntries(
      allResources.filter((r) => r.resource_def_key).map((r) => [r.resource_def_key, r])
    );

    const hint = i18n.t("facilityDetail.predefinedHint", { ex1: "<code>25.7k</code>", ex2: "<code>1,8k</code>", ex3: "<code>32000</code>" });
    container.innerHTML = `
      <div class="border border-zinc-800 rounded p-3 bg-zinc-950">
        <div class="predefined-rows grid gap-2"></div>
        <div class="flex gap-2 mt-3">
          <button type="button" class="save-stock bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-xs font-semibold">${i18n.t("facilityDetail.saveStock")}</button>
        </div>
        <p class="text-xs text-zinc-500 mt-2">${hint}</p>
      </div>
    `;

    const rowsEl = container.querySelector(".predefined-rows");
    rowsEl.innerHTML = resources
      .map((r) => {
        const current = currentByKey[r.key];
        const thumb = r.icon
          ? `<img src="${ui.escapeHtml(r.icon)}" class="h-7 w-7 object-contain" />`
          : `<span class="w-7"></span>`;
        return `
        <div class="flex items-center gap-2">
          ${thumb}
          <span class="flex-1 min-w-0 truncate text-sm" title="${ui.escapeHtml(r.name)}">${ui.escapeHtml(r.name)}</span>
          <input placeholder="${i18n.t("facilityDetail.qtyPlaceholder")}" data-key="${r.key}" data-current-id="${current ? current.id : ""}"
            class="w-28 shrink-0 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-qty" />
        </div>`;
      })
      .join("");

    container.querySelector(".save-stock").addEventListener("click", async () => {
      const entries = [];
      rowsEl.querySelectorAll(".row-qty").forEach((input) => {
        const qty = input.value.trim();
        if (!qty) return;
        const def = foxholeResourceDefs[input.dataset.key];
        const current = allResources.find((r) => String(r.id) === input.dataset.currentId);
        entries.push({
          resource_name: current ? current.name : def.name_en,
          quantity_raw: qty,
          resource_def_key: input.dataset.key,
          storage: "normal",
        });
      });
      if (entries.length === 0) {
        ui.toast(i18n.t("facilityDetail.fillOneQty"), true);
        return;
      }
      try {
        await api.addBuildingStock(building.id, entries);
        ui.toast(i18n.t("facilityDetail.stockSaved"));
        onChange();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  function buildFreeformStockForm(container, building, onChange) {
    const hint = i18n.t("facilityDetail.freeformHint", { ex1: "<code>25.7k</code>", ex2: "<code>1,8k</code>", ex3: "<code>32000</code>" });
    container.innerHTML = `
      <div class="border border-zinc-800 rounded p-3 bg-zinc-950">
        <div class="stock-rows space-y-2"></div>
        <button type="button" class="add-row text-xs text-zinc-400 hover:text-zinc-200 mt-2">${i18n.t("facilityDetail.addRow")}</button>
        <div class="flex gap-2 mt-3">
          <button type="button" class="save-stock bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-xs font-semibold">${i18n.t("facilityDetail.saveStock")}</button>
        </div>
        <p class="text-xs text-zinc-500 mt-2">${hint}</p>
      </div>
    `;

    const rowsEl = container.querySelector(".stock-rows");

    function addRow() {
      const row = ui.el("div", { class: "flex gap-2" });
      row.innerHTML = `
        <input list="resources-datalist" placeholder="${i18n.t("facilityDetail.resourcePlaceholder")}"
          class="flex-1 min-w-0 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-resource" />
        <input placeholder="${i18n.t("facilityDetail.qtyPlaceholder")}"
          class="w-28 shrink-0 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-qty" />
        <button type="button" class="remove-row text-zinc-500 hover:text-red-400 px-2">✕</button>
      `;
      row.querySelector(".remove-row").addEventListener("click", () => row.remove());
      rowsEl.appendChild(row);
    }

    container.querySelector(".add-row").addEventListener("click", addRow);
    addRow();
    addRow();
    addRow();

    container.querySelector(".save-stock").addEventListener("click", async () => {
      const entries = [];
      rowsEl.querySelectorAll(":scope > div").forEach((row) => {
        const name = row.querySelector(".row-resource").value.trim();
        const qty = row.querySelector(".row-qty").value.trim();
        if (name && qty) entries.push({ resource_name: name, quantity_raw: qty });
      });
      if (entries.length === 0) {
        ui.toast(i18n.t("facilityDetail.fillOneRow"), true);
        return;
      }
      try {
        await api.addBuildingStock(building.id, entries);
        ui.toast(i18n.t("facilityDetail.stockSaved"));
        onChange();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  return { render };
})();
