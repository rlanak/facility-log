window.views = window.views || {};

views.facilities = (() => {
  async function render(app) {
    app.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-xl font-bold">Facilities</h1>
      </div>
      <form id="new-facility-form" class="flex gap-2 mb-6">
        <input id="new-facility-name" required placeholder="Nome da facility (ex: Facility Weathered Expanse)"
          class="flex-1 bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">+ Nova Facility</button>
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
      listEl.innerHTML = `<p class="text-zinc-500 text-sm">Carregando...</p>`;
      const facilities = await api.listFacilities();
      if (facilities.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">Nenhuma facility cadastrada ainda.</p>`;
        return;
      }
      listEl.innerHTML = facilities
        .map(
          (f) => `
        <a href="#/facilities/${f.id}" class="block bg-zinc-900 border border-zinc-800 rounded-lg p-4 hover:border-emerald-600 transition">
          <div class="font-semibold">${ui.escapeHtml(f.name)}</div>
          <div class="text-xs text-zinc-500 mt-1">Atualizada em ${new Date(f.updated_at).toLocaleString("pt-BR")}</div>
        </a>
      `
        )
        .join("");
    }

    renderList();
  }

  return { render };
})();
