window.views = window.views || {};

views.report = (() => {
  function copyableBlock(label, text) {
    const box = ui.el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-3" });
    box.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-semibold text-zinc-400 uppercase tracking-wide">${ui.escapeHtml(label)}</span>
        <button class="copy-btn text-xs bg-zinc-800 hover:bg-zinc-700 px-2 py-1 rounded">copiar</button>
      </div>
      <textarea class="markdown-block w-full bg-zinc-950 border border-zinc-800 rounded p-2 text-sm" rows="6">${ui.escapeHtml(text)}</textarea>
    `;
    const textarea = box.querySelector("textarea");
    textarea.style.height = "auto";
    textarea.rows = Math.min(20, Math.max(3, text.split("\n").length + 1));
    box.querySelector(".copy-btn").addEventListener("click", () => ui.copyText(textarea.value));
    return box;
  }

  function renderReportViewer(container, report) {
    container.innerHTML = "";
    const genDate = new Date(report.generated_at).toLocaleString("pt-BR");
    container.appendChild(ui.el("p", { class: "text-xs text-zinc-500 mb-3" }, `Gerado em ${genDate}`));

    const blocksTitle = ui.el("h3", { class: "text-sm font-bold text-zinc-300 mb-2" }, "Blocos (copiar individualmente)");
    container.appendChild(blocksTitle);
    const blocksWrap = ui.el("div", { class: "grid gap-3 mb-6" });
    blocksWrap.appendChild(copyableBlock("Cabeçalho", report.blocks.header));
    blocksWrap.appendChild(copyableBlock("Estoque Atual", report.blocks.stock));
    blocksWrap.appendChild(copyableBlock("Recomendação de Farm", report.blocks.recommendation));
    container.appendChild(blocksWrap);

    const partsTitle = ui.el(
      "h3",
      { class: "text-sm font-bold text-zinc-300 mb-2" },
      report.parts.length > 1 ? `Mensagens para o Discord (${report.parts.length} partes, limite 2000 chars)` : "Mensagem pronta para o Discord"
    );
    container.appendChild(partsTitle);
    const partsWrap = ui.el("div", { class: "grid gap-3" });
    report.parts.forEach((part, i) => {
      partsWrap.appendChild(copyableBlock(report.parts.length > 1 ? `Parte ${i + 1}/${report.parts.length}` : "Mensagem", part));
    });
    container.appendChild(partsWrap);
  }

  async function renderReportTab(container, facilityId) {
    container.innerHTML = `
      <button id="generate-report" class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold mb-6">
        📋 Gerar Relatório Agora
      </button>
      <div id="report-viewer"></div>
    `;
    document.getElementById("generate-report").addEventListener("click", async () => {
      const btn = document.getElementById("generate-report");
      btn.disabled = true;
      btn.textContent = "Gerando...";
      try {
        const report = await api.createReport(facilityId);
        renderReportViewer(document.getElementById("report-viewer"), report);
        ui.toast("Relatório gerado!");
      } catch (err) {
        ui.toast(err.message, true);
      } finally {
        btn.disabled = false;
        btn.textContent = "📋 Gerar Relatório Agora";
      }
    });
  }

  async function renderHistoryTab(container, facilityId) {
    container.innerHTML = `<div id="history-list"></div>`;
    const listEl = document.getElementById("history-list");
    const reports = await api.listReports(facilityId);
    if (reports.length === 0) {
      listEl.innerHTML = `<p class="text-zinc-500 text-sm">Nenhum relatório gerado ainda.</p>`;
      return;
    }
    listEl.innerHTML = "";
    reports.forEach((report) => {
      const item = ui.el("div", { class: "border border-zinc-800 rounded-lg mb-2 overflow-hidden" });
      const header = ui.el(
        "button",
        { class: "w-full text-left px-4 py-3 bg-zinc-900 hover:bg-zinc-800 text-sm flex justify-between items-center" },
        [
          ui.el("span", {}, `Relatório de ${new Date(report.generated_at).toLocaleString("pt-BR")}`),
          ui.el("span", { class: "text-zinc-500 text-xs" }, "expandir ▾"),
        ]
      );
      const body = ui.el("div", { class: "p-4 hidden" });
      header.addEventListener("click", () => {
        body.classList.toggle("hidden");
        if (!body.classList.contains("hidden") && body.children.length === 0) {
          renderReportViewer(body, report);
        }
      });
      item.appendChild(header);
      item.appendChild(body);
      listEl.appendChild(item);
    });
  }

  return { renderReportTab, renderHistoryTab };
})();
