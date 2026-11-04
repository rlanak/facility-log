window.views = window.views || {};

views.facilities = (() => {
  async function render(app) {
    app.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">${i18n.t("facilities.title")}</h1>
      </div>
      <form id="new-facility-form" class="flex gap-2 mb-6">
        <input id="new-facility-name" required placeholder="${i18n.t("facilities.namePlaceholder")}"
          class="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("facilities.add")}</button>
      </form>
      <div id="facilities-list" class="grid gap-3 sm:grid-cols-2"></div>
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
      const facilities = await api.listFacilities();
      if (facilities.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("facilities.empty")}</p>`;
        return;
      }
      listEl.innerHTML = facilities
        .map(
          (f) => `
        <a href="#/facilities/${f.id}" class="block bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-emerald-600 transition">
          <div class="font-semibold">${f.private ? `<span title="${i18n.t("facilities.privateHint")}">🔒</span> ` : ""}${ui.escapeHtml(f.name)}</div>
          ${f.owner_name ? `<div class="text-xs text-zinc-500 mt-1">${i18n.t("facilities.owner", { name: ui.escapeHtml(f.owner_name) })}</div>` : ""}
          <div class="text-xs text-zinc-500 mt-1">${i18n.t("facilities.updatedAt", { date: new Date(f.updated_at).toLocaleString(i18n.getLang()) })}</div>
        </a>
      `
        )
        .join("");
    }

    renderList();
  }

  return { render };
})();
