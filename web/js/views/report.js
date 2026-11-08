window.views = window.views || {};

views.report = (() => {
  function copyableBlock(label, text) {
    const box = ui.el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-3" });
    box.innerHTML = `
      <div class="flex items-center justify-between mb-2">
        <span class="text-xs font-semibold text-zinc-400 uppercase tracking-wide">${ui.escapeHtml(label)}</span>
        <button class="copy-btn text-xs bg-zinc-800 hover:bg-zinc-700 px-2 py-1 rounded">${i18n.t("report.copy")}</button>
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
    const genDate = i18n.formatDateTime(report.generated_at);
    container.appendChild(ui.el("p", { class: "text-xs text-zinc-500 mb-3" }, i18n.t("report.generatedAt", { date: genDate })));

    const blocksTitle = ui.el("h3", { class: "text-sm font-bold text-zinc-300 mb-2" }, i18n.t("report.blocksTitle"));
    container.appendChild(blocksTitle);
    const blocksWrap = ui.el("div", { class: "grid gap-3 mb-6" });
    blocksWrap.appendChild(copyableBlock(i18n.t("report.header"), report.blocks.header));
    blocksWrap.appendChild(copyableBlock(i18n.t("report.stock"), report.blocks.stock));
    blocksWrap.appendChild(copyableBlock(i18n.t("report.recommendation"), report.blocks.recommendation));
    container.appendChild(blocksWrap);

    const partsTitle = ui.el(
      "h3",
      { class: "text-sm font-bold text-zinc-300 mb-2" },
      report.parts.length > 1 ? i18n.t("report.discordParts", { n: report.parts.length }) : i18n.t("report.discordReady")
    );
    container.appendChild(partsTitle);
    const partsWrap = ui.el("div", { class: "grid gap-3" });
    report.parts.forEach((part, i) => {
      const label = report.parts.length > 1 ? i18n.t("report.part", { i: i + 1, n: report.parts.length }) : i18n.t("report.message");
      partsWrap.appendChild(copyableBlock(label, part));
    });
    container.appendChild(partsWrap);
  }

  async function renderReportTab(container, facilityId) {
    container.innerHTML = `
      <button id="generate-report" class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold mb-6">
        ${i18n.t("report.generate")}
      </button>
      <div id="report-viewer"></div>
    `;
    document.getElementById("generate-report").addEventListener("click", async () => {
      const btn = document.getElementById("generate-report");
      btn.disabled = true;
      btn.textContent = i18n.t("report.generating");
      try {
        const report = await api.createReport(facilityId);
        renderReportViewer(document.getElementById("report-viewer"), report);
        ui.toast(i18n.t("report.generated"));
      } catch (err) {
        ui.toast(err.message, true);
      } finally {
        btn.disabled = false;
        btn.textContent = i18n.t("report.generate");
      }
    });
  }

  async function renderHistoryTab(container, facilityId) {
    container.innerHTML = `<div id="history-list"></div>`;
    const listEl = document.getElementById("history-list");
    const reports = await api.listReports(facilityId);
    if (reports.length === 0) {
      listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("report.noneYet")}</p>`;
      return;
    }
    listEl.innerHTML = "";
    reports.forEach((report) => {
      const item = ui.el("div", { class: "border border-zinc-800 rounded-lg mb-2 overflow-hidden" });
      const header = ui.el(
        "div",
        { class: "w-full px-4 py-3 bg-zinc-900 hover:bg-zinc-800 text-sm flex justify-between items-center gap-2" },
        [
          ui.el(
            "button",
            { class: "flex-1 min-w-0 text-left" },
            [
              ui.el(
                "span",
                {},
                i18n.t("report.reportOf", { date: i18n.formatDateTime(report.generated_at) }) +
                  (report.created_by_name ? ` · ${i18n.t("report.by", { name: report.created_by_name })}` : "")
              ),
              ui.el("span", { class: "text-zinc-500 text-xs ml-2" }, i18n.t("report.expand")),
            ]
          ),
          ui.el(
            "button",
            { class: "delete-report shrink-0 text-xs text-red-400 hover:text-red-300 border border-red-900 hover:border-red-600 rounded px-2 py-1" },
            i18n.t("common.delete")
          ),
        ]
      );
      const toggleBtn = header.querySelector("button:first-child");
      const deleteBtn = header.querySelector(".delete-report");
      const body = ui.el("div", { class: "p-4 hidden" });
      toggleBtn.addEventListener("click", () => {
        body.classList.toggle("hidden");
        if (!body.classList.contains("hidden") && body.children.length === 0) {
          renderReportViewer(body, report);
        }
      });
      deleteBtn.addEventListener("click", async () => {
        if (!confirm(i18n.t("report.deleteConfirm"))) return;
        try {
          await api.deleteReport(report.id);
          ui.toast(i18n.t("report.deleted"));
          renderHistoryTab(container, facilityId);
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
      item.appendChild(header);
      item.appendChild(body);
      listEl.appendChild(item);
    });
  }

  return { renderReportTab, renderHistoryTab };
})();
