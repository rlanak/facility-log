window.views = window.views || {};

// "Metas" tab of a facility: how much of each item the facility wants to
// keep (all buildings summed). The report works out what's missing down the
// production chain to get there. Per facility since 02/11/2026 — before it
// was one global number per item on the old "Catálogo de Recursos" page.
views.targets = (() => {
  const CATEGORY_ORDER = [
    "materials",
    "supplies",
    "heavy_ammo",
    "heavy_arms",
    "small_arms",
    "utility",
    "medical",
    "uniforms",
    "parts",
  ];

  function formatQty(qty) {
    return Math.round(qty).toLocaleString(i18n.getLang());
  }

  // Liquids are thought of in liters (like the report and the tanks); stock
  // and targets are stored in units, so convert on the way in and out.
  function toShown(units, def) {
    return def && def.is_liquid ? units * def.liters_per_unit : units;
  }

  // "3000", "3k", "1,5k", "5000L" → units; null = empty (remove); NaN = invalid.
  function parseAmount(text, def) {
    let s = text.trim().toLowerCase().replace(/\s+/g, "").replace(",", ".");
    if (!s) return null;
    s = s.replace(/l$/, "");
    let mult = 1;
    if (s.endsWith("k")) {
      mult = 1000;
      s = s.slice(0, -1);
    }
    if (!/^\d+(\.\d+)?$/.test(s)) return NaN;
    const shown = parseFloat(s) * mult;
    return def && def.is_liquid ? Math.round((shown / def.liters_per_unit) * 100) / 100 : shown;
  }

  async function renderTargetsTab(container, facilityId) {
    container.innerHTML = `
      <div class="max-w-4xl">
        <p class="text-sm text-zinc-400 mb-4">${i18n.t("targets.intro")}</p>
        <div class="relative mb-4">
          <input id="target-search" autocomplete="off" placeholder="${i18n.t("targets.searchPlaceholder")}"
            class="w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
          <div id="target-results" class="hidden absolute z-20 left-0 right-0 mt-1 max-h-80 overflow-y-auto bg-zinc-900 border border-zinc-700 rounded shadow-xl"></div>
        </div>
        <div id="target-pending"></div>
        <div id="targets-list"></div>
      </div>`;

    const searchEl = document.getElementById("target-search");
    const resultsEl = document.getElementById("target-results");
    const pendingEl = document.getElementById("target-pending");
    const listEl = document.getElementById("targets-list");

    const foxholeResources = await api.listFoxholeResources();
    const defsByKey = Object.fromEntries(foxholeResources.map((r) => [r.key, r]));
    let resources = [];
    let targets = [];

    // One searchable list: every catalog item plus free-typed items the
    // player created that aren't in the catalog.
    function searchItems() {
      const items = foxholeResources.map((def) => ({
        key: `def:${def.key}`,
        def,
        resource: resources.find((r) => r.resource_def_key === def.key) || null,
        label: i18n.catalogName(def),
        alt: def.name_en,
        category: def.category || "materials",
      }));
      for (const r of resources.filter((r) => !r.resource_def_key)) {
        items.push({ key: `res:${r.id}`, def: null, resource: r, label: r.nickname || r.name, alt: r.name, category: "other" });
      }
      return items;
    }

    function renderResults() {
      const q = searchEl.value.trim().toLowerCase();
      if (!q) {
        resultsEl.classList.add("hidden");
        return;
      }
      const withTarget = new Set(targets.map((t) => t.resource.id));
      const matches = searchItems()
        .filter((it) => !(it.resource && withTarget.has(it.resource.id)))
        .filter(
          (it) =>
            it.label.toLowerCase().includes(q) ||
            it.alt.toLowerCase().includes(q) ||
            (it.resource && (it.resource.nickname || "").toLowerCase().includes(q))
        )
        .sort(
          (a, b) =>
            (CATEGORY_ORDER.indexOf(a.category) + 1 || 99) - (CATEGORY_ORDER.indexOf(b.category) + 1 || 99) ||
            a.label.localeCompare(b.label)
        )
        .slice(0, 40);
      resultsEl.classList.remove("hidden");
      if (matches.length === 0) {
        resultsEl.innerHTML = `<p class="text-xs text-zinc-500 p-3">${i18n.t("targets.searchEmpty")}</p>`;
        return;
      }
      resultsEl.innerHTML = matches
        .map(
          (it) => `
          <button type="button" data-key="${it.key}" class="pick w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-zinc-800">
            <span class="w-7 h-7 shrink-0 flex items-center justify-center">${it.def && it.def.icon ? `<img src="${ui.escapeHtml(it.def.icon)}" class="max-h-7 max-w-7 object-contain" />` : "•"}</span>
            <span class="flex-1 min-w-0 truncate">${ui.escapeHtml(it.label)}</span>
            <span class="text-xs text-zinc-600 whitespace-nowrap">${i18n.t(`category.${it.category}`)}</span>
          </button>`
        )
        .join("");
      resultsEl.querySelectorAll(".pick").forEach((btn) => {
        btn.addEventListener("click", () => {
          const item = searchItems().find((it) => it.key === btn.dataset.key);
          searchEl.value = "";
          resultsEl.classList.add("hidden");
          renderPending(item);
        });
      });
    }

    // Picked item waiting for its number.
    function renderPending(item) {
      const unit = item.def && item.def.is_liquid ? "L" : "";
      pendingEl.innerHTML = `
        <form class="flex flex-wrap items-center gap-2 mb-4 rounded-lg border border-emerald-800 bg-emerald-950/20 px-3 py-2">
          ${item.def && item.def.icon ? `<img src="${ui.escapeHtml(item.def.icon)}" class="h-8 w-8 object-contain" />` : ""}
          <span class="text-sm font-medium flex-1 min-w-[8rem]">${ui.escapeHtml(item.label)}</span>
          <label class="text-xs text-zinc-400 flex items-center gap-2">${i18n.t("targets.metaLabel")}
            <input name="amount" placeholder="${unit ? "5000L" : "3000"}" class="w-28 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm tabular-nums focus:outline-none focus:border-emerald-500" />
          </label>
          <button class="bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-sm font-semibold">${i18n.t("targets.add")}</button>
          <button type="button" class="cancel text-zinc-500 hover:text-zinc-200 text-sm px-1">✕</button>
        </form>`;
      const form = pendingEl.querySelector("form");
      const amountEl = form.querySelector('[name="amount"]');
      amountEl.focus();
      form.querySelector(".cancel").addEventListener("click", () => (pendingEl.innerHTML = ""));
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const amount = parseAmount(amountEl.value, item.def);
        if (amount === null || Number.isNaN(amount) || amount <= 0) {
          ui.toast(i18n.t("resources.invalidNumber"), true);
          return;
        }
        try {
          await api.setFacilityTarget(facilityId, {
            resource_id: item.resource ? item.resource.id : null,
            resource_def_key: item.resource ? null : item.def.key,
            target_max: amount,
          });
          pendingEl.innerHTML = "";
          await refresh();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    }

    function renderList() {
      if (targets.length === 0) {
        listEl.innerHTML = `<p class="text-sm text-zinc-500 border border-dashed border-zinc-800 rounded-lg p-6 text-center">${i18n.t("targets.empty")}</p>`;
        return;
      }
      const rows = targets
        .map((t) => {
          const def = t.resource.resource_def_key ? defsByKey[t.resource.resource_def_key] : null;
          const unit = def && def.is_liquid ? "L" : "";
          const target = toShown(t.target_max, def);
          const current = toShown(t.current, def);
          const missing = Math.max(0, target - current);
          const pct = Math.min(100, target > 0 ? (current / target) * 100 : 100);
          return { t, def, unit, target, current, missing, pct, name: i18n.resourceName(t.resource, defsByKey) };
        })
        // Furthest from the target first; met targets, then abundant items
        // (ignored by the report), at the end.
        .sort(
          (a, b) =>
            a.t.resource.unlimited - b.t.resource.unlimited || a.pct - b.pct || a.name.localeCompare(b.name)
        );

      listEl.innerHTML = `
        <div class="rounded-lg border border-zinc-800 overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-zinc-900 text-xs text-zinc-500">
              <tr>
                <th class="text-left font-normal px-2 sm:px-3 py-2">${i18n.t("targets.colItem")}</th>
                <th class="text-right font-normal px-2 sm:px-3 py-2">${i18n.t("targets.colStock")}</th>
                <th class="text-right font-normal px-2 sm:px-3 py-2">${i18n.t("targets.colTarget")}</th>
                <th class="text-right font-normal px-2 sm:px-3 py-2">${i18n.t("targets.colMissing")}</th>
                <th class="hidden sm:table-cell px-3 py-2 w-32"></th>
                <th class="w-8"></th>
              </tr>
            </thead>
            <tbody class="divide-y divide-zinc-800">
              ${rows
                .map(
                  (r) => `
                <tr class="group bg-zinc-950/40">
                  <td class="px-2 sm:px-3 py-1.5">
                    <button type="button" data-id="${r.t.resource.id}" class="item-info flex items-center gap-2 min-w-0 text-left hover:text-emerald-300" title="${i18n.t("item.openHint")}">
                      <span class="w-7 h-7 shrink-0 flex items-center justify-center">${r.def && r.def.icon ? `<img src="${ui.escapeHtml(r.def.icon)}" class="max-h-7 max-w-7 object-contain" />` : "•"}</span>
                      <span class="min-w-0">
                        <span class="block break-words">${ui.escapeHtml(r.name)}</span>
                        ${views.itemPanel.originBadge(r.t.resource)}
                      </span>
                    </button>
                  </td>
                  <td class="px-2 sm:px-3 py-1.5 text-right tabular-nums text-zinc-400 whitespace-nowrap">${formatQty(r.current)}${r.unit}</td>
                  <td class="px-2 sm:px-3 py-1.5 text-right">
                    <input data-id="${r.t.resource.id}" value="${Math.round(r.target * 100) / 100}${r.unit}"
                      class="target-input w-20 sm:w-24 bg-transparent border border-transparent hover:border-zinc-700 focus:border-emerald-500 focus:bg-zinc-900 rounded px-2 py-1 text-right tabular-nums font-semibold focus:outline-none" />
                  </td>
                  <td class="px-2 sm:px-3 py-1.5 text-right tabular-nums whitespace-nowrap ${r.t.resource.unlimited ? "text-zinc-600" : r.missing > 0 ? "text-amber-400" : "text-emerald-500"}">${r.missing > 0 ? `${formatQty(r.missing)}${r.unit}` : "✓"}</td>
                  <td class="hidden sm:table-cell px-3 py-1.5">
                    <div class="bg-zinc-800 rounded h-2 overflow-hidden" title="${Math.round(r.pct)}%">
                      <div class="${r.pct >= 100 ? "bg-emerald-600" : "bg-amber-500"} h-full" style="width:${r.pct}%"></div>
                    </div>
                  </td>
                  <td class="pr-2 text-right">
                    <button data-id="${r.t.resource.id}" class="remove-target text-zinc-600 hover:text-red-400 opacity-0 group-hover:opacity-100 focus:opacity-100 px-1" title="${i18n.t("targets.remove")}">✕</button>
                  </td>
                </tr>
                ${r.t.resource.unlimited ? `<tr><td colspan="6" class="px-3 pb-2 text-xs text-sky-500">${i18n.t("targets.unlimitedNote")}</td></tr>` : ""}`
                )
                .join("")}
            </tbody>
          </table>
        </div>
        <p class="text-xs text-zinc-600 mt-2">${i18n.t("targets.editHint")}</p>`;

      listEl.querySelectorAll(".target-input").forEach((inputEl) => {
        const initial = inputEl.value;
        inputEl.addEventListener("keydown", (e) => {
          if (e.key === "Enter") inputEl.blur();
          if (e.key === "Escape") {
            inputEl.value = initial;
            inputEl.blur();
          }
        });
        inputEl.addEventListener("change", async () => {
          const target = targets.find((t) => String(t.resource.id) === inputEl.dataset.id);
          const def = target.resource.resource_def_key ? defsByKey[target.resource.resource_def_key] : null;
          const amount = parseAmount(inputEl.value, def);
          if (Number.isNaN(amount)) {
            ui.toast(i18n.t("resources.invalidNumber"), true);
            inputEl.value = initial;
            return;
          }
          if (amount === null && !confirm(i18n.t("targets.removeConfirm"))) {
            inputEl.value = initial;
            return;
          }
          try {
            await api.setFacilityTarget(facilityId, { resource_id: target.resource.id, target_max: amount });
            await refresh();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      });

      listEl.querySelectorAll(".remove-target").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!confirm(i18n.t("targets.removeConfirm"))) return;
          await api.setFacilityTarget(facilityId, { resource_id: Number(btn.dataset.id), target_max: null });
          await refresh();
        });
      });

      listEl.querySelectorAll(".item-info").forEach((btn) => {
        btn.addEventListener("click", () => {
          const resource = targets.find((t) => String(t.resource.id) === btn.dataset.id).resource;
          views.itemPanel.open(resource, defsByKey[resource.resource_def_key] || null, refresh, facilityId);
        });
      });
    }

    async function refresh() {
      [resources, targets] = await Promise.all([api.listResources(facilityId), api.listFacilityTargets(facilityId)]);
      renderList();
    }

    searchEl.addEventListener("input", renderResults);
    searchEl.addEventListener("focus", renderResults);
    searchEl.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        searchEl.value = "";
        resultsEl.classList.add("hidden");
      }
    });
    document.addEventListener("click", function hide(e) {
      if (!document.body.contains(searchEl)) return document.removeEventListener("click", hide);
      if (!e.target.closest("#target-results") && e.target !== searchEl) resultsEl.classList.add("hidden");
    });

    await refresh();
  }

  return { renderTargetsTab };
})();
