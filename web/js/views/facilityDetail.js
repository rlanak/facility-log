window.views = window.views || {};

views.facilityDetail = (() => {
  let facilityId;
  let allResources = [];

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
      app.innerHTML = `<p class="text-red-400">Facility não encontrada.</p>`;
      return;
    }

    app.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <h1 class="text-xl font-bold">${ui.escapeHtml(facility.name)}</h1>
        <div class="flex gap-2">
          <button id="rename-facility" class="text-xs text-zinc-400 hover:text-zinc-200">renomear</button>
          <button id="delete-facility" class="text-xs text-red-400 hover:text-red-300">excluir facility</button>
        </div>
      </div>
      <div class="flex gap-2 mb-6">
        ${tabLink("buildings", "Prédios & Estoque", activeTab)}
        ${tabLink("report", "Relatório", activeTab)}
        ${tabLink("history", "Histórico", activeTab)}
      </div>
      <div id="tab-content"></div>
    `;

    document.getElementById("rename-facility").addEventListener("click", async () => {
      const name = prompt("Novo nome da facility:", facility.name);
      if (!name || !name.trim()) return;
      await api.updateFacility(facilityId, { name: name.trim() });
      render(app, facilityId, activeTab);
    });

    document.getElementById("delete-facility").addEventListener("click", async () => {
      if (!confirm("Excluir essa facility? Todos os prédios, estoques e relatórios serão apagados.")) return;
      await api.deleteFacility(facilityId);
      location.hash = "#/";
    });

    allResources = await api.listResources();

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
      <form id="new-building-form" class="grid grid-cols-[1fr_160px_auto] gap-2 mb-6">
        <input id="b-name" required placeholder="Nome do prédio (ex: Coke Furnace 1)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <input id="b-role" placeholder="Papel (opcional)"
          class="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500" />
        <button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold whitespace-nowrap">+ Prédio</button>
      </form>
      <div id="buildings-list" class="space-y-3"></div>
    `;

    document.getElementById("new-building-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("b-name").value.trim();
      const role = document.getElementById("b-role").value.trim();
      if (!name) return;
      try {
        await api.createBuilding(facilityId, { name, role });
        e.target.reset();
        renderBuildingsList();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });

    async function renderBuildingsList() {
      const listEl = document.getElementById("buildings-list");
      const buildings = await api.listBuildings(facilityId);
      if (buildings.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">Nenhum prédio cadastrado ainda.</p>`;
        return;
      }
      listEl.innerHTML = "";
      for (const building of buildings) {
        listEl.appendChild(await buildingCard(building, renderBuildingsList));
      }
    }

    renderBuildingsList();
  }

  async function buildingCard(building, onChange) {
    const card = ui.el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-4" });
    const stock = await api.getBuildingStock(building.id);

    card.innerHTML = `
      <div class="flex items-center justify-between">
        <div>
          <span class="font-semibold">${ui.escapeHtml(building.name)}</span>
          ${building.role ? `<span class="text-xs text-zinc-500 ml-2">${ui.escapeHtml(building.role)}</span>` : ""}
        </div>
        <div class="flex gap-2">
          <button class="edit-building text-xs text-zinc-400 hover:text-zinc-200">editar</button>
          <button class="delete-building text-xs text-red-400 hover:text-red-300">excluir</button>
        </div>
      </div>
      <div class="text-sm text-zinc-300 mt-2">
        ${
          stock.length === 0
            ? '<span class="text-zinc-600">sem lançamentos</span>'
            : stock
                .map((s) => `<span class="mr-3">${ui.escapeHtml(s.resource_icon)} ${ui.escapeHtml(s.resource_name)}: <strong>${s.quantity}</strong></span>`)
                .join("")
        }
      </div>
      <button class="toggle-stock-form text-xs text-emerald-400 hover:text-emerald-300 mt-3">+ Lançar estoque</button>
      <div class="stock-form-container hidden mt-3"></div>
    `;

    card.querySelector(".delete-building").addEventListener("click", async () => {
      if (!confirm(`Excluir o prédio "${building.name}"? Estoques e imagens associados também serão apagados.`)) return;
      await api.deleteBuilding(building.id);
      onChange();
    });

    card.querySelector(".edit-building").addEventListener("click", async () => {
      const name = prompt("Nome do prédio:", building.name);
      if (name === null) return;
      const role = prompt("Papel (opcional):", building.role || "");
      if (role === null) return;
      await api.updateBuilding(building.id, { name: name.trim(), role: role.trim() });
      onChange();
    });

    const toggleBtn = card.querySelector(".toggle-stock-form");
    const formContainer = card.querySelector(".stock-form-container");
    toggleBtn.addEventListener("click", () => {
      formContainer.classList.toggle("hidden");
      if (!formContainer.classList.contains("hidden") && formContainer.children.length === 0) {
        buildStockForm(formContainer, building, onChange);
      }
    });

    return card;
  }

  function buildStockForm(container, building, onChange) {
    container.innerHTML = `
      <div class="border border-zinc-800 rounded p-3 bg-zinc-950">
        <div class="stock-rows space-y-2"></div>
        <button type="button" class="add-row text-xs text-zinc-400 hover:text-zinc-200 mt-2">+ Adicionar linha</button>
        <div class="flex gap-2 mt-3">
          <button type="button" class="save-stock bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-xs font-semibold">Salvar Lançamento</button>
        </div>
        <p class="text-xs text-zinc-500 mt-2">Aceita formatos como <code>25.7k</code>, <code>1,8k</code> ou <code>32000</code>.</p>
      </div>
    `;

    const rowsEl = container.querySelector(".stock-rows");

    function addRow() {
      const row = ui.el("div", { class: "flex gap-2" });
      row.innerHTML = `
        <input list="resources-datalist" placeholder="Recurso (ex: Coal)"
          class="flex-1 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-resource" />
        <input placeholder="Qtd (ex: 25.7k)"
          class="w-32 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500 row-qty" />
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
        ui.toast("Preencha pelo menos uma linha.", true);
        return;
      }
      try {
        await api.addBuildingStock(building.id, entries);
        ui.toast("Estoque lançado!");
        onChange();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  return { render };
})();
