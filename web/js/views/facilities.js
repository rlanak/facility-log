window.views = window.views || {};

// Home: one card per facility with a glance at it — which structures it
// has, production queues running/stopped and how close the Metas are (same
// projection as the Dashboard tab, fetched per card after the list shows).
views.facilities = (() => {
  async function render(app) {
    app.innerHTML = `
      <div class="flex items-center gap-3 mb-4">
        <h1 class="text-2xl font-bold uppercase tracking-wide">${i18n.t("facilities.title")}</h1>
        <span class="flex-1 h-px bg-zinc-800"></span>
      </div>
      <form id="new-facility-form" class="flex gap-2 mb-6">
        <input id="new-facility-name" required placeholder="${i18n.t("facilities.namePlaceholder")}"
          class="flex-1 min-w-0 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="inline-flex items-center gap-1.5 bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">${ui.icon("plus")}${i18n.t("facilities.add")}</button>
      </form>
      <div id="facilities-list" class="grid gap-4 sm:grid-cols-2"></div>
    `;

    document.getElementById("new-facility-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const input = document.getElementById("new-facility-name");
      const name = input.value.trim();
      if (!name) return;
      try {
        await api.createFacility({ name });
        input.value = "";
        renderList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    async function renderList() {
      const listEl = document.getElementById("facilities-list");
      listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("facilities.loading")}</p>`;
      const [facilities, types] = await Promise.all([api.listFacilities(), api.listFoxholeBuildingTypes().catch(() => [])]);
      if (facilities.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("facilities.empty")}</p>`;
        return;
      }
      const typeByKey = Object.fromEntries(types.map((t) => [t.key, t]));
      listEl.innerHTML = "";
      for (const f of facilities) {
        const card = ui.el("a", {
          href: `#/facilities/${f.id}`,
          class:
            "group flex flex-col bg-zinc-900 border border-zinc-800 border-t-2 border-t-emerald-800 rounded-lg p-4 hover:border-emerald-700 transition min-w-0",
        });
        card.innerHTML = `
          <div class="flex items-start gap-2 min-w-0">
            <div class="flex-1 min-w-0">
              <div class="font-display text-xl font-bold uppercase tracking-wide leading-tight truncate group-hover:text-emerald-300" title="${ui.escapeHtml(f.name)}">${ui.escapeHtml(f.name)}</div>
              ${f.owner_name ? `<div class="text-xs text-zinc-500 mt-0.5">${i18n.t("facilities.owner", { name: ui.escapeHtml(f.owner_name) })}</div>` : ""}
            </div>
            ${f.private ? `<span class="text-zinc-500" title="${i18n.t("facilities.privateHint")}">${ui.icon("lock")}</span>` : ""}
          </div>
          <div class="summary mt-3 flex-1"><div class="h-16 rounded bg-zinc-800/40 animate-pulse"></div></div>
          <div class="text-[11px] text-zinc-500 mt-3">${i18n.t("facilities.updatedAt", { date: i18n.formatDateTime(f.updated_at) })}</div>
        `;
        listEl.appendChild(card);
        api
          .getDashboard(f.id)
          .then((data) => (card.querySelector(".summary").innerHTML = summaryHtml(data, typeByKey)))
          .catch(() => (card.querySelector(".summary").innerHTML = ""));
      }
    }

    renderList();
  }

  function summaryHtml(data, typeByKey) {
    const buildings = data.buildings || [];
    if (!buildings.length) return `<p class="text-sm text-zinc-500">${i18n.t("facilities.noBuildings")}</p>`;

    // Structures it has: icon + count per type.
    const counts = new Map();
    for (const b of buildings) counts.set(b.building_type_key || "", (counts.get(b.building_type_key || "") || 0) + 1);
    const strip = [...counts.entries()]
      .map(([key, n]) => {
        const t = typeByKey[key];
        const name = t ? i18n.catalogName(t) : i18n.t("facilityDetail.groupOther");
        const img = t && t.icon ? `<img src="${ui.escapeHtml(t.icon)}" class="w-7 h-7 object-contain" />` : ui.icon("boxes", "w-5 h-5 text-zinc-500");
        return `<span class="relative inline-flex items-center justify-center w-10 h-10 rounded-md bg-zinc-950/60 border border-zinc-800" title="${ui.escapeHtml(name)}">${img}${
          n > 1 ? `<span class="absolute -top-1.5 -right-1.5 text-[10px] font-bold bg-zinc-700 text-zinc-100 rounded-full px-1.5 leading-4">${n}</span>` : ""
        }</span>`;
      })
      .join("");

    const slots = buildings.flatMap((b) => b.slots || []);
    const running = slots.filter((s) => s.running).length;
    const stopped = slots.length - running;
    const stat = (iconName, value, label, cls) =>
      `<div class="flex items-center gap-2 min-w-0"><span class="${cls}">${ui.icon(iconName, "w-4 h-4")}</span><span class="font-display text-lg font-semibold leading-none">${value}</span><span class="text-xs text-zinc-500 truncate">${label}</span></div>`;
    const stats = [
      slots.length ? stat("factory", running, i18n.t("facilities.running"), running ? "text-emerald-400" : "text-zinc-600") : "",
      slots.length ? stat("alert", stopped, i18n.t("facilities.stopped"), stopped ? "text-red-400" : "text-zinc-600") : "",
    ].join("");

    const targets = data.targets || [];
    let goals = "";
    if (targets.length) {
      const met = targets.filter((t) => t.projected >= t.target).length;
      const avg = Math.round((targets.reduce((sum, t) => sum + Math.min(1, t.target ? t.projected / t.target : 1), 0) / targets.length) * 100);
      goals = `
        <div class="mt-3">
          <div class="flex items-center justify-between text-xs mb-1">
            <span class="inline-flex items-center gap-1 text-zinc-400">${ui.icon("target", "w-3.5 h-3.5")}${i18n.t("facilities.goals", { met, total: targets.length })}</span>
            <span class="font-display text-sm font-semibold ${avg >= 100 ? "text-emerald-400" : "text-zinc-300"}">${avg}%</span>
          </div>
          <div class="h-1.5 rounded-full bg-zinc-800 overflow-hidden"><div class="h-full ${avg >= 100 ? "bg-emerald-500" : "bg-emerald-700"}" style="width:${avg}%"></div></div>
        </div>`;
    }

    return `
      <div class="flex flex-wrap gap-2">${strip}</div>
      ${stats ? `<div class="grid grid-cols-2 gap-2 mt-3">${stats}</div>` : ""}
      ${goals}`;
  }

  return { render };
})();
