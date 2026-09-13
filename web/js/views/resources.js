window.views = window.views || {};

views.resources = (() => {
  async function render(app) {
    app.innerHTML = `
      <h1 class="text-xl font-bold mb-4">Catálogo de Recursos</h1>
      <p class="text-zinc-500 text-sm mb-1">Lista de recursos compartilhada entre todas as facilities — cadastre aqui uma vez
        (ícone, meta de estoque opcional) e reuse em qualquer prédio. Você também pode criar um recurso novo direto na hora
        de lançar estoque, se preferir.</p>
      <p class="text-zinc-500 text-sm mb-6">Marque <strong>"é matéria-prima"</strong> só pros recursos que você efetivamente
        farma no mundo (ex: Coal, Sulfur). Desmarque pra itens que seus prédios produzem/transformam (ex: Coke, Cmat) —
        assim a recomendação de farm do relatório nunca sugere "farmar" algo que só sai de produção local.</p>

      <div class="bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-6">
        <h2 class="text-sm font-bold text-zinc-300 mb-2">📖 Importar do catálogo Foxhole</h2>
        <p class="text-xs text-zinc-500 mb-3">Nomes fixos (vêm da wiki), você pode dar um apelido depois de importar.</p>
        <input id="foxhole-res-search" placeholder="Buscar (ex: coal, coke, 20mm)..."
          class="w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm mb-3 focus:outline-none focus:border-emerald-500" />
        <div id="foxhole-res-results" class="grid gap-1 max-h-64 overflow-y-auto"></div>
      </div>

      <h2 class="text-sm font-bold text-zinc-300 mb-2">Ou cadastre manualmente</h2>
      <form id="new-resource-form" class="grid grid-cols-[1fr_100px_140px_auto] gap-2 mb-2">
        <input id="res-name" required placeholder="Nome (ex: Coal, Cmat, Am3)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="res-icon" placeholder="Ícone (opcional)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="res-target" type="number" step="any" placeholder="Meta (opcional)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">+ Adicionar</button>
      </form>
      <label class="flex items-center gap-2 text-sm text-zinc-400 mb-6">
        <input id="res-farmable" type="checkbox" checked class="accent-emerald-600" />
        é matéria-prima (farmável)
      </label>
      <div id="resources-list" class="divide-y divide-zinc-800 border border-zinc-800 rounded-lg overflow-hidden"></div>
    `;

    document.getElementById("new-resource-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("res-name").value.trim();
      const icon = document.getElementById("res-icon").value.trim();
      const targetRaw = document.getElementById("res-target").value;
      const farmable = document.getElementById("res-farmable").checked;
      if (!name) return;
      try {
        await api.createResource({
          name,
          icon,
          target_max: targetRaw ? parseFloat(targetRaw) : null,
          farmable,
        });
        e.target.reset();
        document.getElementById("res-farmable").checked = true;
        renderList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    let foxholeResources = [];
    let currentResources = [];

    function renderFoxholeResults(filter) {
      const resultsEl = document.getElementById("foxhole-res-results");
      const q = filter.trim().toLowerCase();
      if (!q) {
        resultsEl.innerHTML = `<p class="text-xs text-zinc-600 p-2">Digite pra buscar entre ${foxholeResources.length} itens.</p>`;
        return;
      }
      const matches = foxholeResources.filter((r) => r.name_en.toLowerCase().includes(q)).slice(0, 30);
      if (matches.length === 0) {
        resultsEl.innerHTML = `<p class="text-xs text-zinc-600 p-2">Nada encontrado.</p>`;
        return;
      }
      const importedKeys = new Set(currentResources.map((r) => r.resource_def_key).filter(Boolean));
      resultsEl.innerHTML = matches
        .map((r) => {
          const already = importedKeys.has(r.key);
          const thumb = r.icon
            ? `<img src="${ui.escapeHtml(r.icon)}" class="h-8 w-8 inline-block object-contain" />`
            : "";
          return `
          <div class="flex items-center justify-between px-2 py-1.5 hover:bg-zinc-800 rounded text-sm">
            <span class="flex items-center gap-2">${thumb} ${ui.escapeHtml(r.name_en)} ${!r.farmable ? '<span class="text-xs text-zinc-600">(produzido)</span>' : ""}</span>
            ${
              already
                ? '<span class="text-xs text-zinc-600">já importado</span>'
                : `<button data-key="${r.key}" class="import-foxhole-resource text-xs text-emerald-400 hover:text-emerald-300">+ importar</button>`
            }
          </div>`;
        })
        .join("");

      resultsEl.querySelectorAll(".import-foxhole-resource").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const def = foxholeResources.find((r) => r.key === btn.dataset.key);
          try {
            await api.createResource({
              name: def.name_en,
              icon: "",
              farmable: def.farmable,
              resource_def_key: def.key,
            });
            ui.toast(`${def.name_en} importado!`);
            await renderList();
            renderFoxholeResults(document.getElementById("foxhole-res-search").value);
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      });
    }

    document.getElementById("foxhole-res-search").addEventListener("input", (e) => {
      renderFoxholeResults(e.target.value);
    });

    async function renderList() {
      const listEl = document.getElementById("resources-list");
      currentResources = await api.listResources();
      if (currentResources.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm p-4">Nenhum recurso cadastrado ainda.</p>`;
        return;
      }
      listEl.innerHTML = currentResources
        .map((r) => {
          const def = foxholeResources.find((f) => f.key === r.resource_def_key);
          const thumb =
            def && def.icon
              ? `<img src="${ui.escapeHtml(def.icon)}" class="h-9 w-9 object-contain" />`
              : `<span class="text-lg">${ui.escapeHtml(r.icon || "•")}</span>`;
          return `
        <div class="flex items-center justify-between px-4 py-2 bg-zinc-900">
          <div class="flex items-center gap-3">
            ${thumb}
            <span class="font-medium">${ui.escapeHtml(r.nickname || r.name)}</span>
            ${r.nickname ? `<span class="text-xs text-zinc-600">(${ui.escapeHtml(r.name)})</span>` : ""}
            ${r.resource_def_key ? '<span class="text-xs text-zinc-600" title="do catálogo Foxhole">📖</span>' : ""}
            ${r.target_max != null ? `<span class="text-xs text-zinc-500">meta: ${r.target_max}</span>` : ""}
            <label class="flex items-center gap-1 text-xs text-zinc-400">
              <input type="checkbox" data-id="${r.id}" class="toggle-farmable accent-emerald-600" ${r.farmable ? "checked" : ""} />
              matéria-prima
            </label>
            ${!r.farmable ? '<span class="text-xs text-zinc-600">(produzido/intermediário)</span>' : ""}
          </div>
          <div class="flex items-center gap-2">
            <button data-id="${r.id}" class="edit-nickname text-xs text-zinc-400 hover:text-zinc-200">apelido</button>
            <button data-id="${r.id}" class="edit-target text-xs text-zinc-400 hover:text-zinc-200">meta</button>
            <button data-id="${r.id}" class="delete-resource text-xs text-red-400 hover:text-red-300">excluir</button>
          </div>
        </div>
      `;
        })
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

      listEl.querySelectorAll(".toggle-farmable").forEach((checkbox) => {
        checkbox.addEventListener("change", async () => {
          try {
            await api.updateResource(checkbox.dataset.id, { farmable: checkbox.checked });
            renderList();
          } catch (err) {
            ui.toast(err.message, true);
            checkbox.checked = !checkbox.checked;
          }
        });
      });

      listEl.querySelectorAll(".edit-nickname").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const resource = currentResources.find((r) => String(r.id) === btn.dataset.id);
          const nickname = prompt("Apelido (deixe vazio pra usar o nome padrão):", resource.nickname || "");
          if (nickname === null) return;
          try {
            await api.updateResource(btn.dataset.id, { nickname: nickname.trim() || null });
            renderList();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      });

      listEl.querySelectorAll(".edit-target").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const resource = currentResources.find((r) => String(r.id) === btn.dataset.id);
          const targetRaw = prompt(
            "Meta de estoque (deixe vazio pra remover):",
            resource.target_max != null ? String(resource.target_max) : ""
          );
          if (targetRaw === null) return;
          const target = targetRaw.trim();
          if (target && isNaN(parseFloat(target))) {
            ui.toast("Digite um número válido.", true);
            return;
          }
          try {
            await api.updateResource(btn.dataset.id, { target_max: target ? parseFloat(target) : null });
            renderList();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      });
    }

    foxholeResources = await api.listFoxholeResources();
    await renderList();
    renderFoxholeResults("");
  }

  return { render };
})();
