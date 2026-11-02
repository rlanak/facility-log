window.views = window.views || {};

// "Importar do save": pulls a pinned stockpile (e.g. a Material Transfer
// Station) straight out of the game's map save — exact numbers, no OCR. Same
// rule as OCR though: values only pre-fill the form, the user confirms.
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

  async function renderSaveImportUI(container, building, foxholeType, onSaved) {
    const [status, catalog] = await Promise.all([api.saveStatus(), api.listFoxholeResources()]);
    const catalogByKey = Object.fromEntries(catalog.map((r) => [r.key, r]));

    container.innerHTML = "";
    container.appendChild(el("p", { class: "text-xs text-zinc-400 mb-3" }, i18n.t("saveImport.intro")));

    if (!status.parser_available) {
      container.appendChild(el("p", { class: "text-sm text-amber-400" }, i18n.t("saveImport.noParser")));
      return;
    }

    const sourceRow = el("div", { class: "flex flex-wrap items-center gap-2 mb-3" });
    const fileInput = el("input", { type: "file", accept: ".sav", class: "hidden" });
    const uploadBtn = el(
      "button",
      { class: "text-xs border border-zinc-700 hover:border-zinc-500 rounded px-2 py-1" },
      i18n.t("saveImport.upload")
    );
    uploadBtn.addEventListener("click", () => fileInput.click());
    if (status.local_save) {
      const localBtn = el(
        "button",
        { class: "text-xs border border-emerald-800 hover:border-emerald-600 text-emerald-400 rounded px-2 py-1" },
        i18n.t("saveImport.readLocal")
      );
      localBtn.addEventListener("click", () => load(null));
      sourceRow.appendChild(localBtn);
    }
    sourceRow.appendChild(uploadBtn);
    sourceRow.appendChild(fileInput);
    container.appendChild(sourceRow);
    container.appendChild(el("p", { class: "text-[11px] text-zinc-500 mb-3 break-all" }, i18n.t("saveImport.whereIsSave")));

    const body = el("div");
    container.appendChild(body);

    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) load(fileInput.files[0]);
    });

    async function load(file) {
      body.innerHTML = `<p class="text-sm text-zinc-500">${i18n.t("saveImport.reading")}</p>`;
      let pins;
      try {
        pins = await api.listSavePins(file);
      } catch (err) {
        body.innerHTML = "";
        body.appendChild(el("p", { class: "text-sm text-red-400" }, err.message));
        return;
      }
      renderPins(pins);
    }

    function renderPins(pins) {
      body.innerHTML = "";
      if (pins.length === 0) {
        body.appendChild(el("p", { class: "text-sm text-amber-400" }, i18n.t("saveImport.noPins")));
        return;
      }

      // Preselect: the pin this building was linked to last time, else the
      // freshest pin of the same structure type, else the freshest overall.
      const linked = pins.find((p) => p.key === building.save_pin_key);
      const sameType = pins.find((p) => p.building_type_key && p.building_type_key === building.building_type_key);
      let current = linked || sameType || pins[0];

      const select = el(
        "select",
        { class: `${inputClass} w-full mb-3` },
        pins.map((p) =>
          el(
            "option",
            { value: p.key },
            `${p.label} · ${i18n.t("saveImport.readAgo", { ago: ago(p.last_updated_unix) })}${p.key === building.save_pin_key ? " ★" : ""}`
          )
        )
      );
      select.value = current.key;
      body.appendChild(el("label", { class: "block text-xs text-zinc-400 mb-1" }, i18n.t("saveImport.pickPin")));
      body.appendChild(select);

      const rowsEl = el("div", { class: "grid gap-2 mb-3" });
      body.appendChild(rowsEl);
      const saveBtn = el(
        "button",
        { class: "bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold" },
        i18n.t("saveImport.save")
      );
      body.appendChild(saveBtn);

      let rows = [];
      function renderRows() {
        rowsEl.innerHTML = "";
        rows = current.items.map((item) => ({ ...item, include: true, quantityRaw: String(item.quantity) }));
        for (const row of rows) {
          const check = el("input", { type: "checkbox", class: "shrink-0" });
          check.checked = true;
          check.addEventListener("change", () => (row.include = check.checked));

          let nameEl;
          if (row.resource_def_key) {
            const def = catalogByKey[row.resource_def_key];
            nameEl = el("span", { class: "flex-1 min-w-0 truncate text-sm", title: row.codename }, [
              def && def.icon ? el("img", { src: def.icon, class: "inline h-5 w-5 mr-1 align-middle" }) : null,
              def ? i18n.catalogName(def) : row.name || row.codename,
            ]);
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
      }

      select.addEventListener("change", () => {
        current = pins.find((p) => p.key === select.value);
        renderRows();
      });
      renderRows();

      saveBtn.addEventListener("click", async () => {
        const chosen = rows.filter((r) => r.include && r.quantityRaw.trim());
        const unresolved = chosen.filter((r) => !r.resource_def_key && !r.pickedKey);
        if (unresolved.length > 0) {
          ui.toast(i18n.t("saveImport.pickUnknown", { codename: unresolved[0].codename }), true);
          return;
        }
        if (chosen.length === 0) {
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
            chosen.map((r) => {
              const key = r.resource_def_key || r.pickedKey;
              return {
                resource_name: catalogByKey[key].name_en,
                resource_def_key: key,
                quantity_raw: r.quantityRaw.trim(),
                source: "save",
              };
            })
          );
          ui.toast(i18n.t("saveImport.saved", { n: chosen.length }));
          onSaved();
        } catch (err) {
          ui.toast(err.message, true);
        }
      });
    }

    // Running locally, read this PC's save right away.
    if (status.local_save) load(null);
  }

  return { renderSaveImportUI };
})();
