window.views = window.views || {};

// Dashboard tab of a facility. Asks the server every 30s for an *estimate* —
// stock as it probably is now if the queues kept running since the last log
// (see app/services/projection.py). Nothing here is saved; reports and Metas
// keep using logged stock.
views.dashboard = (() => {
  const REFRESH_MS = 30000;
  // A log older than this makes the estimate unreliable (queues get changed,
  // material moved): the building gets a warning.
  const STALE_SECONDS = 24 * 3600;
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

  // "21:37" today, "02/11 21:37" any other day — a bare time is ambiguous
  // once the log is days old.
  function when(date) {
    const time = i18n.formatTime(date);
    if (i18n.sameDay(date, new Date())) return time;
    return `${i18n.formatDateTime(date, { day: "2-digit", month: "2-digit" })} ${time}`;
  }

  function pct(part, whole) {
    return whole > 0 ? Math.round((part / whole) * 100) : 0;
  }

  function itemLabel(key) {
    const def = defs[key];
    return def ? i18n.catalogName(def) : key;
  }

  function targetsHtml(targets) {
    if (!targets.length) return "";
    const rows = targets
      .map((t) => {
        const k = t.resource_def_key;
        const done = t.projected >= t.target;
        const gained = Math.max(0, t.projected - t.logged);
        const p = pct(t.projected, t.target);
        return `
        <div class="bg-zinc-900 border border-zinc-800 rounded p-3">
          <div class="flex items-baseline justify-between gap-2">
            <span class="text-sm font-medium truncate min-w-0" title="${ui.escapeHtml(t.name)}">${ui.escapeHtml(t.name)}</span>
            <span class="text-xs whitespace-nowrap ${done ? "text-emerald-400" : "text-amber-400"}">${
              done ? i18n.t("dashboard.targetDone") : `${p}%`
            }</span>
          </div>
          <div class="text-sm tabular-nums mt-1">≈ ${formatQty(t.projected, k)} <span class="text-zinc-500">${i18n.t("dashboard.of")} ${formatQty(t.target, k)}</span>${
            done ? "" : ` <span class="text-zinc-400">· ${i18n.t("dashboard.missing", { qty: formatQty(t.target - t.projected, k) })}</span>`
          }</div>
          <div class="h-2 bg-zinc-800 rounded mt-2 overflow-hidden"><div class="h-full ${done ? "bg-emerald-500" : "bg-amber-500"}" style="width:${Math.min(100, p)}%"></div></div>
          <div class="text-xs text-zinc-500 mt-1">${i18n.t("dashboard.loggedVsProjected", {
            logged: formatQty(t.logged, k),
            gained: `+${formatQty(gained, k)}`,
          })}</div>
          ${t.incoming && !done ? `<div class="text-xs text-sky-300 mt-0.5">${i18n.t("dashboard.incoming", { qty: formatQty(t.incoming, k) })}</div>` : ""}
        </div>`;
      })
      .join("");
    return `
      <h2 class="text-sm font-semibold text-zinc-300 mb-2">${i18n.t("dashboard.targetsTitle")}</h2>
      <div class="grid gap-2 mb-6" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">${rows}</div>`;
  }

  // Where else in the facility a missing input is sitting (stations first):
  // the estimate never moves material, but the player can.
  function elsewhere(key, building, buildings) {
    return buildings
      .filter((o) => o.id !== building.id && (o.projected[key] || 0) >= 1)
      .sort((a, c) => Number(c.storage) - Number(a.storage) || c.projected[key] - a.projected[key])
      .slice(0, 2)
      .map((o) => `${formatQty(o.projected[key], key)} ${i18n.t("dashboard.inBuilding", { name: ui.escapeHtml(o.location ? `${o.name} (${o.location})` : o.name) })}`);
  }

  function slotHtml(slot, now, building, buildings) {
    const outputs = slot.produced.map((p) => p.name).join(", ") || slot.recipe_key;
    const made = slot.produced.map((p) => `+${formatQty(p.qty, p.resource)} ${ui.escapeHtml(p.name)}`).join(", ");
    let status;
    let hint = "";
    if (slot.running && slot.empty_at) {
      const at = i18n.parseDate(slot.empty_at);
      status = `<span class="text-emerald-400">● ${i18n.t("dashboard.running")}</span> · ${i18n.t("dashboard.emptyIn", {
        span: formatSpan((at - now) / 1000),
        time: when(at),
      })}`;
    } else if (slot.running) {
      status = `<span class="text-emerald-400">● ${i18n.t("dashboard.running")}</span> · ${i18n.t("dashboard.noLimit")}`;
    } else {
      const since = slot.empty_at ? ` ${i18n.t("dashboard.since", { time: when(i18n.parseDate(slot.empty_at)) })}` : "";
      status = `<span class="text-red-400">● ${i18n.t("dashboard.stopped")}</span>${since}${
        slot.missing.length ? ` · ${i18n.t("dashboard.lacks", { items: ui.escapeHtml(slot.missing.join(", ")) })}` : ""
      }`;
      const found = (slot.missing_keys || []).flatMap((k) => {
        const where = elsewhere(k, building, buildings);
        return where.length ? [`${ui.escapeHtml(itemLabel(k))}: ${where.join(", ")}`] : [];
      });
      if (found.length) hint = `<div class="text-xs text-sky-300 mt-0.5">💡 ${i18n.t("dashboard.availableElsewhere", { list: found.join(" · ") })}</div>`;
    }
    return `
      <div class="border-t border-zinc-800 pt-2 mt-2">
        <div class="text-sm"><span class="font-medium">${ui.escapeHtml(outputs)}</span>
          <span class="text-zinc-500">· ${i18n.t(slot.queue_count === 1 ? "dashboard.queue" : "dashboard.queues", { n: slot.queue_count })}</span></div>
        <div class="text-xs mt-0.5">${status}</div>
        ${hint}
        ${slot.cycles_done ? `<div class="text-xs text-zinc-400 mt-0.5">${i18n.t("dashboard.sinceLog", { made, cycles: slot.cycles_done })}</div>` : ""}
      </div>`;
  }

  function lastLogHtml(b) {
    if (!b.last_logged_at) return `<div class="text-xs text-zinc-500 mb-2">${i18n.t("dashboard.neverLogged")}</div>`;
    const text = i18n.t("dashboard.lastLog", { span: formatSpan(b.elapsed_seconds), time: when(i18n.parseDate(b.last_logged_at)) });
    // Stations aren't projected, so an old log there is just "old", not a warning.
    if (b.elapsed_seconds < STALE_SECONDS || b.storage) {
      return `<div class="text-xs text-zinc-500 mb-2" title="${i18n.t("dashboard.lastLogHint")}">${text}</div>`;
    }
    return `<div class="text-xs text-amber-400 mb-2" title="${i18n.t("dashboard.lastLogHint")}">⚠ ${text} · ${i18n.t("dashboard.stale")}</div>`;
  }

  function buildingHtml(b, now, buildings) {
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
    return `
      <div class="bg-zinc-900 border border-zinc-800 rounded-lg p-3 flex flex-col">
        <div class="flex items-baseline justify-between gap-2">
          <span class="font-semibold truncate min-w-0">${ui.escapeHtml(b.name)}</span>
          ${b.location ? `<span class="text-xs text-zinc-500 whitespace-nowrap">📍 ${ui.escapeHtml(b.location)}</span>` : ""}
        </div>
        ${lastLogHtml(b)}
        <div class="grid gap-1">${lines || `<span class="text-xs text-zinc-500">${i18n.t("dashboard.noStock")}</span>`}</div>
        ${b.slots.map((s) => slotHtml(s, now, b, buildings)).join("")}
      </div>`;
  }

  // Private orders (services/private_orders.py): who, what, where, when.
  function privateHtml(orders, now) {
    if (!orders || !orders.length) return "";
    const rows = orders
      .map((o) => {
        const item = o.outputs.map((x) => x.name).join(", ") || o.recipe_key;
        const where = o.building_location ? `${o.building_name} (${o.building_location})` : o.building_name;
        let status;
        if (o.status === "released") {
          status = `<span class="text-amber-400">${i18n.t("private.released", { time: when(i18n.parseDate(o.expires_at)) })}</span>`;
        } else if (o.status === "ready") {
          const exp = i18n.parseDate(o.expires_at);
          status = `<span class="text-emerald-400">${i18n.t("private.ready")}</span> · ${i18n.t("private.retrieveBefore", { time: when(exp), span: formatSpan((exp - now) / 1000) })}`;
        } else if (o.ready_at) {
          const ready = i18n.parseDate(o.ready_at);
          const left = o.outputs.map((x) => `${formatQty(x.per_cycle * o.remaining_cycles, x.resource)} ${ui.escapeHtml(x.name)}`).join(" + ");
          status = `<span class="text-emerald-400">●</span> ${i18n.t("private.left", { left })} · ${i18n.t("private.readyAt", { time: when(ready), span: formatSpan((ready - now) / 1000) })}`;
        } else {
          status = `<span class="text-emerald-400">● ${i18n.t("private.running")}</span>`;
        }
        return `
        <div class="bg-zinc-900 border border-zinc-800 rounded p-3 min-w-0">
          <div class="flex items-center gap-1.5 text-sm min-w-0">
            <span class="text-zinc-500 shrink-0">${ui.icon("lock", "w-3.5 h-3.5")}</span>
            <span class="font-semibold truncate">${ui.escapeHtml(o.owner_name)}</span>
            <span class="text-zinc-400 truncate min-w-0">· ${ui.escapeHtml(item)}</span>
          </div>
          <div class="text-xs text-zinc-500 truncate">${ui.escapeHtml(where)}</div>
          <div class="text-xs mt-1">${status}</div>
        </div>`;
      })
      .join("");
    return `
      <h2 class="text-sm font-semibold text-zinc-300 mb-1">${i18n.t("dashboard.privateTitle")}</h2>
      <p class="text-xs text-zinc-500 mb-2">${i18n.t("dashboard.privateHint")}</p>
      <div class="grid gap-2 mb-6" style="grid-template-columns:repeat(auto-fill,minmax(260px,1fr))">${rows}</div>`;
  }

  // One line on top: how many queues run, how many stopped and on what.
  function summaryHtml(producing) {
    const slots = producing.flatMap((b) => b.slots);
    if (!slots.length) return "";
    const running = slots.filter((s) => s.running).length;
    const stopped = slots.length - running;
    const lacking = [...new Set(slots.filter((s) => !s.running).flatMap((s) => s.missing))];
    const stale = producing.filter((b) => b.last_logged_at && b.elapsed_seconds >= STALE_SECONDS).length;
    const parts = [
      `<span class="${running ? "text-emerald-400" : "text-zinc-500"}">● ${i18n.t("dashboard.summaryRunning", { n: running })}</span>`,
      `<span class="${stopped ? "text-red-400" : "text-zinc-500"}">● ${i18n.t("dashboard.summaryStopped", { n: stopped })}</span>`,
    ];
    if (lacking.length) parts.push(i18n.t("dashboard.summaryLacking", { items: ui.escapeHtml(lacking.join(", ")) }));
    if (stale) parts.push(`<span class="text-amber-400">⚠ ${i18n.t("dashboard.summaryStale", { n: stale })}</span>`);
    return `<div class="bg-zinc-900 border border-zinc-800 rounded px-3 py-2 mb-4 text-sm flex flex-wrap gap-x-4 gap-y-1">${parts.join("")}</div>`;
  }

  function draw(container, data) {
    const now = i18n.parseDate(data.now);
    const producing = data.buildings.filter((b) => b.slots.length);
    const allStations = data.buildings.filter((b) => b.storage && !b.slots.length);
    const stations = allStations.filter((b) => Object.values(b.logged).some((q) => q >= 0.5));
    const emptyStations = allStations.filter((b) => !stations.includes(b)).map((b) => ui.escapeHtml(b.location ? `${b.name} (${b.location})` : b.name));
    const grid = (list) =>
      `<div class="grid gap-3" style="grid-template-columns:repeat(auto-fill,minmax(280px,1fr))">${list
        .map((b) => buildingHtml(b, now, data.buildings))
        .join("")}</div>`;
    container.querySelector(".dash-body").innerHTML = `
      ${summaryHtml(producing)}
      ${targetsHtml(data.targets)}
      ${privateHtml(data.private_orders, now)}
      <h2 class="text-sm font-semibold text-zinc-300 mb-1">${i18n.t("dashboard.productionTitle")}</h2>
      <p class="text-xs text-zinc-500 mb-2">${i18n.t("dashboard.legend")}</p>
      ${producing.length ? grid(producing) : `<p class="text-sm text-zinc-500">${i18n.t("dashboard.noProduction")}</p>`}
      ${
        stations.length
          ? `<h2 class="text-sm font-semibold text-zinc-300 mt-6 mb-1">${i18n.t("dashboard.stationsTitle")}</h2>
             <p class="text-xs text-zinc-500 mb-2">${i18n.t("dashboard.stationsHint")}</p>${grid(stations)}`
          : ""
      }
      ${emptyStations.length ? `<p class="text-xs text-zinc-500 mt-2">${i18n.t("dashboard.emptyStations", { list: emptyStations.join(", ") })}</p>` : ""}
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
        <p class="text-xs text-zinc-500 mb-2">${i18n.t("dashboard.webhookTrust")}</p>
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
      ? i18n.t("dashboard.webhookLast", { span: formatSpan((Date.now() - i18n.parseDate(status.last_sent_at)) / 1000) })
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
      <p class="text-xs text-zinc-500 mt-2">${i18n.t("dashboard.webhookTrust")}</p>
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
      if (!document.body.contains(container) || !/\/(dashboard|live)$/.test(location.hash)) return stop();
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
