window.views = window.views || {};

views.print = (() => {
  function el(tag, attrs, children) {
    return ui.el(tag, attrs, children);
  }

  async function renderCaptureUI(container, building, onSaved) {
    let ocrAvailable = false;
    let detectAvailable = false;
    let engineMessage = i18n.t("print.engineNone");
    // "IA do meu computador" (web version): this browser reads the numbers
    // with the user's own Ollama; the server reader stays as the fallback.
    const myAI = window.appMe && window.appMe.auth_enabled ? personalAI.active() : null;
    let myAIFailed = false;
    try {
      const status = await api.ocrStatus();
      ocrAvailable = status.available || Boolean(myAI);
      detectAvailable = status.stockpile_detect_available;
      // Which engine reads the numbers is picked in Configurações; say which
      // one is actually in use (it falls back when the chosen one is down).
      const name = (key) => i18n.t(`settings.provider.${key}`);
      if (myAI) engineMessage = i18n.t("print.engineMyAI", { model: myAI.model });
      else if (!status.effective_provider) engineMessage = i18n.t("print.engineNone");
      else if (status.effective_provider !== status.provider)
        engineMessage = i18n.t("print.engineFallback", { chosen: name(status.provider), engine: name(status.effective_provider) });
      else engineMessage = i18n.t("print.engine", { engine: name(status.effective_provider) });
    } catch (_) {}

    // One number: with the user's own AI when it's on (falling back to the
    // server reader if it doesn't answer), else with the server.
    async function readNumber(box) {
      if (myAI && !myAIFailed) {
        try {
          return await personalAI.read(imgEl, box, myAI);
        } catch (_) {
          myAIFailed = true;
          ui.toast(i18n.t("print.myAIFailed"), true);
        }
      }
      const result = await api.readImageCrop(image.id, box);
      return result.guess ? result.raw_text || result.guess : "";
    }

    const resources = await api.listResources();
    // The whole Foxhole catalog too, so an unrecognized slot can be named as
    // any catalog item (and get its catalog link) — not only resources the
    // user already has.
    const catalog = await api.listFoxholeResources().catch(() => []);
    // What's logged in this building now: a STOCKPILE screenshot lists every
    // item there is, so anything logged here but not in the print can be
    // zeroed on save (opt-in checkbox, remembered in this browser).
    const currentStock = (await api.getBuildingStock(building.id).catch(() => [])).filter(
      (s) => s.storage === "normal" && s.quantity > 0
    );
    let zeroMissing = true;
    try {
      zeroMissing = localStorage.getItem("printZeroMissing") !== "0";
    } catch (_) {}

    let image = null; // {id, url, naturalWidth, naturalHeight}
    let crops = []; // {localId, x,y,w,h, thumbDataUrl, resourceName, resourceDefKey, quantityRaw, ambiguous, rivalNameEn}
    let nextLocalId = 1;
    let scaleX = 1;
    let scaleY = 1;
    let mode = detectAvailable ? "auto" : "manual";

    container.innerHTML = "";
    container.appendChild(
      el("p", { class: "text-xs mb-2 " + (engineMessage.startsWith("✓") ? "text-emerald-400" : "text-amber-400") }, engineMessage)
    );

    // Usually the print is already in the clipboard: Ctrl+V anywhere in the
    // modal loads it (see the paste listener below). The file picker only
    // opens from its own button — clicking the zone used to open it, which
    // got in the way of pasting.
    const fileInput = el("input", { type: "file", accept: "image/png,image/jpeg,image/webp", class: "hidden" });
    const pickFileBtn = el(
      "button",
      { type: "button", class: "mt-3 text-xs border border-zinc-700 hover:border-zinc-500 text-zinc-300 rounded px-3 py-1.5" },
      i18n.t("print.pickFile")
    );
    pickFileBtn.addEventListener("click", () => fileInput.click());
    const dropzone = el("div", {
      class: "border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center text-sm text-zinc-400",
    }, [el("p", {}, i18n.t("print.dropzone")), pickFileBtn]);

    const stageWrap = el("div", { class: "mt-4 hidden" });
    const modeToggle = el("div", { class: "flex gap-2 mb-2" });
    const autoModeBtn = el("button", { type: "button", class: "text-xs px-2 py-1 rounded border" }, i18n.t("print.modeAuto"));
    const manualModeBtn = el("button", { type: "button", class: "text-xs px-2 py-1 rounded border" }, i18n.t("print.modeManual"));
    const stage = el("div", { class: "relative inline-block max-w-full" });
    const imgEl = el("img", { class: "max-w-full block rounded" });
    const canvas = el("canvas", { class: "absolute top-0 left-0 cursor-crosshair" });
    const dragHintEl = el("p", { class: "text-xs text-zinc-500 mt-2" }, i18n.t("print.dragHint"));
    stage.appendChild(imgEl);
    stage.appendChild(canvas);
    if (detectAvailable) {
      modeToggle.appendChild(autoModeBtn);
      modeToggle.appendChild(manualModeBtn);
      stageWrap.appendChild(modeToggle);
    }
    stageWrap.appendChild(stage);
    stageWrap.appendChild(dragHintEl);
    // Detection progress: finding the items, then (with the user's own AI)
    // reading each number — the slow part, shown as n/total.
    const progressEl = el("div", { class: "hidden mt-2 flex items-center gap-2 text-sm text-emerald-400" });
    stageWrap.appendChild(progressEl);
    function showProgress(text, busy = true) {
      progressEl.classList.remove("hidden");
      progressEl.innerHTML = (busy ? ui.icon("refresh", "w-4 h-4 animate-spin") : ui.icon("check", "w-4 h-4")) + `<span></span>`;
      progressEl.querySelector("span").textContent = text;
    }
    const hideProgress = () => progressEl.classList.add("hidden");
    // Each detection run gets a number: a newer run (or a new image) makes an
    // older one stop instead of adding its items on top.
    let detectRun = 0;

    function updateModeUI() {
      const activeCls = "bg-emerald-700 border-emerald-700 text-white";
      const inactiveCls = "border-zinc-700 text-zinc-400 hover:text-zinc-200";
      autoModeBtn.className = "text-xs px-2 py-1 rounded border " + (mode === "auto" ? activeCls : inactiveCls);
      manualModeBtn.className = "text-xs px-2 py-1 rounded border " + (mode === "manual" ? activeCls : inactiveCls);
      dragHintEl.textContent = mode === "auto" ? i18n.t("print.dragHintAuto") : i18n.t("print.dragHint");
    }
    autoModeBtn.addEventListener("click", () => {
      mode = "auto";
      updateModeUI();
    });
    manualModeBtn.addEventListener("click", () => {
      mode = "manual";
      updateModeUI();
    });
    updateModeUI();

    const cropsListEl = el("div", { class: "grid gap-2 mt-4" });
    const saveBtn = el("button", {
      class: "hidden bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold mt-4",
    }, i18n.t("print.saveEntries"));

    container.appendChild(dropzone);
    container.appendChild(fileInput);
    container.appendChild(stageWrap);
    const zeroBox = el("div", { class: "hidden mt-3 rounded border border-zinc-800 bg-zinc-900/60 p-2 text-sm" });
    container.appendChild(cropsListEl);
    container.appendChild(zeroBox);
    container.appendChild(saveBtn);

    dropzone.addEventListener("dragover", (e) => e.preventDefault());
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });
    // Whole page while this form is open; text pastes (e.g. into a
    // quantity field) pass through untouched.
    document.addEventListener("paste", function onPaste(e) {
      if (!document.body.contains(container)) return document.removeEventListener("paste", onPaste);
      const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
      if (!item) return;
      e.preventDefault();
      handleFile(item.getAsFile());
    });
    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });

    async function handleFile(file) {
      try {
        const uploaded = await api.uploadBuildingImage(building.id, file);
        image = uploaded;
        detectRun++;
        crops = [];
        hideProgress();
        renderCropsList();
        imgEl.src = uploaded.url;
        await new Promise((resolve, reject) => {
          imgEl.onload = resolve;
          imgEl.onerror = reject;
        });
        stageWrap.classList.remove("hidden");
        setupCanvas();
        ui.toast(i18n.t("print.uploaded"));
      } catch (err) {
        ui.toast(err.message || i18n.t("print.uploadFailed"), true);
      }
    }

    function setupCanvas() {
      // naturalWidth/naturalHeight are known right after onload regardless of
      // whether the element has been laid out/painted yet, unlike clientWidth —
      // so we compute the display size ourselves instead of reading it back.
      const containerWidth = container.clientWidth || 700;
      const maxDisplayWidth = Math.min(containerWidth, 700);
      const scale = Math.min(1, maxDisplayWidth / imgEl.naturalWidth);
      const displayWidth = Math.round(imgEl.naturalWidth * scale);
      const displayHeight = Math.round(imgEl.naturalHeight * scale);

      imgEl.style.width = displayWidth + "px";
      imgEl.style.height = displayHeight + "px";
      scaleX = imgEl.naturalWidth / displayWidth;
      scaleY = imgEl.naturalHeight / displayHeight;

      canvas.width = displayWidth;
      canvas.height = displayHeight;
      canvas.style.width = displayWidth + "px";
      canvas.style.height = displayHeight + "px";
      redrawCanvas();
      attachCanvasListenersOnce();
    }

    let listenersAttached = false;

    function attachCanvasListenersOnce() {
      if (listenersAttached) return;
      listenersAttached = true;

      const ctx = canvas.getContext("2d");
      let dragging = false;
      let start = null;

      function pos(e) {
        const rect = canvas.getBoundingClientRect();
        return { x: e.clientX - rect.left, y: e.clientY - rect.top };
      }

      canvas.addEventListener("mousedown", (e) => {
        dragging = true;
        start = pos(e);
      });
      canvas.addEventListener("mousemove", (e) => {
        if (!dragging) return;
        const p = pos(e);
        redrawCanvas();
        ctx.strokeStyle = theme.rgb("emerald", 400);
        ctx.lineWidth = 2;
        ctx.strokeRect(start.x, start.y, p.x - start.x, p.y - start.y);
      });
      window.addEventListener("mouseup", (e) => {
        if (!dragging) return;
        dragging = false;
        const p = pos(e);
        const rectX = Math.min(start.x, p.x);
        const rectY = Math.min(start.y, p.y);
        const rectW = Math.abs(p.x - start.x);
        const rectH = Math.abs(p.y - start.y);
        if (rectW < 6 || rectH < 6) {
          redrawCanvas();
          return;
        }
        if (mode === "auto") {
          autoDetectPanel(rectX, rectY, rectW, rectH);
        } else {
          addCrop(rectX, rectY, rectW, rectH);
        }
      });
    }

    function redrawCanvas() {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = theme.rgb("emerald", 500);
      ctx.lineWidth = 2;
      ctx.font = "12px monospace";
      ctx.fillStyle = theme.rgb("emerald", 500);
      crops.forEach((c, i) => {
        ctx.strokeRect(c.displayX, c.displayY, c.displayW, c.displayH);
        ctx.fillText(String(i + 1), c.displayX + 2, c.displayY + 12);
      });
    }

    async function addCrop(displayX, displayY, displayW, displayH) {
      const box = {
        x: Math.round(displayX * scaleX),
        y: Math.round(displayY * scaleY),
        width: Math.round(displayW * scaleX),
        height: Math.round(displayH * scaleY),
      };

      const thumbCanvas = document.createElement("canvas");
      thumbCanvas.width = box.width;
      thumbCanvas.height = box.height;
      thumbCanvas.getContext("2d").drawImage(
        imgEl, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height
      );

      const crop = {
        localId: nextLocalId++,
        displayX,
        displayY,
        displayW,
        displayH,
        box,
        thumbDataUrl: thumbCanvas.toDataURL("image/png"),
        resourceName: "",
        quantityRaw: "",
      };
      crops.push(crop);
      redrawCanvas();
      renderCropsList();

      if (ocrAvailable) {
        try {
          const guess = await readNumber(box);
          if (guess && !crop.quantityRaw) {
            crop.quantityRaw = guess;
            renderCropsList();
          }
        } catch (_) {}
      }
    }

    async function autoDetectPanel(displayX, displayY, displayW, displayH) {
      const box = {
        x: Math.round(displayX * scaleX),
        y: Math.round(displayY * scaleY),
        width: Math.round(displayW * scaleX),
        height: Math.round(displayH * scaleY),
      };
      const run = ++detectRun;
      redrawCanvas();
      // The server also reads the numbers when the user's own AI is off, so
      // this one step can take a while: count the seconds.
      const started = Date.now();
      const label = myAI ? i18n.t("print.detecting") : i18n.t("print.detectingReading");
      showProgress(label);
      const ticker = setInterval(() => {
        if (run === detectRun) showProgress(`${label} ${Math.round((Date.now() - started) / 1000)}s`);
      }, 1000);
      try {
        // With the user's own AI the server only finds the items; the
        // numbers are read below, from this browser.
        const result = await api.detectStockpile(image.id, box, !myAI);
        clearInterval(ticker);
        if (run !== detectRun) return;
        if (!result.available) {
          hideProgress();
          ui.toast(i18n.t("print.detectUnavailable"), true);
          return;
        }
        if (result.items.length === 0) {
          hideProgress();
          ui.toast(i18n.t("print.detectNone"), true);
          return;
        }
        // A new detection replaces the previous one's items (marking the
        // panel again used to list everything twice); manual crops stay.
        crops = crops.filter((c) => !c.iconBox);
        const added = result.items.map(addDetectedCrop);
        redrawCanvas();
        renderCropsList();
        if (myAI) {
          const toRead = added.filter((c) => c.numberBox && c.numberBox.width);
          for (const [i, crop] of toRead.entries()) {
            if (run !== detectRun) return;
            showProgress(i18n.t("print.readingProgress", { n: i + 1, total: toRead.length }));
            try {
              const guess = await readNumber(crop.numberBox);
              if (run !== detectRun) return;
              if (guess && !crop.quantityRaw) {
                crop.quantityRaw = guess;
                renderCropsList();
              }
            } catch (_) {}
          }
        }
        showProgress(i18n.t("print.detected", { n: result.items.length }), false);
      } catch (err) {
        clearInterval(ticker);
        if (run !== detectRun) return;
        hideProgress();
        ui.toast(err.message || i18n.t("print.detectFailed"), true);
      }
    }

    function addDetectedCrop(item) {
      const box = { x: item.box_x, y: item.box_y, width: item.box_width, height: item.box_height };
      const thumbCanvas = document.createElement("canvas");
      thumbCanvas.width = box.width;
      thumbCanvas.height = box.height;
      thumbCanvas.getContext("2d").drawImage(
        imgEl, box.x, box.y, box.width, box.height, 0, 0, box.width, box.height
      );

      // resource_def_key null = a slot with a quantity whose item wasn't
      // recognized (e.g. a mod-redrawn icon): the user names it.
      const existing = item.resource_def_key && resources.find((r) => r.resource_def_key === item.resource_def_key);
      const catalogName = i18n.getCatalogLang() === "en-US" ? item.name_en : item.name_pt || item.name_en;
      const detectedName = existing ? existing.name : catalogName || "";

      const crop = {
        detectedName,
        iconBox: box,
        numberBox: { x: item.number_x, y: item.number_y, width: item.number_width, height: item.number_height },
        localId: nextLocalId++,
        displayX: box.x / scaleX,
        displayY: box.y / scaleY,
        displayW: box.width / scaleX,
        displayH: box.height / scaleY,
        box,
        thumbDataUrl: thumbCanvas.toDataURL("image/png"),
        resourceName: detectedName,
        resourceDefKey: item.resource_def_key,
        // quantity_guess strips non-digit characters, which also strips a
        // k/K/m/M magnitude suffix ("53k" -> "53") -- using it as the
        // pre-fill would silently save a value 1000x too small. Prefer the
        // full raw OCR text (keeps the suffix) whenever it found a real
        // digit at all; quantity_guess is only truthy in that same case
        // (see readers.sanitize), so this never shows raw garbage.
        quantityRaw: item.quantity_guess ? item.quantity_raw : "",
        ambiguous: item.ambiguous,
        unknown: !item.resource_def_key,
        rivalNameEn: item.rival_name_en,
      };
      crops.push(crop);
      return crop;
    }

    function renderCropsList() {
      cropsListEl.innerHTML = "";
      crops.forEach((crop, i) => {
        const wrap = el("div", {
          class: "bg-zinc-900 border rounded p-2 " + (crop.ambiguous ? "border-amber-700" : "border-zinc-800"),
        });
        const row = el("div", { class: "flex items-center gap-2" });
        const thumb = el("img", { src: crop.thumbDataUrl, class: "h-10 w-auto rounded border border-zinc-700" });
        const label = el("span", { class: "text-xs text-zinc-500 w-4" }, String(i + 1));

        const nameInput = el("input", {
          list: "print-resources-datalist",
          placeholder: i18n.t("print.resourcePlaceholder"),
          class: "flex-1 min-w-0 bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500",
        });
        nameInput.value = crop.resourceName;
        nameInput.addEventListener("input", () => {
          crop.resourceName = nameInput.value;
          renderZeroBox();
        });

        const qtyInput = el("input", {
          placeholder: i18n.t("print.qtyPlaceholder"),
          class: "w-28 shrink-0 bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500",
        });
        qtyInput.value = crop.quantityRaw;
        qtyInput.addEventListener("input", () => {
          crop.quantityRaw = qtyInput.value;
          renderZeroBox();
        });

        const removeBtn = el("button", { class: "text-zinc-500 hover:text-red-400 px-1" }, "✕");
        removeBtn.addEventListener("click", () => {
          crops = crops.filter((c) => c.localId !== crop.localId);
          redrawCanvas();
          renderCropsList();
        });

        row.appendChild(label);
        row.appendChild(thumb);
        row.appendChild(nameInput);
        row.appendChild(qtyInput);
        row.appendChild(removeBtn);
        wrap.appendChild(row);
        if (crop.unknown || crop.ambiguous) {
          const note = crop.unknown
            ? i18n.t("print.unknownNote")
            : crop.rivalNameEn
              ? i18n.t("print.ambiguousNote", { rival: crop.rivalNameEn })
              : i18n.t("print.checkNote");
          wrap.appendChild(el("p", { class: "text-[11px] text-amber-400 mt-1 ml-6" }, note));
        }
        cropsListEl.appendChild(wrap);
      });

      if (!document.getElementById("print-resources-datalist")) {
        const datalist = el(
          "datalist",
          { id: "print-resources-datalist" },
          resources
            .map((r) => r.name)
            .concat(catalog.map((d) => i18n.catalogName(d)).filter((n) => !resources.some((r) => r.name === n)))
            .map((n) => el("option", { value: n }))
        );
        container.appendChild(datalist);
      }

      saveBtn.classList.toggle("hidden", crops.length === 0);
      renderZeroBox();
    }

    // Logged items the print doesn't list — a preview of what the server
    // will zero (it does its own matching on save).
    function missingFromPrint() {
      const keptIds = new Set();
      for (const c of crops) {
        if (!c.resourceName.trim() || !c.quantityRaw.trim()) continue;
        const key = confirmedDefKey(c);
        const lower = c.resourceName.trim().toLowerCase();
        for (const r of resources) {
          if ((key && r.resource_def_key === key) || r.name.toLowerCase() === lower) keptIds.add(r.id);
        }
        for (const s of currentStock) if (s.resource_name.toLowerCase() === lower) keptIds.add(s.resource_id);
      }
      return currentStock.filter((s) => !keptIds.has(s.resource_id));
    }

    function renderZeroBox() {
      const missing = crops.length ? missingFromPrint() : [];
      zeroBox.innerHTML = "";
      zeroBox.classList.toggle("hidden", missing.length === 0);
      if (!missing.length) return;
      const checkbox = el("input", { type: "checkbox", class: "accent-emerald-600" });
      checkbox.checked = zeroMissing;
      checkbox.addEventListener("change", () => {
        zeroMissing = checkbox.checked;
        try {
          localStorage.setItem("printZeroMissing", zeroMissing ? "1" : "0");
        } catch (_) {}
        renderZeroBox();
      });
      zeroBox.appendChild(
        el("label", { class: "flex items-center gap-2 cursor-pointer text-zinc-200" }, [
          checkbox,
          el("span", {}, i18n.t("print.zeroMissing", { n: missing.length })),
        ])
      );
      zeroBox.appendChild(
        el(
          "p",
          { class: "text-xs mt-1 ml-6 " + (zeroMissing ? "text-amber-400" : "text-zinc-500") },
          (zeroMissing ? i18n.t("print.zeroMissingWill") : i18n.t("print.zeroMissingKeep")) +
            " " +
            missing.map((s) => s.resource_name).join(", ")
        )
      );
    }

    // The catalog key for what the user finally confirmed: the detected key
    // only if they kept the detected name — if they corrected it (e.g. picked
    // the right Assembly Materials tier), the key must follow the new name,
    // or the entry would be logged under the detector's wrong guess.
    function confirmedDefKey(c) {
      const name = c.resourceName.trim();
      if (c.resourceDefKey && name === c.detectedName) return c.resourceDefKey;
      const lower = name.toLowerCase();
      const match = resources.find((r) => r.name.toLowerCase() === lower);
      if (match && match.resource_def_key) return match.resource_def_key;
      const def = catalog.find((d) => [d.name_en, d.name_pt].some((n) => n && n.toLowerCase() === lower));
      return def ? def.key : match ? match.resource_def_key : null;
    }

    saveBtn.addEventListener("click", async () => {
      const kept = crops.filter((c) => c.resourceName.trim() && c.quantityRaw.trim());
      const entries = kept.map((c) => ({
        resource_name: c.resourceName.trim(),
        quantity_raw: c.quantityRaw.trim(),
        source: "ocr",
        source_image_id: image.id,
        resource_def_key: confirmedDefKey(c),
      }));
      if (entries.length === 0) {
        ui.toast(i18n.t("print.fillOneCrop"), true);
        return;
      }
      try {
        const zeroing = zeroMissing && missingFromPrint().length > 0;
        await api.addBuildingStock(building.id, entries, { zeroMissing: zeroing });
        // Teach the detector: each confirmed auto-detected slot becomes a
        // real exemplar of that item (how it tells Assembly Materials tiers
        // apart). Best effort — a failure here never blocks the save.
        const exemplars = kept
          .filter((c) => c.iconBox && confirmedDefKey(c))
          .map((c) => ({
            resource_def_key: confirmedDefKey(c),
            box_x: c.iconBox.x,
            box_y: c.iconBox.y,
            box_width: c.iconBox.width,
            box_height: c.iconBox.height,
          }));
        if (exemplars.length) api.saveIconExemplars(image.id, exemplars).catch(() => {});
        ui.toast(i18n.t("print.saved", { n: entries.length }));
        detectRun++;
        hideProgress();
        crops = [];
        redrawCanvas();
        renderCropsList();
        onSaved();
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
  }

  return { renderCaptureUI };
})();
