window.views = window.views || {};

// "Ao vivo" tab of a facility: the dashboard the command asked for
// (03/11/2026). Asks the server every 30s for a live *estimate* — stock as
// it probably is now if the queues kept running since the last log (see
// app/services/projection.py). Nothing here is saved; reports and Metas
// keep using logged stock.
views.dashboard = (() => {
  const REFRESH_MS = 30000;
  let refreshTimer = null;
  let tickTimer = null;
  let defs = null;

  function stop() {
    clearInterval(refreshTimer);
    clearInterval(tickTimer);
    refreshTimer = tickTimer = null;
  }

  function formatQty(units, key) {
    const def = defs[key];
    const shown = def && def.is_liquid ? units * def.liters_per_unit : units;
    return Math.round(shown).toLocaleString(i18n.getLang()) + (def && def.is_liquid ? "L" : "");
  }

  function formatSpan(seconds) {
    seconds = Math.max(0, Math.round(seconds));
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h${String(m).padStart(2, "0")}`;
    if (m) return `${m}min`;
    return `${seconds}s`;
  }

  function clock(date) {
    return date.toLocaleTimeString(i18n.getLang(), { hour: "2-digit", minute: "2-digit" });
  }

  function itemLabel(key) {
    const def = defs[key];
    return def ? i18n.catalogName(def) : key;
  }

  function targetsHtml(targets) {
    if (!targets.length) return "";
    const rows = targets
      .map((t) => {
        const pct = t.target > 0 ? Math.min(100, (t.projected / t.target) * 100) : 0;
        const done = t.projected >= t.target;
        const gained = t.projected - t.logged;
        return `
        <div class="bg-zinc-900 border border-zinc-800 rounded p-3">
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-sm font-medium truncate min-w-0" title="${ui.escapeHtml(t.name)}">${ui.escapeHtml(t.name)}</span>
            <span class="text-sm tabular-nums whitespace-nowrap ${done ? "text-emerald-400" : ""}">≈ ${formatQty(t.projected, t.resource_def_key)} / ${formatQty(t.target, t.resource_def_key)}</span>
          </div>
          <div class="h-2 bg-zinc-800 rounded mt-2 overflow-hidden"><div class="h-full ${done ? "bg-emerald-500" : "bg-amber-500"}" style="width:${pct}%"></div></div>
          <div class="text-xs text-zinc-500 mt-1">${i18n.t("dashboard.loggedVsProjected", {
            logged: formatQty(t.logged, t.resource_def_key),
            gained: gained > 0 ? `+${formatQty(gained, t.resource_def_key)}` : "0",
          })}${done ? "" : ` · ${i18n.t("dashboard.missing", { qty: formatQty(t.target - t.projected, t.resource_def_key) })}`}</div>
        </div>`;
      })
      .join("");
    return `
      <h2 class="text-sm font-semibold text-zinc-300 mb-2">${i18n.t("dashboard.targetsTitle")}</h2>
      <div class="grid gap-2 mb-6" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">${rows}</div>`;
  }

  function slotHtml(slot, now) {
    const outputs = slot.produced.map((p) => p.name).join(", ") || slot.recipe_key;
    const made = slot.produced.map((p) => `+${formatQty(p.qty, p.resource)} ${ui.escapeHtml(p.name)}`).join(", ");
    let status;
    if (slot.running && slot.empty_at) {
      const at = new Date(slot.empty_at);
      status = `<span class="text-emerald-400">● ${i18n.t("dashboard.running")}</span> · ${i18n.t("dashboard.emptyIn", {
        span: formatSpan((at - now) / 1000),
        time: clock(at),
      })}`;
    } else if (slot.running) {
      status = `<span class="text-emerald-400">● ${i18n.t("dashboard.running")}</span>`;
    } else {
      const since = slot.empty_at ? ` ${i18n.t("dashboard.since", { time: clock(new Date(slot.empty_at)) })}` : "";
      status = `<span class="text-red-400">● ${i18n.t("dashboard.stopped")}</span>${since}${
        slot.missing.length ? ` · ${i18n.t("dashboard.lacks", { items: ui.escapeHtml(slot.missing.join(", ")) })}` : ""
      }`;
    }
    return `
      <div class="border-t border-zinc-800 pt-2 mt-2">
        <div class="text-sm"><span class="font-medium">${ui.escapeHtml(outputs)}</span>
          <span class="text-zinc-500">· ${i18n.t(slot.queue_count === 1 ? "dashboard.queue" : "dashboard.queues", { n: slot.queue_count })}</span></div>
        <div class="text-xs mt-0.5">${status}</div>
        ${slot.cycles_done ? `<div class="text-xs text-zinc-400 mt-0.5">${i18n.t("dashboard.sinceLog", { made, cycles: slot.cycles_done })}</div>` : ""}
      </div>`;
  }

  function buildingHtml(b, now) {
    const keys = Object.keys(b.projected).filter((k) => b.projected[k] > 0.5 || (b.logged[k] || 0) > 0.5);
    keys.sort((a, c) => itemLabel(a).localeCompare(itemLabel(c)));
    const lines = keys
      .map((k) => {
        const before = b.logged[k] || 0;
        const after = b.projected[k];
        const changed = Math.abs(after - before) >= 0.5;
        return `
        <div class="flex items-center gap-2 text-sm">
          ${defs[k] && defs[k].icon ? `<img src="${ui.escapeHtml(defs[k].icon)}" class="h-5 w-5 object-contain shrink-0" />` : `<span class="w-5"></span>`}
          <span class="flex-1 min-w-0 truncate" title="${ui.escapeHtml(itemLabel(k))}">${ui.escapeHtml(itemLabel(k))}</span>
          <span class="tabular-nums whitespace-nowrap ${changed ? (after > before ? "text-emerald-300" : "text-amber-300") : "text-zinc-300"}">${
            changed ? `≈ ${formatQty(after, k)}` : formatQty(after, k)
          }</span>
        </div>`;
      })
      .join("");
    const logged = b.last_logged_at
      ? i18n.t("dashboard.lastLog", { span: formatSpan(b.elapsed_seconds), time: clock(new Date(b.last_logged_at)) })
      : i18n.t("dashboard.neverLogged");
    return `
      <div class="bg-zinc-900 border border-zinc-800 rounded-lg p-3 flex flex-col">
        <div class="flex items-baseline justify-between gap-2">
          <span class="font-semibold truncate min-w-0">${ui.escapeHtml(b.name)}</span>
          ${b.location ? `<span class="text-xs text-zinc-500 whitespace-nowrap">📍 ${ui.escapeHtml(b.location)}</span>` : ""}
        </div>
        <div class="text-xs text-zinc-500 mb-2" title="${i18n.t("dashboard.lastLogHint")}">${logged}</div>
        <div class="grid gap-1">${lines || `<span class="text-xs text-zinc-500">${i18n.t("dashboard.noStock")}</span>`}</div>
        ${b.slots.map((s) => slotHtml(s, now)).join("")}
      </div>`;
  }

  function draw(container, data) {
    const now = new Date(data.now);
    const producing = data.buildings.filter((b) => b.slots.length);
    container.querySelector(".dash-body").innerHTML = `
      ${targetsHtml(data.targets)}
      <h2 class="text-sm font-semibold text-zinc-300 mb-2">${i18n.t("dashboard.productionTitle")}</h2>
      ${
        producing.length
          ? `<div class="grid gap-3" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">${producing.map((b) => buildingHtml(b, now)).join("")}</div>`
          : `<p class="text-sm text-zinc-500">${i18n.t("dashboard.noProduction")}</p>`
      }
      <p class="text-xs text-zinc-600 mt-4">${i18n.t("dashboard.footer")}</p>`;
  }

  // "📣 No Discord": a channel webhook the server keeps editing with this
  // panel (app/services/discord_dashboard.py). The URL never comes back from
  // the API, only its last 4 characters.
  async function drawWebhook(box, facilityId, status, editing = false) {
    const interval = status.interval_seconds;
    const btn = "px-2 py-1 rounded text-xs";
    if (!status.configured && !status.can_manage) {
      box.innerHTML = `<p class="text-xs text-zinc-500">${i18n.t("dashboard.webhookOwnerOnly")}</p>`;
      return;
    }
    if (!status.configured || editing) {
      box.innerHTML = `
        <p class="text-xs text-zinc-400 mb-2">${i18n.t("dashboard.webhookHelp", { interval })}</p>
        <form class="flex flex-wrap gap-2">
          <input name="url" type="password" autocomplete="off" ${status.configured ? "" : "required"}
            placeholder="${status.configured ? i18n.t("dashboard.webhookKeepUrl") : i18n.t("dashboard.webhookPlaceholder")}"
            class="flex-1 min-w-0 basis-64 bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-sm" />
          <input name="thread" autocomplete="off" placeholder="${i18n.t("dashboard.webhookThreadPlaceholder")}"
            value="${ui.escapeHtml(status.thread_id || "")}"
            class="flex-1 min-w-0 basis-64 bg-zinc-950 border border-zinc-700 rounded px-2 py-1 text-sm" />
          <button class="${btn} bg-indigo-600 hover:bg-indigo-500 font-semibold">${i18n.t("dashboard.webhookSave")}</button>
          ${editing ? `<button type="button" class="wh-cancel ${btn} bg-zinc-800 hover:bg-zinc-700">${i18n.t("dashboard.webhookCancel")}</button>` : ""}
        </form>`;
      box.querySelector("form").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        try {
          const next = await api.setDiscordWebhook(facilityId, ev.target.url.value.trim(), ev.target.thread.value.trim());
          if (!next.last_error) ui.toast(i18n.t("dashboard.webhookSent"));
          drawWebhook(box, facilityId, next);
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
      const cancel = box.querySelector(".wh-cancel");
      if (cancel) cancel.addEventListener("click", () => drawWebhook(box, facilityId, status));
      return;
    }
    const last = status.last_sent_at
      ? i18n.t("dashboard.webhookLast", { span: formatSpan((Date.now() - new Date(status.last_sent_at)) / 1000) })
      : i18n.t("dashboard.webhookNever");
    box.innerHTML = `
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-sm flex-1 min-w-0">${i18n.t("dashboard.webhookOn", { interval, hint: ui.escapeHtml(status.url_hint) })}${
          status.thread_id ? ` · ${i18n.t("dashboard.webhookInThread")}` : ""
        }
          <span class="text-xs text-zinc-500">· ${last}</span></span>
        <button class="wh-send ${btn} bg-zinc-800 hover:bg-zinc-700">${i18n.t("dashboard.webhookSendNow")}</button>
        ${
          status.can_manage
            ? `<button class="wh-change ${btn} bg-zinc-800 hover:bg-zinc-700">${i18n.t("dashboard.webhookChange")}</button>
        <button class="wh-remove ${btn} bg-zinc-800 hover:bg-red-900">${i18n.t("dashboard.webhookRemove")}</button>`
            : ""
        }
      </div>
      ${status.last_error ? `<p class="text-xs text-red-400 mt-1 break-words">${ui.escapeHtml(i18n.t("dashboard.webhookError", { error: status.last_error }))}</p>` : ""}`;
    box.querySelector(".wh-send").addEventListener("click", async () => {
      try {
        const next = await api.sendDiscordWebhook(facilityId);
        if (!next.last_error) ui.toast(i18n.t("dashboard.webhookSent"));
        drawWebhook(box, facilityId, next);
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
    if (!status.can_manage) return;
    box.querySelector(".wh-change").addEventListener("click", () => drawWebhook(box, facilityId, status, true));
    box.querySelector(".wh-remove").addEventListener("click", async () => {
      if (!confirm(i18n.t("dashboard.webhookRemoveConfirm"))) return;
      try {
        await api.deleteDiscordWebhook(facilityId);
        drawWebhook(box, facilityId, await api.getDiscordWebhook(facilityId));
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  async function renderDashboardTab(container, facilityId) {
    stop();
    if (!defs) {
      const list = await api.listFoxholeResources();
      defs = Object.fromEntries(list.map((r) => [r.key, r]));
    }
    container.innerHTML = `
      <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
        <p class="text-sm text-zinc-400">${i18n.t("dashboard.intro")}</p>
        <span class="dash-status text-xs text-zinc-500 tabular-nums"></span>
      </div>
      <details class="dash-webhook-wrap bg-zinc-900 border border-zinc-800 rounded p-3 mb-4">
        <summary class="cursor-pointer text-sm font-semibold text-zinc-300">${i18n.t("dashboard.webhookTitle")}</summary>
        <div class="dash-webhook mt-2"></div>
      </details>
      <div class="dash-body"></div>`;
    const webhookBox = container.querySelector(".dash-webhook");
    const webhookStatus = await api.getDiscordWebhook(facilityId);
    // Open when it's on, so its status shows; closed otherwise.
    if (webhookStatus.configured) container.querySelector(".dash-webhook-wrap").open = true;
    drawWebhook(webhookBox, facilityId, webhookStatus);
    const statusEl = container.querySelector(".dash-status");
    let fetchedAt = null;
    let failed = false;

    async function refresh() {
      // Left the tab (or the page re-rendered): stop polling.
      if (!document.body.contains(container) || !location.hash.endsWith("/live")) return stop();
      try {
        draw(container, await api.getDashboard(facilityId));
        // Refresh "último envio" too — unless the URL form is open (would wipe the typing).
        if (!webhookBox.querySelector("form")) drawWebhook(webhookBox, facilityId, await api.getDiscordWebhook(facilityId));
        fetchedAt = Date.now();
        failed = false;
      } catch (err) {
        failed = true;
      }
      tick();
    }

    function tick() {
      if (!document.body.contains(container)) return stop();
      if (!fetchedAt) return;
      const ago = Math.round((Date.now() - fetchedAt) / 1000);
      const next = Math.max(0, Math.round((REFRESH_MS - (Date.now() - fetchedAt)) / 1000));
      statusEl.textContent = `${failed ? i18n.t("dashboard.offline") + " · " : ""}${i18n.t("dashboard.updated", { ago, next })}`;
    }

    await refresh();
    refreshTimer = setInterval(refresh, REFRESH_MS);
    tickTimer = setInterval(tick, 1000);
  }

  return { renderDashboardTab };
})();
