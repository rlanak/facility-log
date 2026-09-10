window.views = window.views || {};

views.resources = (() => {
  async function render(app) {
    app.innerHTML = `
      <h1 class="text-xl font-bold mb-4">Catálogo de Recursos</h1>
      <p class="text-zinc-500 text-sm mb-4">Recursos são compartilhados entre todas as facilities. Você também pode criar um recurso novo direto na hora de lançar estoque.</p>
      <form id="new-resource-form" class="grid grid-cols-[1fr_100px_140px_auto] gap-2 mb-6">
        <input id="res-name" required placeholder="Nome (ex: Coal, Cmat, Am3)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="res-icon" placeholder="Ícone (🪨)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="res-target" type="number" step="any" placeholder="Meta (opcional)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">+ Adicionar</button>
      </form>
      <div id="resources-list" class="divide-y divide-zinc-800 border border-zinc-800 rounded-lg overflow-hidden"></div>
    `;

    document.getElementById("new-resource-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("res-name").value.trim();
      const icon = document.getElementById("res-icon").value.trim();
      const targetRaw = document.getElementById("res-target").value;
      if (!name) return;
      try {
        await api.createResource({
          name,
          icon,
          target_max: targetRaw ? parseFloat(targetRaw) : null,
        });
        e.target.reset();
        renderList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    async function renderList() {
      const listEl = document.getElementById("resources-list");
      const resources = await api.listResources();
      if (resources.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm p-4">Nenhum recurso cadastrado ainda.</p>`;
        return;
      }
      listEl.innerHTML = resources
        .map(
          (r) => `
        <div class="flex items-center justify-between px-4 py-2 bg-zinc-900">
          <div class="flex items-center gap-3">
            <span class="text-lg">${ui.escapeHtml(r.icon || "•")}</span>
            <span class="font-medium">${ui.escapeHtml(r.name)}</span>
            ${r.target_max != null ? `<span class="text-xs text-zinc-500">meta: ${r.target_max}</span>` : ""}
          </div>
          <button data-id="${r.id}" class="delete-resource text-xs text-red-400 hover:text-red-300">excluir</button>
        </div>
      `
        )
        .join("");

      listEl.querySelectorAll(".delete-resource").forEach((btn) => {
        btn.addEventListener("click", async () => {
          if (!confirm("Excluir esse recurso? Lançamentos de estoque associados também serão apagados.")) return;
          try {
            await api.deleteResource(btn.dataset.id);
            renderList();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      });
    }

    renderList();
  }

  return { render };
})();
