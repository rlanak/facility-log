window.views = window.views || {};

// Private ("Personal") production orders in a building card — see
// app/services/private_orders.py. Logged by hand from the order panel in the
// game (who, recipe, inputs loaded, time left on the running cycle); the
// server works out how many are left and when it's ready. Never touches the
// public stock: the output only counts once logged where it was put.
views.privateOrders = (() => {
  const input =
    "w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";

  function span(seconds) {
    seconds = Math.max(0, Math.round(seconds));
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h${String(m).padStart(2, "0")}`;
    if (m) return `${m}min`;
    return `${seconds}s`;
  }

  // "21:37" today, "10/11 21:37" another day.
  function when(value) {
    const date = i18n.parseDate(value);
    const time = i18n.formatTime(date);
    if (i18n.sameDay(date, new Date())) return time;
    return `${i18n.formatDateTime(date, { day: "2-digit", month: "2-digit" })} ${time}`;
  }

  function qtyLabel(qty, key, defs) {
    const def = defs[key];
    if (def && def.is_liquid && def.liters_per_unit) return `${Math.round(qty * def.liters_per_unit)}L`;
    return Number(qty).toLocaleString(i18n.getLang(), { maximumFractionDigits: 2 });
  }

  // "0:00:52", "1:30", "52" → seconds (the game shows h:mm:ss).
  function parseClock(text) {
    const parts = String(text || "").trim().split(":").filter((p) => p !== "");
    if (!parts.length || parts.some((p) => !/^\d+$/.test(p))) return parts.length ? NaN : 0;
    return parts.reduce((total, p) => total * 60 + parseInt(p, 10), 0);
  }

  function clock(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  // Wall-clock date/time in the user's time zone (Configurações), as the
  // print/Discord message shows it.
  function zoneParts(date, opts) {
    return Object.fromEntries(
      new Intl.DateTimeFormat("en-US", { timeZone: i18n.getTimeZone(), hourCycle: "h23", ...opts })
        .formatToParts(date)
        .map((p) => [p.type, p.value])
    );
  }
  function hhmm(date) {
    const p = zoneParts(date, { hour: "2-digit", minute: "2-digit" });
    return `${p.hour}:${p.minute}`;
  }
  function ymd(date) {
    const p = zoneParts(date, { year: "numeric", month: "2-digit", day: "2-digit" });
    return `${p.year}-${p.month}-${p.day}`;
  }
  // "2026-11-08" + "19:46" in the user's time zone → Date (null if invalid).
  function zonedAt(day, time) {
    const d = /^(\d{4})-(\d{2})-(\d{2})$/.exec((day || "").trim());
    const t = /^(\d{1,2}):(\d{2})$/.exec((time || "").trim());
    if (!d || !t || +t[1] > 23 || +t[2] > 59) return null;
    const guess = Date.UTC(+d[1], +d[2] - 1, +d[3], +t[1], +t[2]);
    const p = zoneParts(new Date(guess), { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const offset = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second) - guess;
    return new Date(guess - offset);
  }
  // Always with the day: "08/11 19:46".
  function stamp(value) {
    const date = i18n.parseDate(value);
    return `${i18n.formatDateTime(date, { day: "2-digit", month: "2-digit" })} ${i18n.formatTime(date)}`;
  }

  function outputsLabel(order) {
    return order.outputs.map((o) => o.name).join(", ") || order.recipe_key;
  }

  const STATUS = {
    running: { pill: "bg-emerald-950/60 text-emerald-300 border-emerald-800", edge: "border-l-emerald-600", bar: "bg-emerald-500", key: "private.statusRunning" },
    ready: { pill: "bg-amber-950/60 text-amber-300 border-amber-700", edge: "border-l-amber-500", bar: "bg-amber-500", key: "private.statusReady" },
    released: { pill: "bg-red-950/60 text-red-300 border-red-800", edge: "border-l-red-600", bar: "bg-red-500", key: "private.statusReleased" },
  };

  // One private order as a block: status, item, who, how much is made (bar),
  // and the dates that matter — when it started, when it's ready, until when
  // it can be retrieved. Same block on the card and on the Dashboard.
  // where: building label (Dashboard); actions: Retirado/edit/delete (card).
  function orderBlock(o, defs, { where = "", actions = false } = {}) {
    const st = STATUS[o.status] || STATUS.running;
    const out = o.outputs[0];
    const def = out && defs[out.resource];
    const done = out ? out.done : 0;
    const total = out && out.total != null ? out.total : null;
    const pct = total ? Math.min(100, Math.round((done / total) * 100)) : o.status === "running" ? 0 : 100;
    const amount = out
      ? total != null && o.status === "running"
        ? `${qtyLabel(done, out.resource, defs)} / ${qtyLabel(total, out.resource, defs)}`
        : qtyLabel(done, out.resource, defs)
      : "";
    let dates = `${i18n.t("private.startedAt", { time: stamp(o.started_at) })}`;
    if (o.status === "running" && o.ready_at) {
      const ready = i18n.parseDate(o.ready_at);
      dates += ` · ${i18n.t("private.readyIn", { time: stamp(o.ready_at), span: span((ready - Date.now()) / 1000) })}`;
    } else if (o.status === "ready") {
      const exp = i18n.parseDate(o.expires_at);
      dates += ` · ${i18n.t("private.readyAtStamp", { time: stamp(o.ready_at) })}<br><span class="text-amber-300">${i18n.t("private.retrieveUntil", { time: stamp(o.expires_at), span: span((exp - Date.now()) / 1000) })}</span>`;
    } else if (o.status === "released") {
      dates += `<br><span class="text-red-300">${i18n.t("private.releasedAt", { time: stamp(o.expires_at) })}</span>`;
    }
    const retrieveCls =
      o.status === "running"
        ? "border border-zinc-700 text-zinc-300 hover:border-zinc-500"
        : "bg-amber-600 hover:bg-amber-500 text-zinc-950 font-semibold";
    return `
      <div class="po-block rounded-md border border-zinc-800 border-l-4 ${st.edge} bg-zinc-950/60 p-2 text-xs min-w-0" data-id="${o.id}">
        <div class="flex items-center gap-1.5 min-w-0">
          <span class="text-zinc-500 shrink-0">${ui.icon("lock", "w-3.5 h-3.5")}</span>
          <span class="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold">${i18n.t("private.label")}</span>
          <span class="ml-auto shrink-0 border rounded-full px-2 py-0.5 text-[10px] font-semibold ${st.pill}">${i18n.t(st.key)}</span>
        </div>
        <div class="flex items-center gap-2 mt-1.5 min-w-0">
          ${def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="w-8 h-8 object-contain shrink-0" />` : ""}
          <div class="min-w-0 flex-1">
            <div class="font-display text-base font-semibold text-zinc-100 truncate leading-tight" title="${ui.escapeHtml(outputsLabel(o))}">${ui.escapeHtml(outputsLabel(o))}</div>
            <div class="text-zinc-400 truncate">${ui.escapeHtml(o.owner_name)}${where ? ` · ${ui.escapeHtml(where)}` : ""}</div>
          </div>
          <span class="font-display text-base font-semibold tabular-nums text-zinc-100 whitespace-nowrap" title="${i18n.t("private.madeHint")}">${amount}</span>
        </div>
        <div class="h-1.5 bg-zinc-800 rounded mt-1.5 overflow-hidden"><div class="h-full ${st.bar}" style="width:${pct}%"></div></div>
        <div class="text-zinc-400 mt-1 leading-snug">${dates}</div>
        ${
          actions
            ? `<div class="flex items-center gap-1 mt-1.5">
                 <button class="po-close inline-flex items-center gap-1 rounded px-2 py-0.5 ${retrieveCls}">${ui.icon("check", "w-3.5 h-3.5")}${i18n.t("private.retrieved")}</button>
                 <span class="flex-1"></span>
                 <button class="po-edit text-zinc-500 hover:text-zinc-100 p-0.5" title="${i18n.t("common.edit")}">${ui.icon("pencil", "w-3.5 h-3.5")}</button>
                 <button class="po-delete text-zinc-600 hover:text-red-400 p-0.5" title="${i18n.t("private.delete")}">✕</button>
               </div>`
            : ""
        }
      </div>`;
  }

  // Ready first (someone has to go retrieve it), then the ones still running
  // by when they're ready, then the ones the game already released.
  function sortOrders(orders) {
    const rank = { ready: 0, running: 1, released: 2 };
    return [...orders].sort(
      (a, b) =>
        (rank[a.status] ?? 1) - (rank[b.status] ?? 1) ||
        String(a.ready_at || a.started_at).localeCompare(String(b.ready_at || b.started_at))
    );
  }

  // The card's "Filas privadas" block: one line per open order + the add button.
  function cardSection({ building, recipes, orders, defs, buildings, resources, onChange, recipeLabel }) {
    const box = ui.el("div", { class: "private-orders mt-2 grid gap-1.5" });
    const list = sortOrders(orders)
      .map((o) => orderBlock(o, defs, { actions: true }))
      .join("");
    box.innerHTML = `
      ${list}
      <button class="po-add inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-emerald-300" title="${i18n.t("private.addHint")}">${ui.icon("lock", "w-3.5 h-3.5")}${i18n.t("private.add")}</button>`;

    const title = (key) => `${i18n.t(key)} — ${i18n.buildingName(building, null)}`;
    box.querySelector(".po-add").addEventListener("click", () =>
      ui.openModal(title("private.newTitle"), (body, close) => form(body, { building, recipes, defs, order: null, recipeLabel, onSaved: () => (close(), onChange()) }), { maxWidth: "max-w-lg" })
    );
    box.querySelectorAll("[data-id]").forEach((row) => {
      const order = orders.find((o) => String(o.id) === row.dataset.id);
      row.querySelector(".po-edit").addEventListener("click", () =>
        ui.openModal(title("private.editTitle"), (body, close) => form(body, { building, recipes, defs, order, recipeLabel, onSaved: () => (close(), onChange()) }), { maxWidth: "max-w-lg" })
      );
      row.querySelector(".po-delete").addEventListener("click", async () => {
        if (!confirm(i18n.t("private.deleteConfirm", { owner: order.owner_name, item: outputsLabel(order) }))) return;
        try {
          await api.deletePrivateOrder(building.id, order.id);
          onChange();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
      row.querySelector(".po-close").addEventListener("click", () =>
        ui.openModal(title("private.retrieveTitle"), (body, close) => retrieveForm(body, { building, order, defs, buildings, resources, onSaved: () => (close(), onChange()) }), { maxWidth: "max-w-lg" })
      );
    });
    return box;
  }

  function solidInputs(recipe, defs) {
    return recipe.inputs.filter((io) => io.resource && !(defs[io.resource] && defs[io.resource].is_liquid));
  }

  // A recipe amount in stock units. The catalog states liquids in liters
  // (see foxhole_data.recipe_io_qty on the server); qtyLabel() takes units.
  function unitsOf(io, defs) {
    const def = defs[io.resource];
    const qty = io.qty ?? 1;
    return def && def.is_liquid && def.liters_per_unit ? qty / def.liters_per_unit : qty;
  }

  // New / edit form. The preview below repeats the server's math so the
  // player sees "32 × 300mm, pronto ~20:49" before saving.
  function form(container, { building, recipes, defs, order, onSaved, recipeLabel }) {
    const me = window.appMe && window.appMe.user ? window.appMe.user.name : "";
    // The card passes the building's own labels (they tell apart recipes
    // that make the same item — see facilityDetail.recipeLabel).
    recipeLabel =
      recipeLabel || ((r) => r.outputs.map((o) => `${o.qty ?? 1}x ${i18n.catalogName(defs[o.resource]) || o.resource}`).join(" + "));
    container.innerHTML = `
      <form class="grid grid-cols-1 gap-3">
        <p class="text-xs text-zinc-500">${i18n.t("private.formHint")}</p>
        <div class="po-print border border-dashed border-zinc-700 rounded p-3 text-xs text-zinc-400 grid grid-cols-1 gap-2">
          <div class="flex flex-wrap items-center gap-2">
            ${ui.icon("camera", "w-4 h-4")}
            <span class="flex-1 min-w-0">${i18n.t("private.printHint")}</span>
            <label class="cursor-pointer border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1 text-zinc-300">${i18n.t("private.printChoose")}
              <input type="file" accept="image/png,image/jpeg,image/webp" class="hidden po-file" />
            </label>
          </div>
          <img class="po-thumb hidden max-h-32 max-w-full object-contain rounded border border-zinc-800" alt="" />
          <p class="po-print-status hidden"></p>
        </div>
        <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.owner")}
          <input name="owner" class="${input}" maxlength="100" value="${ui.escapeHtml(order ? order.owner_name : me)}" placeholder="${i18n.t("private.ownerPlaceholder")}" />
        </label>
        <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.recipe")}
          <select name="recipe" class="${input}">
            ${recipes.map((r) => `<option value="${r.key}" ${order && order.recipe_key === r.key ? "selected" : ""}>${ui.escapeHtml(recipeLabel(r))}</option>`).join("")}
          </select>
        </label>
        <div class="po-inputs grid gap-2"></div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-2">
          <label class="grid gap-1 text-xs text-zinc-400" title="${i18n.t("private.doneBeforeHint")}">${i18n.t("private.doneBefore")}
            <input name="done" inputmode="numeric" class="${input}" placeholder="0" value="${order && order.done_before ? order.done_before : ""}" />
          </label>
          <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.cycleLeft")}
            <input name="cycle" class="${input}" placeholder="0:00:52" value="${order && order.cycle_left_seconds ? clock(order.cycle_left_seconds) : ""}" />
          </label>
          <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.printDate")}
            <input name="day" type="date" class="${input}" value="${ymd(order ? i18n.parseDate(order.started_at) : new Date())}" max="${ymd(new Date())}" />
          </label>
          <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.printTime")}
            <input name="time" class="${input}" placeholder="19:46" value="${hhmm(order ? i18n.parseDate(order.started_at) : new Date())}" />
          </label>
        </div>
        <p class="po-preview text-sm text-zinc-300"></p>
        <div><button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("common.save")}</button></div>
      </form>`;
    const f = container.querySelector("form");
    const inputsBox = f.querySelector(".po-inputs");
    const preview = f.querySelector(".po-preview");
    const originalWhen = `${f.day.value} ${f.time.value}`;
    // Unchanged date/time on an edit keeps the exact start (seconds included).
    const startOf = () =>
      order && `${f.day.value} ${f.time.value}` === originalWhen ? i18n.parseDate(order.started_at) : zonedAt(f.day.value, f.time.value);
    const recipeOf = () => recipes.find((r) => r.key === f.recipe.value);

    function drawInputs(prefill) {
      const recipe = recipeOf();
      const loaded =
        prefill ||
        (order && order.recipe_key === recipe.key ? Object.fromEntries(order.inputs.map((i) => [i.resource, i.loaded])) : {});
      inputsBox.innerHTML = solidInputs(recipe, defs)
        .map((io) => {
          const def = defs[io.resource];
          return `
          <label class="flex items-center gap-2 text-sm">
            ${def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="w-7 h-7 object-contain shrink-0" />` : ""}
            <span class="flex-1 min-w-0 truncate">${ui.escapeHtml(i18n.catalogName(def) || io.resource)}
              <span class="text-xs text-zinc-500">· ${i18n.t("private.perCycle", { qty: io.qty })}</span></span>
            <input data-key="${io.resource}" data-per="${io.qty}" inputmode="decimal" class="w-24 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-right focus:outline-none focus:border-emerald-500"
              value="${loaded[io.resource] ?? ""}" placeholder="0" />
          </label>`;
        })
        .join("");
      inputsBox.querySelectorAll("input").forEach((el) => el.addEventListener("input", drawPreview));
      drawPreview();
    }

    function values() {
      const inputs = {};
      // ui.parseQuantity: the game (and the print reader) writes "1.2k".
      for (const el of inputsBox.querySelectorAll("input")) {
        const n = el.value.trim() === "" ? 0 : ui.parseQuantity(el.value);
        inputs[el.dataset.key] = n;
      }
      const doneText = f.done.value.trim();
      const done = doneText === "" ? 0 : ui.parseQuantity(doneText);
      return { inputs, cycle: parseClock(f.cycle.value), done: Number.isInteger(done) && done >= 0 ? done : NaN };
    }

    function drawPreview() {
      const recipe = recipeOf();
      const { inputs, cycle, done } = values();
      const solids = solidInputs(recipe, defs);
      if (Object.values(inputs).some((n) => isNaN(n) || n < 0) || isNaN(cycle) || isNaN(done)) {
        preview.textContent = "";
        return;
      }
      if (!solids.length) {
        preview.textContent = "";
        return;
      }
      const cycles = Math.min(...solids.map((io) => Math.floor((inputs[io.resource] || 0) / io.qty))) + (cycle > 0 ? 1 : 0);
      const start = startOf() || new Date();
      const ready = new Date(start.getTime() + (cycle + (cycles - (cycle > 0 ? 1 : 0)) * recipe.time_seconds) * 1000);
      const out = recipe.outputs
        .filter((o) => o.resource)
        .map((o) => `${qtyLabel(unitsOf(o, defs) * cycles, o.resource, defs)} ${i18n.catalogName(defs[o.resource]) || o.resource}`)
        .join(" + ");
      let text = cycles > 0 ? i18n.t("private.preview", { cycles, out, time: when(ready) }) : i18n.t("private.previewNone");
      // "Já fabricado" is in items, not cycles: a cycle of Cmats makes 3.
      const perCycle = recipe.outputs.filter((o) => o.resource).map((o) => unitsOf(o, defs))[0] || 1;
      if (done > 0) text += " · " + i18n.t("private.previewDone", { done, total: done + cycles * perCycle });
      preview.textContent = text;
    }

    f.recipe.addEventListener("change", () => drawInputs());
    f.cycle.addEventListener("input", drawPreview);
    f.time.addEventListener("input", drawPreview);
    f.day.addEventListener("input", drawPreview);
    f.done.addEventListener("input", drawPreview);
    drawInputs();

    // Screenshot of the order panel → pre-fill (recipe, inputs, already
    // made, time left). Nothing saves until the user presses Salvar.
    const printBox = f.querySelector(".po-print");
    const thumb = f.querySelector(".po-thumb");
    const printStatus = f.querySelector(".po-print-status");
    function showStatus(text, kind) {
      printStatus.classList.remove("hidden", "text-emerald-400", "text-amber-400", "text-red-400", "text-zinc-400");
      printStatus.classList.add(
        kind === "ok" ? "text-emerald-400" : kind === "warn" ? "text-amber-400" : kind === "error" ? "text-red-400" : "text-zinc-400"
      );
      printStatus.textContent = text;
    }
    async function readPrint(file) {
      if (!file || !file.type.startsWith("image/")) return;
      thumb.src = URL.createObjectURL(file);
      thumb.classList.remove("hidden");
      showStatus(i18n.t("private.printReading"));
      try {
        const image = await api.uploadBuildingImage(building.id, file);
        const r = await api.readPrivateOrderPrint(building.id, image.id, recipes.map((x) => x.key));
        if (!r.available) return showStatus(i18n.t("print.detectUnavailable"), "error");
        if (!r.recipe_key || !recipes.some((x) => x.key === r.recipe_key)) return showStatus(i18n.t("private.printNoRecipe"), "warn");
        f.recipe.value = r.recipe_key;
        drawInputs(r.inputs || {});
        if (r.done_before != null && r.done_before !== "") f.done.value = r.done_before;
        if (r.cycle_left_seconds != null) f.cycle.value = clock(r.cycle_left_seconds);
        drawPreview();
        const missing = solidInputs(recipeOf(), defs).filter((io) => !(r.inputs || {})[io.resource]).length;
        // Only what the recipe used: stray icons elsewhere in the print don't matter.
        const unsure = Boolean(r.unsure);
        const notes = [i18n.t("private.printRead")];
        if (r.cycle_left_seconds == null) notes.push(i18n.t("private.printNoClock"));
        if (missing) notes.push(i18n.t("private.printMissing"));
        if (unsure) notes.push(i18n.t("private.printUnsure"));
        showStatus(notes.join(" "), notes.length > 1 ? "warn" : "ok");
      } catch (err) {
        showStatus(err.message || i18n.t("print.detectFailed"), "error");
      }
    }
    f.querySelector(".po-file").addEventListener("change", (e) => readPrint(e.target.files[0]));
    printBox.addEventListener("dragover", (e) => {
      e.preventDefault();
      printBox.classList.add("border-emerald-500");
    });
    printBox.addEventListener("dragleave", () => printBox.classList.remove("border-emerald-500"));
    printBox.addEventListener("drop", (e) => {
      e.preventDefault();
      printBox.classList.remove("border-emerald-500");
      readPrint(e.dataTransfer.files[0]);
    });
    // Ctrl+V anywhere while the form is open.
    function onPaste(e) {
      if (!document.body.contains(f)) return document.removeEventListener("paste", onPaste);
      const item = [...((e.clipboardData && e.clipboardData.items) || [])].find((i) => i.type.startsWith("image/"));
      if (!item) return;
      e.preventDefault();
      readPrint(item.getAsFile());
    }
    document.addEventListener("paste", onPaste);

    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      const { inputs, cycle, done } = values();
      if (Object.values(inputs).some((n) => isNaN(n) || n < 0) || isNaN(cycle) || isNaN(done)) {
        ui.toast(i18n.t("resources.invalidNumber"), true);
        return;
      }
      const started = startOf();
      if (!started) {
        ui.toast(i18n.t("private.invalidTime"), true);
        return;
      }
      if (started.getTime() > Date.now() + 60000) {
        ui.toast(i18n.t("private.futureTime"), true);
        return;
      }
      const data = {
        owner_name: f.owner.value.trim(),
        recipe_key: f.recipe.value,
        inputs,
        cycle_left_seconds: cycle,
        done_before: done,
        started_at: started.toISOString(),
      };
      try {
        if (order) await api.updatePrivateOrder(building.id, order.id, data);
        else await api.createPrivateOrder(building.id, data);
        document.removeEventListener("paste", onPaste);
        onSaved();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  // "Retirado": close the order and, if wanted, log the output where it
  // went (usually a reserved MTS). Stock is a snapshot, so the new value is
  // the destination's current stock + what came out — editable, confirmed
  // by the user like everything else.
  function retrieveForm(container, { building, order, defs, buildings, resources, onSaved }) {
    const outputs = order.outputs.filter((o) => !(defs[o.resource] && defs[o.resource].is_liquid));
    const stationsFirst = [...buildings].sort((a, b) => Number(b.storage) - Number(a.storage));
    container.innerHTML = `
      <form class="grid gap-3">
        <p class="text-sm">${i18n.t("private.retrieveIntro", { owner: ui.escapeHtml(order.owner_name), item: ui.escapeHtml(outputsLabel(order)) })}</p>
        ${order.status === "released" ? `<p class="text-xs text-amber-400">${i18n.t("private.releasedHint")}</p>` : ""}
        <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("private.logWhere")}
          <select name="dest" class="${input}">
            <option value="">${i18n.t("private.dontLog")}</option>
            ${stationsFirst
              .map((b) => `<option value="${b.id}" ${order.status === "released" && b.id === building.id ? "selected" : ""}>${ui.escapeHtml(b.label)}</option>`)
              .join("")}
          </select>
        </label>
        <div class="po-rows grid gap-2"></div>
        <div><button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("private.retrieveSave")}</button></div>
      </form>`;
    const f = container.querySelector("form");
    const rows = f.querySelector(".po-rows");
    let current = {};

    async function drawRows() {
      const dest = f.dest.value;
      if (!dest || !outputs.length) {
        rows.innerHTML = "";
        return;
      }
      current = {};
      try {
        const stock = await api.getBuildingStock(dest);
        for (const o of outputs) {
          const r = resources.find((x) => x.resource_def_key === o.resource);
          const entry = r && stock.find((s) => s.resource_id === r.id && s.storage === "normal");
          current[o.resource] = entry ? entry.quantity : 0;
        }
      } catch (err) {
        ui.toast(err.message, true);
      }
      // Ready/released = the whole order came out; still running = what's done so far.
      rows.innerHTML = outputs
        .map((o) => {
          const got = order.status === "running" ? o.done : o.total ?? o.done;
          const now = current[o.resource] || 0;
          const def = defs[o.resource];
          return `
          <div class="flex flex-wrap items-center gap-2 text-sm">
            ${def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="w-7 h-7 object-contain shrink-0" />` : ""}
            <span class="flex-1 min-w-0 truncate">${ui.escapeHtml(o.name)}</span>
            <span class="text-xs text-zinc-500">${i18n.t("private.currentPlus", { current: qtyLabel(now, o.resource, defs) })}</span>
            <input data-key="${o.resource}" data-current="${now}" inputmode="decimal" value="${got}"
              class="w-20 bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-sm text-right focus:outline-none focus:border-emerald-500" />
            <span class="po-total text-xs text-zinc-300 w-28 text-right"></span>
          </div>`;
        })
        .join("");
      const total = (el) => {
        const n = ui.parseQuantity(el.value);
        el.parentElement.querySelector(".po-total").textContent = isNaN(n) ? "" : `= ${qtyLabel(Number(el.dataset.current) + n, el.dataset.key, defs)}`;
      };
      rows.querySelectorAll("input").forEach((el) => {
        total(el);
        el.addEventListener("input", () => total(el));
      });
    }

    f.dest.addEventListener("change", drawRows);
    drawRows();

    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        const dest = f.dest.value;
        if (dest) {
          const entries = [];
          for (const el of rows.querySelectorAll("input")) {
            const n = ui.parseQuantity(el.value);
            if (isNaN(n) || n < 0) {
              ui.toast(i18n.t("resources.invalidNumber"), true);
              return;
            }
            if (n === 0) continue;
            const def = defs[el.dataset.key];
            entries.push({
              resource_name: def ? def.name_en : el.dataset.key,
              resource_def_key: el.dataset.key,
              // 2 decimals at most: the server reads "12.345" as twelve thousand.
              quantity_raw: String(Math.round((Number(el.dataset.current) + n) * 100) / 100),
              storage: "normal",
            });
          }
          if (entries.length) await api.addBuildingStock(dest, entries);
        }
        await api.closePrivateOrder(building.id, order.id);
        ui.toast(i18n.t("private.closed"));
        onSaved();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  return { cardSection, orderBlock, sortOrders };
})();
