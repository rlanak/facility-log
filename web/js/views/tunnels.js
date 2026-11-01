window.views = window.views || {};

views.tunnels = (() => {
  const LIVE_REFRESH_MS = 30_000;
  const HEALTH_FULL_SECONDS = 96 * 3600; // same as services/msupps.py

  let liveTimer = null;

  function fmtQty(value) {
    const trim = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1).replace(/\.?0+$/, ""));
    if (value >= 1_000_000) return trim(value / 1_000_000) + "M";
    if (value >= 1_000) return trim(value / 1_000) + "k";
    return trim(value);
  }

  // Mirrors report_generator.format_duration so the page and the Discord
  // report read the same.
  function fmtDuration(seconds) {
    seconds = Math.max(0, Math.floor(seconds));
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const pad = (n) => String(n).padStart(2, "0");
    if (days) return `${days}d${pad(hours)}h`;
    if (hours) return `${hours}h${pad(minutes)}`;
    if (minutes) return `${minutes}min`;
    return `${seconds}s`;
  }

  // The backend projects the stock to the moment of the request; this
  // re-projects it to *now* client-side every LIVE_REFRESH_MS so the page
  // keeps counting down without re-reading the save — the "live" feel the
  // tray app was missing.
  function project(t) {
    if (t.quantity == null || !t.rate_per_hour) return null;
    const elapsed = Math.max(0, Date.now() / 1000 - t.game_updated_unix);
    const estimated = Math.max(0, t.quantity - (t.rate_per_hour * elapsed) / 3600);
    const secondsLeft = (estimated / t.rate_per_hour) * 3600;
    return { estimated, secondsLeft, pct: Math.min(100, Math.round((secondsLeft / HEALTH_FULL_SECONDS) * 100)) };
  }

  function healthClass(pct) {
    if (pct == null) return "bg-zinc-600";
    if (pct < 15) return "bg-red-500";
    if (pct < 35) return "bg-orange-500";
    if (pct < 70) return "bg-yellow-400";
    return "bg-emerald-500";
  }

  function tunnelName(t) {
    return t.label || `${t.hex_name} ${t.grid}`.trim();
  }

  function renderCard(t, facilities, onChange) {
    const live = project(t);
    const card = ui.el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex flex-col gap-2 min-w-0" });

    const top = ui.el("div", { class: "flex items-center gap-2 min-w-0" }, [
      ui.el("span", { class: `inline-block w-3 h-3 rounded-full shrink-0 ${healthClass(live && live.pct)}` }),
      ui.el("span", { class: "font-semibold truncate", title: tunnelName(t) }, tunnelName(t)),
      ui.el("span", { class: "ml-auto text-sm text-zinc-400 shrink-0" }, live ? `${live.pct}%` : "—"),
    ]);
    card.appendChild(top);

    const sub = ui.el("div", { class: "text-xs text-zinc-500 flex flex-wrap gap-x-2" }, [
      t.label ? `${t.hex_name} ${t.grid}` : null,
      t.facility_name ? i18n.t("tunnels.facility", { name: t.facility_name }) : i18n.t("tunnels.noFacility"),
    ]);
    card.appendChild(sub);

    if (live) {
      card.appendChild(
        ui.el("div", { class: "text-lg font-bold" }, i18n.t("tunnels.estimated", { qty: fmtQty(Math.round(live.estimated)) }))
      );
      const source = t.rate_source === "manual" ? i18n.t("tunnels.rateManual") : i18n.t("tunnels.rateAuto");
      card.appendChild(
        ui.el(
          "div",
          { class: "text-sm text-zinc-300" },
          `${i18n.t("tunnels.rate", { rate: Math.round(t.rate_per_hour) })} (${source}) · ${i18n.t("tunnels.runsOut", {
            duration: fmtDuration(live.secondsLeft),
          })}`
        )
      );
    } else {
      card.appendChild(ui.el("div", { class: "text-lg font-bold" }, `${fmtQty(t.quantity ?? 0)} mSupps`));
      card.appendChild(ui.el("div", { class: "text-xs text-amber-400" }, i18n.t("tunnels.noRate")));
    }

    if (t.game_updated_unix) {
      card.appendChild(
        ui.el(
          "div",
          { class: "text-xs text-zinc-500" },
          i18n.t("tunnels.readAgo", {
            ago: fmtDuration(Date.now() / 1000 - t.game_updated_unix),
            qty: fmtQty(t.quantity),
          })
        )
      );
    }

    if (!t.pinned) {
      card.appendChild(
        ui.el(
          "div",
          { class: "text-xs text-amber-400", title: i18n.t("tunnels.unpinnedHint") },
          `⚠️ ${i18n.t("tunnels.unpinned")} — ${i18n.t("tunnels.unpinnedHint")}`
        )
      );
    }

    const actions = ui.el("div", { class: "flex flex-wrap gap-2 mt-1" }, [
      ui.el(
        "button",
        {
          class: "text-xs bg-zinc-800 hover:bg-zinc-700 px-2 py-1 rounded",
          onclick: () => openEdit(t, facilities, onChange),
        },
        i18n.t("tunnels.edit")
      ),
      ui.el(
        "button",
        {
          class: "text-xs text-red-400 hover:text-red-300 px-2 py-1",
          onclick: async () => {
            if (!confirm(i18n.t("tunnels.confirmDelete"))) return;
            try {
              await api.deleteTunnel(t.id);
              onChange();
            } catch (err) {
              ui.toast(err.message, true);
            }
          },
        },
        i18n.t("tunnels.delete")
      ),
    ]);
    card.appendChild(actions);
    return card;
  }

  function openEdit(t, facilities, onChange) {
    ui.openModal(`${i18n.t("tunnels.editTitle")} — ${tunnelName(t)}`, (body, close) => {
      const inputClass =
        "w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";
      const labelInput = ui.el("input", { class: inputClass, placeholder: i18n.t("tunnels.labelPlaceholder") });
      labelInput.value = t.label || "";
      const rateInput = ui.el("input", { class: inputClass, type: "number", min: "0", step: "1" });
      rateInput.value = t.manual_rate_per_hour ?? "";
      const facilitySelect = ui.el("select", { class: inputClass }, [
        ui.el("option", { value: "" }, `— ${i18n.t("tunnels.noFacility")} —`),
        ...facilities.map((f) => ui.el("option", { value: String(f.id) }, f.name)),
      ]);
      facilitySelect.value = t.facility_id ? String(t.facility_id) : "";

      const field = (label, input, hint) =>
        ui.el("label", { class: "block mb-3" }, [
          ui.el("span", { class: "block text-xs text-zinc-400 mb-1" }, label),
          input,
          hint ? ui.el("span", { class: "block text-xs text-zinc-500 mt-1" }, hint) : null,
        ]);

      const form = ui.el("form", {}, [
        field(i18n.t("tunnels.labelField"), labelInput),
        field(i18n.t("tunnels.rateField"), rateInput, i18n.t("tunnels.rateHint")),
        field(i18n.t("tunnels.facilityField"), facilitySelect, i18n.t("tunnels.facilityHint")),
        ui.el(
          "button",
          { class: "bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold" },
          i18n.t("tunnels.save")
        ),
      ]);
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const rate = rateInput.value.trim() === "" ? null : Number(rateInput.value);
        try {
          await api.updateTunnel(t.id, {
            label: labelInput.value,
            manual_rate_per_hour: rate,
            facility_id: facilitySelect.value ? Number(facilitySelect.value) : null,
          });
          ui.toast(i18n.t("tunnels.saved"));
          close();
          onChange();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
      body.appendChild(form);
    });
  }

  async function render(app) {
    if (liveTimer) clearInterval(liveTimer);

    app.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
        <h1 class="text-xl font-bold">${i18n.t("tunnels.title")}</h1>
        <button id="tunnels-sync" class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("tunnels.sync")}</button>
      </div>
      <p class="text-sm text-zinc-400 mb-2">${i18n.t("tunnels.intro")}</p>
      <p id="tunnels-status" class="text-xs text-zinc-500 mb-4 break-all"></p>
      <div id="tunnels-list" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"></div>
    `;
    const statusEl = document.getElementById("tunnels-status");
    const listEl = document.getElementById("tunnels-list");
    const syncBtn = document.getElementById("tunnels-sync");

    let tunnels = [];
    let facilities = [];

    function draw() {
      listEl.innerHTML = "";
      if (tunnels.length === 0) {
        listEl.innerHTML = `<p class="text-zinc-500 text-sm">${i18n.t("tunnels.empty")}</p>`;
        return;
      }
      for (const t of tunnels) listEl.appendChild(renderCard(t, facilities, refresh));
    }

    async function refresh() {
      [tunnels, facilities] = await Promise.all([api.listTunnels(), api.listFacilities()]);
      draw();
    }

    async function sync({ quiet = false } = {}) {
      syncBtn.disabled = true;
      syncBtn.textContent = i18n.t("tunnels.syncing");
      try {
        const result = await api.syncTunnels();
        statusEl.textContent = i18n.t("tunnels.savePath", { path: result.save_path });
        statusEl.className = "text-xs text-zinc-500 mb-4 break-all";
        if (!quiet) ui.toast(i18n.t("tunnels.synced", { n: result.tunnels_in_save, new: result.new_readings }));
      } catch (err) {
        statusEl.textContent = err.message;
        statusEl.className = "text-xs text-amber-400 mb-4 break-all";
      } finally {
        syncBtn.disabled = false;
        syncBtn.textContent = i18n.t("tunnels.sync");
      }
      await refresh();
    }

    syncBtn.addEventListener("click", () => sync());

    const status = await api.tunnelStatus();
    if (!status.parser_available || !status.save_path) {
      statusEl.textContent = !status.parser_available ? i18n.t("tunnels.noParser") : i18n.t("tunnels.noSave");
      statusEl.className = "text-xs text-amber-400 mb-4 break-all";
      await refresh();
    } else {
      // Opening the page reads the save right away — same as the tray app
      // did when its status window opened.
      await sync({ quiet: true });
    }

    liveTimer = setInterval(() => {
      // Stop once the user navigates away (the router replaces #app's content).
      if (!document.body.contains(listEl)) {
        clearInterval(liveTimer);
        liveTimer = null;
        return;
      }
      draw();
    }, LIVE_REFRESH_MS);
  }

  return { render };
})();
