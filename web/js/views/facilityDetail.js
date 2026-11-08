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
    // Storage stations have no recipes: their rows are what the stockpile
    // accepts (MTS: large items + Cmat; RTS: loose raw resources).
    for (const key of foxholeType.accepts || []) {
      const def = foxholeResourceDefs[key];
      if (def) seen.set(key, { key, name: i18n.catalogName(def), search: `${def.name_pt || ""} ${def.name_en}`, icon: def.icon });
    }
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
        if (def && def.is_liquid && !keys.has(io.resource) && !isUnlimited(io.resource)) keys.set(io.resource, def);
      }
    }
    return [...keys.entries()];
  }

  // Resource.unlimited (e.g. Water): always available, so no tank to track.
  function isUnlimited(key) {
    const resource = allResources.find((r) => r.resource_def_key === key);
    return resource ? resource.unlimited : Boolean(foxholeResourceDefs[key] && foxholeResourceDefs[key].unlimited);
  }

  // Upgrade modules of a building type. Base recipes ("Base", "Base
  // (Uniforms)", none) are always available; a building installs at most one
  // upgrade, which adds its own recipes. A type with a single module (e.g.
  // Aircraft Maintenance Hangar) has nothing to choose.
  function isBaseModule(mod) {
    return !mod || mod.startsWith("Base");
  }
  function upgradeOptions(foxholeType) {
    if (!foxholeType) return [];
    const mods = [...new Set(foxholeType.recipes.map((r) => r.module || "Base"))];
    return mods.length > 1 ? mods.filter((m) => !isBaseModule(m)) : [];
  }
  // Saved upgrade, else inferred from a non-base recipe already in
  // production (buildings set up before the upgrade field existed).
  function buildingUpgrade(building, foxholeType) {
    const options = upgradeOptions(foxholeType);
    if (building.upgrade && options.includes(building.upgrade)) return building.upgrade;
    for (const slot of building.production_slots || []) {
      const recipe = foxholeType.recipes.find((r) => r.key === slot.recipe_key);
      if (recipe && options.includes(recipe.module)) return recipe.module;
    }
    return null;
  }
  function upgradeLabel(mod) {
    return mod.replace(/ Upgrade$/, "");
  }

  function resourceThumb(resourceId) {
    const resource = allResources.find((r) => r.id === resourceId);
    const def = resource && foxholeResourceDefs[resource.resource_def_key];
    return def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="h-8 w-8 inline-block object-contain align-middle" />` : "";
  }

  // Mirrors report_generator._display_qty(): a liquid's recipe qty is a real
  // unit count (converted from the wiki's Liters value server-side, see
  // foxhole_data.recipe_io_qty()), so show it back in Liters here too —
  // otherwise a fractional unit count like "0.2 Heavy Oil" would show up on
  // the building card instead of the "6L" a player actually recognizes.
  function displayQty(qty, resourceKey) {
    const def = resourceKey && foxholeResourceDefs[resourceKey];
    if (def && def.is_liquid && def.liters_per_unit) {
      return `${Math.round(qty * def.liters_per_unit)}L`;
    }
    return qty;
  }

  // Stock quantities with thousands separators ("21.900" / "21,900") — the
  // card's value column is right-aligned, so equal-width digits line up.
  function formatQty(qty) {
    return Number(qty).toLocaleString(i18n.getLang(), { maximumFractionDigits: 2 });
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

  // Mirrors report_generator.format_cycle_time: keeps the seconds of one
  // cycle ("1min30"), since it's the multiplier in the math shown.
  function formatCycleTime(seconds) {
    seconds = Math.round(seconds);
    if (seconds >= 3600) return formatDuration(seconds);
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (minutes && secs) return `${minutes}min${String(secs).padStart(2, "0")}`;
    if (minutes) return `${minutes}min`;
    return `${secs}s`;
  }

  function tabLink(tab, label, activeTab) {
    const isActive = tab === activeTab;
    const href = tab === "buildings" ? `#/facilities/${facilityId}` : `#/facilities/${facilityId}/${tab}`;
    return `<a href="${href}" class="px-3 py-1.5 rounded text-sm font-medium whitespace-nowrap ${
      isActive ? "bg-emerald-700 text-white" : "bg-zinc-900 text-zinc-400 hover:text-zinc-200"
    }">${label}</a>`;
  }

  // Hand the facility to another member (web mode). One way: the old owner
  // only becomes owner again if someone hands it back.
  async function openTransfer(app, facility, myId, activeTab) {
    let users;
    try {
      users = (await api.listUsers()).filter((u) => u.id !== myId && u.id !== facility.owner_id);
    } catch (err) {
      ui.toast(err.message, true);
      return;
    }
    ui.openModal(i18n.t("facilityDetail.transferTitle", { name: facility.name }), (body, close) => {
      if (!users.length) {
        body.innerHTML = `<p class="text-sm text-zinc-400">${i18n.t("facilityDetail.transferNoUsers")}</p>`;
        return;
      }
      body.innerHTML = `
        <p class="text-sm text-zinc-400 mb-3">${i18n.t(facility.private ? "facilityDetail.transferHelpPrivate" : "facilityDetail.transferHelp")}</p>
        <select class="transfer-user w-full bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-sm mb-3">
          <option value="">${i18n.t("facilityDetail.transferPick")}</option>
          ${users.map((u) => `<option value="${u.id}">${ui.escapeHtml(u.name)}</option>`).join("")}
        </select>
        <div class="flex justify-end gap-2">
          <button class="transfer-cancel px-3 py-1 rounded text-sm bg-zinc-800 hover:bg-zinc-700">${i18n.t("dashboard.webhookCancel")}</button>
          <button class="transfer-ok px-3 py-1 rounded text-sm bg-red-800 hover:bg-red-700 font-semibold" disabled>${i18n.t("facilityDetail.transferConfirmBtn")}</button>
        </div>`;
      const select = body.querySelector(".transfer-user");
      const ok = body.querySelector(".transfer-ok");
      select.addEventListener("change", () => (ok.disabled = !select.value));
      body.querySelector(".transfer-cancel").addEventListener("click", close);
      ok.addEventListener("click", async () => {
        const name = select.options[select.selectedIndex].text;
        if (!confirm(i18n.t("facilityDetail.transferConfirm", { name }))) return;
        try {
          await api.transferFacility(facility.id, Number(select.value));
          close();
          ui.toast(i18n.t("facilityDetail.transferDone", { name }));
          if (facility.private) location.hash = "#/";
          else render(app, facility.id, activeTab);
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    });
  }

  async function render(app, id, activeTab = "buildings") {
    facilityId = id;
    if (activeTab === "live") activeTab = "dashboard"; // old name of the tab, kept for saved links
    let facility;
    try {
      facility = await api.getFacility(facilityId);
    } catch (err) {
      app.innerHTML = `<p class="text-red-400">${i18n.t("facilityDetail.notFound")}</p>`;
      return;
    }

    // Private/shared only means something with login on (web mode); the
    // owner (or anyone, for a facility without owner yet) can switch it.
    const me = window.appMe || {};
    const myId = me.user ? me.user.id : null;
    const isOwner = !me.auth_enabled || !facility.owner_id || facility.owner_id === myId;
    const sharing = me.auth_enabled
      ? `<button id="toggle-private" ${isOwner ? "" : "disabled"}
            title="${i18n.t(facility.private ? "facilityDetail.privateHint" : "facilityDetail.sharedHint")}"
            class="text-xs border border-zinc-700 rounded px-2 py-1 ${isOwner ? "hover:border-zinc-500" : "opacity-60 cursor-default"}">${
            facility.private ? i18n.t("facilityDetail.private") : i18n.t("facilityDetail.shared")
          }</button>`
      : "";
    app.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
        <div class="min-w-0">
          <h1 class="text-xl font-bold">${ui.escapeHtml(facility.name)}</h1>
          ${facility.owner_name ? `<div class="text-xs text-zinc-500">${i18n.t("facilities.owner", { name: ui.escapeHtml(facility.owner_name) })}</div>` : ""}
        </div>
        <div class="flex gap-2">
          ${sharing}
          ${me.auth_enabled && isOwner ? `<button id="transfer-facility" class="text-xs text-zinc-300 hover:text-zinc-100 border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1">${i18n.t("facilityDetail.transfer")}</button>` : ""}
          <button id="rename-facility" class="text-xs text-zinc-300 hover:text-zinc-100 border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1">${i18n.t("facilityDetail.rename")}</button>
          <button id="delete-facility" ${isOwner ? "" : "hidden"} class="text-xs text-red-400 hover:text-red-300 border border-red-900 hover:border-red-600 rounded px-2 py-1">${i18n.t("facilityDetail.deleteFacility")}</button>
        </div>
      </div>
      <div class="flex flex-wrap gap-2 mb-6">
        ${tabLink("buildings", i18n.t("facilityDetail.tabBuildings"), activeTab)}
        ${tabLink("targets", i18n.t("facilityDetail.tabTargets"), activeTab)}
        ${tabLink("dashboard", i18n.t("facilityDetail.tabDashboard"), activeTab)}
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
      try {
        await api.deleteFacility(facilityId);
        location.hash = "#/";
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    const transferBtn = document.getElementById("transfer-facility");
    if (transferBtn) transferBtn.addEventListener("click", () => openTransfer(app, facility, myId, activeTab));

    const togglePrivate = document.getElementById("toggle-private");
    if (togglePrivate && isOwner) {
      togglePrivate.addEventListener("click", async () => {
        const next = !facility.private;
        if (!confirm(i18n.t(next ? "facilityDetail.makePrivateConfirm" : "facilityDetail.makeSharedConfirm"))) return;
        try {
          await api.updateFacility(facilityId, { private: next });
          render(app, facilityId, activeTab);
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    }

    allResources = await api.listResources(facilityId);
    foxholeBuildingTypes = await api.listFoxholeBuildingTypes();
    if (Object.keys(foxholeResourceDefs).length === 0) {
      const foxholeResources = await api.listFoxholeResources();
      foxholeResourceDefs = Object.fromEntries(foxholeResources.map((r) => [r.key, r]));
    }

    const tabContent = document.getElementById("tab-content");
    if (activeTab === "buildings") await renderBuildingsTab(tabContent);
    else if (activeTab === "targets") await views.targets.renderTargetsTab(tabContent, facilityId);
    else if (activeTab === "dashboard") await views.dashboard.renderDashboardTab(tabContent, facilityId);
    else if (activeTab === "report") await views.report.renderReportTab(tabContent, facilityId);
    else if (activeTab === "history") await views.report.renderHistoryTab(tabContent, facilityId);
  }

  async function renderBuildingsTab(container) {
    container.innerHTML = `
      <datalist id="resources-datalist">
        ${allResources.map((r) => `<option value="${ui.escapeHtml(r.name)}"></option>`).join("")}
      </datalist>
      <datalist id="locations-datalist"></datalist>
      <form id="new-building-form" class="grid grid-cols-1 sm:grid-cols-[220px_1fr_180px_auto] gap-2 mb-6">
        <select id="b-type" class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500">
          <option value="">${i18n.t("facilityDetail.freeBuilding")}</option>
          ${foxholeBuildingTypes.map((t) => `<option value="${t.key}">📖 ${ui.escapeHtml(i18n.catalogName(t))}</option>`).join("")}
        </select>
        <input id="b-name" placeholder="${i18n.t("facilityDetail.buildingNamePlaceholder")}"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="b-location" list="locations-datalist" placeholder="${i18n.t("facilityDetail.locationPlaceholder")}"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">${i18n.t("facilityDetail.addBuilding")}</button>
      </form>
      <div class="flex justify-end items-center gap-2 mb-2 text-xs text-zinc-500">
        <label for="b-grouping">${i18n.t("facilityDetail.groupBy")}</label>
        <select id="b-grouping" class="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-xs focus:outline-none focus:border-emerald-500">
          <option value="type">${i18n.t("facilityDetail.groupByType")}</option>
          <option value="upgrade">${i18n.t("facilityDetail.groupByUpgrade")}</option>
          <option value="location">${i18n.t("facilityDetail.groupByLocation")}</option>
          <option value="location_type">${i18n.t("facilityDetail.groupByLocationType")}</option>
        </select>
      </div>
      <div id="buildings-list" class="space-y-6"></div>
    `;

    // Per-viewer preference: "type" (default), "upgrade" (type + upgrade),
    // "location" or "location_type" (location + type).
    const GROUPINGS = ["type", "upgrade", "location", "location_type"];
    const groupingSelect = document.getElementById("b-grouping");
    try {
      const saved = localStorage.getItem("buildingGrouping");
      groupingSelect.value = GROUPINGS.includes(saved) ? saved : "type";
    } catch {}
    groupingSelect.addEventListener("change", () => {
      try {
        localStorage.setItem("buildingGrouping", groupingSelect.value);
      } catch {}
      renderBuildingsList();
    });

    const typeSelect = document.getElementById("b-type");
    const nameInput = document.getElementById("b-name");
    const locationInput = document.getElementById("b-location");

    document.getElementById("new-building-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = nameInput.value.trim() || null;
      const building_type_key = typeSelect.value || null;
      if (!name && !building_type_key) {
        ui.toast(i18n.t("facilityDetail.needNameOrType"), true);
        return;
      }
      try {
        const location = locationInput.value.trim() || null;
        await api.createBuilding(facilityId, { name, building_type_key, location });
        // Keep the location: buildings are usually added one spot at a time.
        e.target.reset();
        locationInput.value = location || "";
        renderBuildingsList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    // Buildings are grouped by type (Materials Factory, Coal Refinery, ...),
    // each group its own grid with a header — same-type buildings hold
    // similar items, so a group's rows come out even, and the page reads
    // like the facility itself. Groups follow the order of their first
    // building; inside a group, the user's drag order (`position`) holds.
    async function renderBuildingsList() {
      allResources = await api.listResources(facilityId);
      const listEl = document.getElementById("buildings-list");
      const buildings = await api.listBuildings(facilityId);
      if (buildings.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("facilityDetail.noBuildings")}</p>`;
        return;
      }
      const locations = [...new Set(buildings.map((b) => b.location).filter(Boolean))].sort();
      document.getElementById("locations-datalist").innerHTML = locations
        .map((l) => `<option value="${ui.escapeHtml(l)}"></option>`)
        .join("");

      const mode = groupingSelect.value;
      const byUpgrade = mode === "upgrade";
      const byLocation = mode === "location" || mode === "location_type";
      const byType = mode !== "location";
      const groups = new Map();
      for (const building of [...buildings].sort((a, b) => a.position - b.position)) {
        const typeKey = byType ? building.building_type_key || "" : "";
        const type = typeKey ? getFoxholeType(typeKey) : null;
        const upgrade = byUpgrade && type ? buildingUpgrade(building, type) : null;
        const location = byLocation ? building.location || "" : null;
        const key = `${location ?? ""}|${typeKey}|${upgrade || ""}`;
        if (!groups.has(key)) groups.set(key, { typeKey, upgrade, location, members: [] });
        groups.get(key).members.push(building);
      }
      const cards = await Promise.all(buildings.map((b) => buildingCard(b, renderBuildingsList)));
      const cardById = new Map(buildings.map((b, i) => [b.id, cards[i]]));

      listEl.innerHTML = "";
      // By location: locations in name order, "no location" last (stable
      // sort keeps the type order inside each location).
      const groupList = [...groups.values()];
      if (byLocation) {
        groupList.sort((a, b) => (a.location === "") - (b.location === "") || a.location.localeCompare(b.location));
      }
      for (const { typeKey, upgrade, location, members } of groupList) {
        const type = typeKey ? getFoxholeType(typeKey) : null;
        const hasUpgrades = byUpgrade && upgradeOptions(type).length > 0;
        const locationLabel = location === null ? null : `📍 ${location || i18n.t("facilityDetail.noLocation")}`;
        const typeLabel = type ? i18n.catalogName(type) : byType ? i18n.t("facilityDetail.groupOther") : null;
        const section = ui.el("section", {});
        section.appendChild(
          ui.el("div", { class: "flex items-center gap-2 mb-2" }, [
            type && type.icon ? ui.el("img", { src: type.icon, class: "w-7 h-7 object-contain opacity-80" }) : null,
            ui.el("h2", { class: "text-sm font-semibold text-zinc-300" }, [locationLabel, typeLabel].filter(Boolean).join(" · ")),
            hasUpgrades
              ? ui.el("span", { class: "text-xs text-sky-400" }, `· ${upgrade ? upgradeLabel(upgrade) : i18n.t("facilityDetail.noUpgrade")}`)
              : null,
            ui.el("span", { class: "text-xs text-zinc-600" }, `(${members.length})`),
          ])
        );
        const grid = ui.el("div", { class: "grid gap-3 grid-cols-[repeat(auto-fill,minmax(280px,1fr))]" });
        makeGridDroppable(listEl, grid);
        for (const building of members) {
          const card = cardById.get(building.id);
          makeCardDraggable(listEl, grid, card, building.id);
          grid.appendChild(card);
        }
        section.appendChild(grid);
        listEl.appendChild(section);
      }
    }

    // Drag a card by its ⠿ handle within its group. Dropping on a card takes
    // its place: dragged forward it lands after that card, backward before
    // it — so the first card can reach the last spot by dropping anywhere on
    // the last card (the old left/right-half rule made that a narrow target).
    // Dropping on empty grid space sends it to the end. A green bar on the
    // side shows where it will land. Positions are saved in page order.
    let draggingId = null;
    const MARK_BEFORE = `inset 4px 0 0 ${theme.rgb("emerald", 500)}`;
    const MARK_AFTER = `inset -4px 0 0 ${theme.rgb("emerald", 500)}`;

    function draggedIn(grid, exclude) {
      const dragged = draggingId && grid.querySelector(`:scope > [data-building-id="${draggingId}"]`);
      return dragged && dragged !== exclude ? dragged : null;
    }
    function clearMarks(listEl) {
      listEl.querySelectorAll(".building-card").forEach((c) => (c.style.boxShadow = ""));
    }
    async function savePositions(listEl) {
      const ordered = [...listEl.querySelectorAll("[data-building-id]")];
      await Promise.all(ordered.map((el, idx) => api.updateBuilding(el.dataset.buildingId, { position: idx })));
    }
    // Forward drag → after the target; backward → before it.
    function landsAfter(grid, dragged, card) {
      const cards = [...grid.children];
      return cards.indexOf(dragged) < cards.indexOf(card);
    }

    function makeGridDroppable(listEl, grid) {
      grid.addEventListener("dragover", (e) => {
        if (e.target !== grid || !draggedIn(grid)) return;
        e.preventDefault();
        clearMarks(listEl);
        const last = grid.lastElementChild;
        if (last && last.dataset.buildingId !== draggingId) last.style.boxShadow = MARK_AFTER;
      });
      grid.addEventListener("drop", async (e) => {
        if (e.target !== grid) return;
        const dragged = draggedIn(grid);
        clearMarks(listEl);
        if (!dragged) return;
        e.preventDefault();
        grid.appendChild(dragged);
        await savePositions(listEl);
      });
    }

    function makeCardDraggable(listEl, grid, card, buildingId) {
      card.dataset.buildingId = buildingId;
      const handle = card.querySelector(".drag-handle");
      handle.draggable = true;
      handle.addEventListener("dragstart", (e) => {
        draggingId = String(buildingId);
        e.dataTransfer.setData("text/plain", draggingId);
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setDragImage(card, 20, 20);
        card.classList.add("opacity-40");
      });
      handle.addEventListener("dragend", () => {
        draggingId = null;
        card.classList.remove("opacity-40");
        clearMarks(listEl);
      });
      card.addEventListener("dragover", (e) => {
        const dragged = draggedIn(grid, card);
        if (!dragged) return;
        e.preventDefault();
        clearMarks(listEl);
        card.style.boxShadow = landsAfter(grid, dragged, card) ? MARK_AFTER : MARK_BEFORE;
      });
      card.addEventListener("drop", async (e) => {
        const dragged = draggedIn(grid, card);
        clearMarks(listEl);
        if (!dragged) return;
        e.preventDefault();
        grid.insertBefore(dragged, landsAfter(grid, dragged, card) ? card.nextSibling : card);
        await savePositions(listEl);
      });
    }

    renderBuildingsList();
  }

  async function buildingCard(building, onChange) {
    // Layout (reworked Nov 2026 — the old one never lined up): no side icon
    // panel (the group header shows the type icon), one fixed-height row per
    // stock item with the name truncated instead of wrapping word by word,
    // and the action buttons pinned to the bottom (mt-auto) — the grid
    // stretches every card in a row to the same height, so rows line up.
    // Still no overflow-hidden on the card: it used to silently clip content.
    const card = ui.el("div", { class: "building-card bg-zinc-900 border border-zinc-800 rounded-lg flex flex-col min-w-0 h-full transition" });
    const stock = await api.getBuildingStock(building.id);
    const foxholeType = building.building_type_key ? getFoxholeType(building.building_type_key) : null;
    const canImportSave = !foxholeType || Boolean(foxholeType.storage);
    const liquidKeys = activeLiquidKeys(building, foxholeType);
    const liquidResourceIds = new Set(
      liquidKeys
        .map(([key]) => allResources.find((r) => r.resource_def_key === key)?.id)
        .filter((id) => id != null)
    );
    // Only the tank row is pulled into its own section below — a liquid's
    // crate/"normal" stock (overflow once the tank's full) shows here like
    // any other resource.
    // A 0 entry means "used to be here, ran out" (e.g. zeroed by a print):
    // kept in the log, not worth a line on the card.
    const nonLiquidStock = stock.filter(
      (s) => s.quantity > 0 && !(liquidResourceIds.has(s.resource_id) && s.storage === "tank")
    );
    const buildingDisplayName = i18n.buildingName(building, foxholeType);
    const upgrade = foxholeType ? buildingUpgrade(building, foxholeType) : null;
    const iconBtn = "p-1 rounded text-zinc-500 hover:text-zinc-100 hover:bg-zinc-800";
    // One line, each button as wide as its label and then stretched to fill
    // (flex-auto): a flex-wrap row broke into two lines at ~300px cards, and
    // equal columns cut "⚙️ Produção" to "Produ…".
    const actionBtn =
      "flex-auto min-w-0 text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-900 hover:border-emerald-600 rounded px-1.5 py-1 whitespace-nowrap truncate";

    card.innerHTML = `
      <div class="flex items-center gap-2 px-3 pt-3 pb-2 border-b border-zinc-800">
        <span class="drag-handle cursor-grab active:cursor-grabbing text-zinc-600 hover:text-zinc-300 select-none" title="${i18n.t("facilityDetail.dragToReorder")}">⠿</span>
        <div class="flex-1 min-w-0">
          <p class="font-semibold truncate" title="${ui.escapeHtml(buildingDisplayName)}">${ui.escapeHtml(buildingDisplayName)}</p>
          ${
            upgrade || building.location || building.save_pin_key
              ? `<p class="text-[11px] truncate" title="${ui.escapeHtml([upgrade, building.location, building.save_pin_key ? i18n.t("facilityDetail.pinLinked") : ""].filter(Boolean).join(" · "))}">${[
                  upgrade ? `<span class="text-sky-400">⬆ ${ui.escapeHtml(upgradeLabel(upgrade))}</span>` : "",
                  building.location ? `<span class="text-zinc-500">📍 ${ui.escapeHtml(building.location)}</span>` : "",
                  building.save_pin_key ? `<span class="text-emerald-600">📌</span>` : "",
                ]
                  .filter(Boolean)
                  .join(" ")}</p>`
              : ""
          }
        </div>
        <button class="edit-building ${iconBtn}" title="${i18n.t("common.edit")}">✎</button>
        <button class="delete-building ${iconBtn} hover:!text-red-400" title="${i18n.t("common.delete")}">🗑</button>
      </div>
      <div class="px-3 py-2 flex-1 min-w-0">
        ${
          nonLiquidStock.length === 0
            ? `<p class="text-sm text-zinc-600 py-1">${i18n.t("facilityDetail.noEntries")}</p>`
            : `<ul class="text-sm divide-y divide-zinc-800/70">${nonLiquidStock
                .map(
                  (s) => `
              <li class="group flex items-center gap-2 py-1 min-w-0"${s.created_by_name ? ` title="${ui.escapeHtml(i18n.t("facilityDetail.loggedBy", { name: s.created_by_name }))}"` : ""}>
                <span class="w-5 h-5 shrink-0 flex items-center justify-center">${resourceThumb(s.resource_id) || ui.escapeHtml(s.resource_icon)}</span>
                <button type="button" class="item-info truncate flex-1 min-w-0 text-left text-zinc-300 hover:text-emerald-300" data-resource-id="${s.resource_id}" title="${ui.escapeHtml(s.resource_name)} — ${i18n.t("item.openHint")}">${ui.escapeHtml(s.resource_name)}</button>
                <span class="tabular-nums font-semibold">${formatQty(s.quantity)}</span>
                <button class="delete-stock-item text-zinc-600 hover:text-red-400 px-0.5 opacity-0 group-hover:opacity-100 focus:opacity-100" data-resource-id="${s.resource_id}" data-storage="${s.storage}" data-name="${ui.escapeHtml(s.resource_name)}" title="${i18n.t("facilityDetail.deleteStockItem")}">✕</button>
              </li>`
                )
                .join("")}</ul>`
        }
        ${
          liquidKeys.length > 0
            ? `<div class="liquid-tank-section mt-2 rounded bg-zinc-950/60 border border-zinc-800 px-2 py-1.5">
                 <p class="text-[11px] text-zinc-500 mb-1">${i18n.t("facilityDetail.liquidTankTitle")}</p>
                 ${liquidKeys
                   .map(([key, def]) => {
                     const resource = allResources.find((r) => r.resource_def_key === key);
                     const entry = resource ? stock.find((s) => s.resource_id === resource.id && s.storage === "tank") : null;
                     const units = entry ? entry.quantity : 0;
                     const liters = Math.round(units * def.liters_per_unit);
                     const pct = Math.min(100, (liters / 5000) * 100);
                     return `
                     <div class="group flex items-center gap-2 text-xs py-0.5 min-w-0">
                       <span class="w-20 truncate text-zinc-300" title="${ui.escapeHtml(i18n.catalogName(def))}">${ui.escapeHtml(i18n.catalogName(def))}</span>
                       <div class="flex-1 min-w-[3rem] bg-zinc-800 rounded h-2 overflow-hidden">
                         <div class="bg-sky-600 h-full" style="width:${pct}%"></div>
                       </div>
                       <span class="tabular-nums text-zinc-500 whitespace-nowrap">${formatQty(liters)}/5000L</span>
                       <button class="add-liquid text-emerald-400 hover:text-emerald-300 font-bold px-0.5" data-key="${key}" data-current="${units}" title="${i18n.t("facilityDetail.liquidAdd")}">+</button>
                       ${
                         entry
                           ? `<button class="delete-stock-item text-zinc-600 hover:text-red-400 px-0.5 opacity-0 group-hover:opacity-100 focus:opacity-100" data-resource-id="${resource.id}" data-storage="tank" data-name="${ui.escapeHtml(i18n.catalogName(def))}" title="${i18n.t("facilityDetail.deleteStockItem")}">✕</button>`
                           : `<span class="w-3"></span>`
                       }
                     </div>`;
                   })
                   .join("")}
               </div>`
            : ""
        }
        <div class="production-status text-xs leading-snug text-zinc-400 mt-2 space-y-1"></div>
      </div>
      <div class="flex gap-1 px-3 py-2 border-t border-zinc-800 mt-auto">
        <button class="open-stock-modal ${actionBtn}" title="${i18n.t("facilityDetail.launchStock")}">${i18n.t("facilityDetail.btnStock")}</button>
        <button class="open-print-modal ${actionBtn}" title="${i18n.t("facilityDetail.sendPrint")}">${i18n.t("facilityDetail.btnPrint")}</button>
        ${
          // The game only caches stock in the save for pinned stockpiles (MTS, RTS…), never
          // for a factory: production buildings don't get the button. Untyped ones keep it.
          canImportSave
            ? `<button class="open-save-import-modal ${actionBtn}" title="${i18n.t("facilityDetail.importSave")}">${i18n.t("facilityDetail.btnSave")}</button>`
            : ""
        }
        ${
          foxholeType && foxholeType.recipes.length > 0
            ? `<button class="open-production-modal ${actionBtn}" title="${i18n.t("facilityDetail.production")}">${i18n.t("facilityDetail.btnProduction")}</button>`
            : ""
        }
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

    card.querySelectorAll(".item-info").forEach((btn) => {
      btn.addEventListener("click", () => {
        const resource = allResources.find((r) => String(r.id) === btn.dataset.resourceId);
        if (!resource) return;
        views.itemPanel.open(resource, foxholeResourceDefs[resource.resource_def_key] || null, onChange, facilityId);
      });
    });

    card.querySelectorAll(".delete-stock-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm(i18n.t("facilityDetail.deleteStockItemConfirm", { name: btn.dataset.name }))) return;
        try {
          await api.deleteBuildingStockItem(building.id, btn.dataset.resourceId, btn.dataset.storage);
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

    card.querySelector(".edit-building").addEventListener("click", () => {
      ui.openModal(`${i18n.t("common.edit")} — ${buildingDisplayName}`, (body, close) => {
        const label = foxholeType ? i18n.t("facilityDetail.editNicknamePrompt") : i18n.t("facilityDetail.editNamePrompt");
        const input = "w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";
        body.innerHTML = `
          <form class="grid gap-3">
            <label class="grid gap-1 text-xs text-zinc-400">${label}
              <input name="name" class="${input}" value="${ui.escapeHtml(building.name || "")}" />
            </label>
            <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("facilityDetail.locationLabel")}
              <input name="location" list="locations-datalist" class="${input}" value="${ui.escapeHtml(building.location || "")}"
                placeholder="${i18n.t("facilityDetail.locationPlaceholder")}" />
              <span class="text-zinc-600">${i18n.t("facilityDetail.locationHint")}</span>
            </label>
            <div><button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("common.save")}</button></div>
          </form>`;
        const form = body.querySelector("form");
        const nameField = form.querySelector('[name="name"]');
        const locationField = form.querySelector('[name="location"]');
        nameField.focus();
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          try {
            await api.updateBuilding(building.id, {
              name: nameField.value.trim() || null,
              location: locationField.value.trim() || null,
            });
            close();
            onChange();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      }, { maxWidth: "max-w-md" });
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

    card.querySelector(".open-save-import-modal")?.addEventListener("click", () => {
      ui.openModal(
        `${i18n.t("facilityDetail.importSave")} — ${buildingDisplayName}`,
        (body, close) => {
          views.saveImport.renderSaveImportUI(body, building, foxholeType, () => {
            onChange();
            close();
          });
        },
        { maxWidth: "max-w-2xl" }
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
    const n = estimate.queue_count;
    const queues = i18n.t(n === 1 ? "facilityDetail.production.queuesOne" : "facilityDetail.production.queuesMany", { n });
    if (estimate.cycles <= 0) {
      const missing = estimate.inputs_per_cycle.filter((i) => (i.available ?? 0) < i.qty);
      const needed = missing
        .map((i) =>
          i18n.t("facilityDetail.production.missingItem", {
            qty: displayQty(i.qty, i.resource),
            name: i.name,
            available: displayQty(i.available ?? 0, i.resource),
          })
        )
        .join(", ");
      return i18n.t("facilityDetail.production.insufficient", { queues, needed });
    }
    const eta = new Date(estimate.eta).toLocaleTimeString(i18n.getLang(), { hour: "2-digit", minute: "2-digit" });
    const outputs = estimate.outputs.map((o) => `${displayQty(o.qty, o.resource)} ${o.name}`).join(", ");
    // Same wording as report_generator.format_production_line: show the
    // math (cycles split across parallel queues × time per cycle), not just
    // a bare "N cycles, ready in X".
    const exact = estimate.cycles === estimate.rounds * n;
    let line = i18n.t("facilityDetail.production.line", {
      queues,
      cycles: estimate.cycles,
      per_queue:
        n === 1
          ? String(estimate.rounds)
          : i18n.t(exact ? "facilityDetail.production.perQueueExact" : "facilityDetail.production.perQueueUpto", {
              rounds: estimate.rounds,
            }),
      cycle: formatCycleTime(estimate.cycle_seconds),
      duration: formatDuration(estimate.time_seconds),
      eta,
      outputs,
    });
    const leftovers = estimate.leftovers.filter((l) => l.qty > 0);
    if (leftovers.length > 0) {
      line += i18n.t("facilityDetail.production.leftover", {
        leftovers: leftovers.map((l) => `${displayQty(l.qty, l.resource)} ${l.name}`).join(", "),
      });
    }
    return line;
  }

  function buildProductionForm(container, building, foxholeType, onChange) {
    const upgrades = upgradeOptions(foxholeType);
    let selectedUpgrade = buildingUpgrade(building, foxholeType);

    // Only Base + the installed upgrade's recipes. A recipe already in a
    // queue row that the chosen upgrade doesn't offer stays listed (marked
    // ⚠) so switching the upgrade never silently drops a row.
    function recipesByModule(keepKey) {
      const groups = {};
      for (const recipe of foxholeType.recipes) {
        const mod = recipe.module || "Base";
        const allowed = upgrades.length === 0 || isBaseModule(mod) || mod === selectedUpgrade;
        if (!allowed && recipe.key !== keepKey) continue;
        (groups[mod] = groups[mod] || []).push({ recipe, allowed });
      }
      return groups;
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
        Object.entries(recipesByModule(selectedKey))
          .map(
            ([mod, recipes]) => `
          <optgroup label="${ui.escapeHtml(mod)}">
            ${recipes
              .map(
                ({ recipe: r, allowed }) =>
                  `<option value="${r.key}" ${r.key === selectedKey ? "selected" : ""}>${allowed ? "" : "⚠ "}${ui.escapeHtml(recipeLabel(r))}${r.note ? " ⚠" : ""}</option>`
              )
              .join("")}
          </optgroup>`
          )
          .join("")
      );
    }

    container.innerHTML = `
      <div class="border border-zinc-800 rounded p-3 bg-zinc-950">
        ${
          upgrades.length > 0
            ? `<label class="flex flex-wrap items-center gap-2 text-xs text-zinc-400 mb-3">
                 ${i18n.t("facilityDetail.upgrade")}
                 <select class="building-upgrade bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500">
                   <option value="">${i18n.t("facilityDetail.noUpgrade")}</option>
                   ${upgrades.map((m) => `<option value="${ui.escapeHtml(m)}" ${m === selectedUpgrade ? "selected" : ""}>${ui.escapeHtml(upgradeLabel(m))}</option>`).join("")}
                 </select>
                 <span class="text-zinc-600">${i18n.t("facilityDetail.upgradeHint")}</span>
               </label>`
            : ""
        }
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

    const upgradeSelect = container.querySelector(".building-upgrade");
    if (upgradeSelect) {
      upgradeSelect.addEventListener("change", () => {
        selectedUpgrade = upgradeSelect.value || null;
        rowsEl.querySelectorAll(".slot-recipe").forEach((select) => {
          select.innerHTML = recipeOptionsHtml(select.value);
        });
      });
    }

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
        if (upgrades.length > 0 && (building.upgrade || null) !== selectedUpgrade) {
          await api.updateBuilding(building.id, { upgrade: selectedUpgrade });
        }
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
        ${resources.length > 12 ? `<input type="search" placeholder="${i18n.t("facilityDetail.filterItems")}"
          class="row-filter w-full mb-3 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500" />` : ""}
        <div class="predefined-rows grid gap-2 max-h-[55vh] overflow-y-auto pr-1"></div>
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
        <div class="flex items-center gap-2" data-name="${ui.escapeHtml(`${r.name} ${r.search || ""}`.toLowerCase())}">
          ${thumb}
          <span class="flex-1 min-w-0 truncate text-sm" title="${ui.escapeHtml(r.name)}">${ui.escapeHtml(r.name)}</span>
          <input placeholder="${i18n.t("facilityDetail.qtyPlaceholder")}" data-key="${r.key}" data-current-id="${current ? current.id : ""}"
            class="w-28 shrink-0 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-qty" />
        </div>`;
      })
      .join("");

    // Hides rows only: a quantity typed before filtering still gets saved.
    const filter = container.querySelector(".row-filter");
    if (filter) {
      filter.addEventListener("input", () => {
        const q = filter.value.trim().toLowerCase();
        rowsEl.querySelectorAll("[data-name]").forEach((row) => row.classList.toggle("hidden", !row.dataset.name.includes(q)));
      });
    }

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
