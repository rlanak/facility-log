window.views = window.views || {};

// "Importar do save": pulls a pinned stockpile (e.g. a Material Transfer
// Station) straight out of the game's map save — exact numbers, no OCR. Same
// rule as OCR though: values only pre-fill the form, the user confirms.
// Two forms: one building (pick/link its pin) and the whole facility at once
// (every building already linked to a pin — renderBulkUI).
views.saveImport = (() => {
  const el = (tag, attrs, children) => ui.el(tag, attrs, children);
  const inputClass =
    "bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500";

  function ago(unix) {
    const seconds = Math.max(0, Math.floor(Date.now() / 1000 - unix));
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (days) return `${days}d${String(hours).padStart(2, "0")}h`;
    if (hours) return `${hours}h${String(minutes).padStart(2, "0")}`;
    return `${minutes}min`;
  }

  // A pinned stockpile lists everything in it: what's logged in the building
  // (normal storage, above 0) but not in the pin anymore ran out — it gets a
  // 0 entry (history kept). `pinKeys` = every catalog key in the pin.
  async function zeroCandidates(buildingId, pinKeys, resources) {
    const stock = await api.getBuildingStock(buildingId).catch(() => []);
    const byId = Object.fromEntries(resources.map((r) => [r.id, r]));
    return stock
      .filter((s) => s.storage === "normal" && s.quantity > 0)
      .map((s) => ({ entry: s, resource: byId[s.resource_id] }))
      .filter(({ resource }) => resource && resource.resource_def_key && !pinKeys.has(resource.resource_def_key))
      .map(({ entry, resource }) => ({
        resource_name: resource.name,
        resource_def_key: resource.resource_def_key,
        label: entry.resource_name,
        quantity: entry.quantity,
      }));
  }
  const zeroEntries = (zeros, pin) =>
    zeros.map((z) => ({ resource_name: z.resource_name, resource_def_key: z.resource_def_key, quantity_raw: "0", source: "save", recorded_at: pinTime(pin) }));

  // When the game last refreshed the pin: logged as the entries' own time
  // (server: crud._entry_time), so numbers from hours ago don't count as
  // fresh on the Dashboard.
  const pinTime = (pin) => (pin && pin.last_updated_unix > 0 ? new Date(pin.last_updated_unix * 1000).toISOString() : null);

  // Unix seconds of the building's newest log of ordinary (non-tank) stock,
  // or 0 — to warn when a pin is older than what's already logged.
  function lastLogUnix(stock) {
    const times = stock.filter((s) => s.storage === "normal").map((s) => i18n.parseDate(s.recorded_at).getTime() / 1000);
    return times.length ? Math.max(...times) : 0;
  }
  // A minute of slack: the pin's own time is what gets logged on import.
  const olderThanLog = (pin, lastUnix) => lastUnix > 0 && pin.last_updated_unix < lastUnix - 60;

  function itemLabel(def, fallback) {
    return [def && def.icon ? el("img", { src: def.icon, class: "inline h-5 w-5 mr-1 align-middle" }) : null, def ? i18n.catalogName(def) : fallback];
  }

  // Shared top of both forms: intro, parser check, where the save comes from.
  async function header(container, onFile) {
    const status = await api.saveStatus();
    container.innerHTML = "";
    container.appendChild(el("p", { class: "text-xs text-zinc-400 mb-3" }, i18n.t("saveImport.intro")));
    if (!status.parser_available) {
      container.appendChild(el("p", { class: "text-sm text-amber-400" }, i18n.t("saveImport.noParser")));
      return null;
    }
    const barSlot = el("div");
    const body = el("div");
    container.appendChild(barSlot);
    container.appendChild(body);
    async function load(file) {
      body.innerHTML = `<p class="text-sm text-zinc-500">${i18n.t("saveImport.reading")}</p>`;
      try {
        onFile(await api.listSavePins(file), body);
      } catch (err) {
        body.innerHTML = "";
        body.appendChild(el("p", { class: "text-sm text-red-400" }, err.message));
      }
    }
    barSlot.appendChild(await saveFile.sourceBar({ localSave: status.local_save, onFile: load }));
    return body;
  }

  // ---- one building -------------------------------------------------------
  // `others`: the facility's buildings [{id, name, save_pin_key}], to show
  // which pin is already linked to which building.
  async function renderSaveImportUI(container, building, foxholeType, onSaved, others = []) {
    const [catalog, resources] = await Promise.all([api.listFoxholeResources(), api.listResources()]);
    const catalogByKey = Object.fromEntries(catalog.map((r) => [r.key, r]));
    const linkedTo = {};
    for (const b of others) if (b.save_pin_key && b.id !== building.id) (linkedTo[b.save_pin_key] ||= []).push(b.name);

    await header(container, (pins, body) => renderPins(pins, body));

    function renderPins(pins, body) {
      body.innerHTML = "";
      if (pins.length === 0) {
        body.appendChild(el("p", { class: "text-sm text-amber-400" }, i18n.t("saveImport.noPins")));
        return;
      }

      // Preselect: the pin this building was linked to last time, else the
      // freshest pin of the same structure type nobody else is linked to,
      // else the freshest overall.
      const linked = pins.find((p) => p.key === building.save_pin_key);
      const sameType =
        pins.find((p) => p.building_type_key && p.building_type_key === building.building_type_key && !linkedTo[p.key]) ||
        pins.find((p) => p.building_type_key && p.building_type_key === building.building_type_key);
      let current = linked || sameType || pins[0];

      const optionText = (p) => {
        const owners = linkedTo[p.key];
        // Several pins often share a name and grid square: the first items
        // tell them apart.
        const names = p.items.map((i) => (i.resource_def_key && catalogByKey[i.resource_def_key] ? i18n.catalogName(catalogByKey[i.resource_def_key]) : i.name || i.codename));
        const contents = names.length ? ` · ${names.slice(0, 2).join(", ")}${names.length > 2 ? ` +${names.length - 2}` : ""}` : "";
        return (
          `${p.label}${contents} · ${i18n.t("saveImport.readAgo", { ago: ago(p.last_updated_unix) })}` +
          (owners ? ` · 📌 ${i18n.t("saveImport.linkedToOther", { names: owners.join(", ") })}` : "") +
          (p.key === building.save_pin_key ? " ★" : "")
        );
      };
      const select = el(
        "select",
        { class: `${inputClass} w-full` },
        pins.map((p) => el("option", { value: p.key }, optionText(p)))
      );
      select.value = current.key;
      const takenNote = el("p", { class: "text-xs text-amber-400 mt-1 hidden" });
      const pickWrap = el("div", { class: "mb-3" }, [
        el("label", { class: "block text-xs text-zinc-400 mb-1" }, i18n.t("saveImport.pickPin")),
        select,
        takenNote,
      ]);
      body.appendChild(pickWrap);
      const syncTaken = () => {
        const owners = linkedTo[current.key];
        takenNote.classList.toggle("hidden", !owners);
        if (owners) takenNote.textContent = i18n.t("saveImport.alreadyLinked", { names: owners.join(", ") });
      };

      // A building linked to a pin stays on it (MTSs hardly ever move): no
      // pin picker, just the link and a way to undo it.
      if (linked) {
        pickWrap.classList.add("hidden");
        const lockBar = el("div", {
          class: "flex flex-wrap items-center gap-2 mb-3 rounded border border-emerald-900 bg-emerald-950/30 px-3 py-2 text-sm",
        }, [
          el("span", { class: "flex-1 min-w-0" }, [
            el("span", { class: "text-emerald-400" }, `📌 ${i18n.t("saveImport.lockedTo")} `),
            el("span", {}, linked.label),
            el("span", { class: "text-xs text-zinc-500" }, ` · ${i18n.t("saveImport.readAgo", { ago: ago(linked.last_updated_unix) })}`),
          ]),
        ]);
        const unlinkBtn = el(
          "button",
          { type: "button", class: "text-xs text-zinc-400 hover:text-red-400 border border-zinc-700 rounded px-2 py-1" },
          i18n.t("saveImport.unlink")
        );
        unlinkBtn.addEventListener("click", async () => {
          if (!confirm(i18n.t("saveImport.unlinkConfirm"))) return;
          try {
            await api.linkSavePin(building.id, null);
            building.save_pin_key = null;
            lockBar.remove();
            pickWrap.classList.remove("hidden");
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
        lockBar.appendChild(unlinkBtn);
        body.insertBefore(lockBar, pickWrap);
      } else if (building.save_pin_key) {
        body.insertBefore(
          el("p", { class: "text-xs text-amber-400 mb-2" }, i18n.t("saveImport.linkedMissing")),
          pickWrap
        );
      }

      const staleEl = el("p", { class: "text-xs text-amber-400 mb-3 hidden" });
      const rowsEl = el("div", { class: "grid gap-2 mb-3" });
      const zeroEl = el("div", { class: "mb-3" });
      body.appendChild(staleEl);
      body.appendChild(rowsEl);
      body.appendChild(zeroEl);
      // The pin's reading is older than what the building already has
      // logged: importing would put old numbers over newer ones.
      let lastLog = 0;
      const syncStale = () => {
        const stale = olderThanLog(current, lastLog);
        staleEl.classList.toggle("hidden", !stale);
        if (stale) staleEl.textContent = i18n.t("saveImport.olderThanLog", { ago: ago(current.last_updated_unix), last: ago(lastLog) });
      };
      api
        .getBuildingStock(building.id)
        .then((stock) => {
          lastLog = lastLogUnix(stock);
          syncStale();
        })
        .catch(() => {});
      const saveBtn = el(
        "button",
        { class: "bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold" },
        i18n.t("saveImport.save")
      );
      body.appendChild(saveBtn);

      let rows = [];
      let zeros = [];
      let zeroOn = true;
      async function renderZeros() {
        const pinKeys = new Set(current.items.map((i) => i.resource_def_key).filter(Boolean));
        zeros = await zeroCandidates(building.id, pinKeys, resources);
        zeroEl.innerHTML = "";
        if (!zeros.length) return;
        const check = el("input", { type: "checkbox", class: "shrink-0" });
        check.checked = zeroOn;
        check.addEventListener("change", () => (zeroOn = check.checked));
        zeroEl.appendChild(
          el("label", { class: "flex items-start gap-2 text-xs text-amber-400 cursor-pointer" }, [
            check,
            el("span", {}, i18n.t("saveImport.zeroMissing", { items: zeros.map((z) => z.label).join(", ") })),
          ])
        );
      }

      function renderRows() {
        rowsEl.innerHTML = "";
        rows = current.items.map((item) => ({ ...item, include: true, quantityRaw: String(item.quantity) }));
        for (const row of rows) {
          const check = el("input", { type: "checkbox", class: "shrink-0" });
          check.checked = true;
          check.addEventListener("change", () => (row.include = check.checked));

          let nameEl;
          if (row.resource_def_key) {
            nameEl = el("span", { class: "flex-1 min-w-0 truncate text-sm", title: row.codename }, itemLabel(catalogByKey[row.resource_def_key], row.name || row.codename));
          } else {
            // Codename the catalog doesn't map yet — the user picks the
            // resource once and it's remembered (codename_aliases).
            nameEl = el(
              "select",
              { class: `${inputClass} flex-1 min-w-0` },
              [el("option", { value: "" }, i18n.t("saveImport.unknownItem", { codename: row.codename }))].concat(
                catalog
                  .slice()
                  .sort((a, b) => i18n.catalogName(a).localeCompare(i18n.catalogName(b)))
                  .map((r) => el("option", { value: r.key }, i18n.catalogName(r)))
              )
            );
            nameEl.addEventListener("change", () => {
              row.pickedKey = nameEl.value || null;
            });
          }

          const qty = el("input", { class: `${inputClass} w-28 shrink-0` });
          qty.value = row.quantityRaw;
          qty.addEventListener("input", () => (row.quantityRaw = qty.value));

          rowsEl.appendChild(el("div", { class: "flex items-center gap-2 min-w-0" }, [check, nameEl, qty]));
        }
        if (rows.length === 0) {
          rowsEl.appendChild(el("p", { class: "text-sm text-zinc-500" }, i18n.t("saveImport.emptyPin")));
        }
        renderZeros();
      }

      select.addEventListener("change", () => {
        current = pins.find((p) => p.key === select.value);
        syncTaken();
        syncStale();
        renderRows();
      });
      syncTaken();
      renderRows();

      saveBtn.addEventListener("click", async () => {
        const chosen = rows.filter((r) => r.include && r.quantityRaw.trim());
        const unresolved = chosen.filter((r) => !r.resource_def_key && !r.pickedKey);
        if (unresolved.length > 0) {
          ui.toast(i18n.t("saveImport.pickUnknown", { codename: unresolved[0].codename }), true);
          return;
        }
        // An item just named for an unknown code is in the pin after all:
        // it gets the pin's number, never a 0 on top of it.
        const named = new Set(chosen.map((r) => r.pickedKey).filter(Boolean));
        const zeroing = zeroOn ? zeros.filter((z) => !named.has(z.resource_def_key)) : [];
        if (chosen.length === 0 && zeroing.length === 0) {
          ui.toast(i18n.t("saveImport.nothingToSave"), true);
          return;
        }
        try {
          for (const r of chosen.filter((r) => r.pickedKey)) {
            await api.setCodenameAlias({ codename: r.codename, resource_def_key: r.pickedKey });
          }
          await api.linkSavePin(building.id, current.key, current.location);
          await api.addBuildingStock(
            building.id,
            chosen
              .map((r) => {
                const key = r.resource_def_key || r.pickedKey;
                return {
                  resource_name: catalogByKey[key].name_en,
                  resource_def_key: key,
                  quantity_raw: r.quantityRaw.trim(),
                  source: "save",
                  recorded_at: pinTime(current),
                };
              })
              .concat(zeroEntries(zeroing, current))
          );
          ui.toast(i18n.t("saveImport.saved", { n: chosen.length + zeroing.length }));
          onSaved();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    }
  }

  // ---- whole facility -----------------------------------------------------
  // Every building already linked to a pin, read from one save: current vs
  // save value side by side, each value editable, each building opt-out.
  // Codenames the catalog doesn't know are skipped here (named once in the
  // building's own form).
  async function renderBulkUI(container, buildings, onSaved) {
    const [catalog, resources] = await Promise.all([api.listFoxholeResources(), api.listResources()]);
    const catalogByKey = Object.fromEntries(catalog.map((r) => [r.key, r]));
    const linked = buildings.filter((b) => b.save_pin_key);
    await header(container, (pins, body) => draw(pins, body));

    async function draw(pins, body) {
      body.innerHTML = "";
      const pinByKey = Object.fromEntries(pins.map((p) => [p.key, p]));
      const plans = [];
      const list = el("div", { class: "grid gap-3 mb-3" });
      body.appendChild(list);

      for (const b of linked) {
        const pin = pinByKey[b.save_pin_key];
        const card = el("div", { class: "rounded border border-zinc-800 bg-zinc-950/40 p-2" });
        list.appendChild(card);
        if (!pin) {
          card.appendChild(el("p", { class: "text-sm" }, [el("span", { class: "font-semibold" }, b.name), " "]));
          card.appendChild(el("p", { class: "text-xs text-amber-400" }, i18n.t("saveImport.bulkPinMissing")));
          continue;
        }
        const stock = await api.getBuildingStock(b.id).catch(() => []);
        const byId = Object.fromEntries(resources.map((r) => [r.id, r]));
        const currentByKey = {};
        for (const s of stock) {
          const r = byId[s.resource_id];
          if (s.storage === "normal" && r && r.resource_def_key) currentByKey[r.resource_def_key] = s.quantity;
        }
        const known = pin.items.filter((i) => i.resource_def_key);
        const unknown = pin.items.filter((i) => !i.resource_def_key);
        // An unknown code may be one of the logged items under a name the
        // catalog doesn't have yet: with one in the pin, nothing is zeroed.
        const zeros = unknown.length ? [] : await zeroCandidates(b.id, new Set(known.map((i) => i.resource_def_key)), resources);
        // Pin read before the building's last log: left out unless ticked.
        const lastLog = lastLogUnix(stock);
        const stale = olderThanLog(pin, lastLog);
        const plan = { building: b, pin, include: !stale, rows: [] };
        plans.push(plan);

        const check = el("input", { type: "checkbox", class: "shrink-0" });
        check.checked = plan.include;
        check.addEventListener("change", () => {
          plan.include = check.checked;
          table.classList.toggle("opacity-40", !check.checked);
        });
        card.appendChild(
          // Phone: the pin goes under the building's name instead of squeezing it.
          el("label", { class: "flex flex-wrap sm:flex-nowrap items-center gap-x-2 cursor-pointer min-w-0" }, [
            check,
            el("span", { class: "font-semibold truncate flex-1 sm:flex-none min-w-0" }, b.name),
            el("span", { class: "text-xs text-zinc-500 truncate w-full sm:w-auto min-w-0" }, `${pin.label} · ${i18n.t("saveImport.readAgo", { ago: ago(pin.last_updated_unix) })}`),
          ])
        );
        if (stale) card.appendChild(el("p", { class: "text-xs text-amber-400 mt-1" }, `⚠ ${i18n.t("saveImport.bulkOlder", { last: ago(lastLog) })}`));
        const table = el("div", { class: "mt-2 grid gap-1 text-sm" + (stale ? " opacity-40" : "") });
        card.appendChild(table);
        const addRow = (key, label, before, after, isZero) => {
          const row = { key, quantityRaw: String(after) };
          plan.rows.push(row);
          const input = el("input", { class: `${inputClass} w-20 sm:w-24 shrink-0 py-0.5 text-right tabular-nums` });
          input.value = row.quantityRaw;
          input.addEventListener("input", () => (row.quantityRaw = input.value));
          const changed = before !== after;
          table.appendChild(
            el("div", { class: "flex items-center gap-2 min-w-0" }, [
              el("span", { class: "flex-1 min-w-0 break-words sm:truncate" + (isZero ? " text-amber-400" : "") }, label),
              el("span", { class: "w-12 sm:w-20 shrink-0 text-right tabular-nums text-zinc-500" }, before == null ? "—" : String(before)),
              el("span", { class: changed ? "text-emerald-400" : "text-zinc-600" }, "→"),
              input,
            ])
          );
        };
        for (const item of known) {
          addRow(item.resource_def_key, itemLabel(catalogByKey[item.resource_def_key], item.name), currentByKey[item.resource_def_key] ?? null, item.quantity, false);
        }
        for (const z of zeros) addRow(z.resource_def_key, `${z.label} (${i18n.t("saveImport.bulkGone")})`, z.quantity, 0, true);
        if (!known.length && !zeros.length) table.appendChild(el("p", { class: "text-xs text-zinc-500" }, i18n.t("saveImport.emptyPin")));
        if (unknown.length) {
          table.appendChild(
            el(
              "p",
              { class: "text-xs text-amber-400" },
              `${i18n.t("saveImport.bulkUnknown", { codes: unknown.map((u) => u.codename).join(", ") })} ${i18n.t("saveImport.bulkNoZero")}`
            )
          );
        }
      }

      if (!linked.length) list.appendChild(el("p", { class: "text-sm text-zinc-500" }, i18n.t("saveImport.bulkNone")));
      if (!plans.length) return;
      const saveBtn = el(
        "button",
        { class: "bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold" },
        i18n.t("saveImport.bulkSave")
      );
      body.appendChild(saveBtn);
      saveBtn.addEventListener("click", async () => {
        const chosen = plans.filter((p) => p.include && p.rows.length);
        if (!chosen.length) {
          ui.toast(i18n.t("saveImport.nothingToSave"), true);
          return;
        }
        saveBtn.disabled = true;
        try {
          for (const p of chosen) {
            const entries = p.rows
              .filter((r) => r.quantityRaw.trim())
              .map((r) => ({
                resource_name: catalogByKey[r.key] ? catalogByKey[r.key].name_en : r.key,
                resource_def_key: r.key,
                quantity_raw: r.quantityRaw.trim(),
                source: "save",
                recorded_at: pinTime(p.pin),
              }));
            if (entries.length) await api.addBuildingStock(p.building.id, entries);
          }
          ui.toast(i18n.t("saveImport.bulkSaved", { n: chosen.length }));
          onSaved();
        } catch (err) {
          saveBtn.disabled = false;
          ui.toast(err.message, true);
        }
      });
    }
  }

  return { renderSaveImportUI, renderBulkUI };
})();
