window.views = window.views || {};

views.print = (() => {
  function el(tag, attrs, children) {
    return ui.el(tag, attrs, children);
  }

  async function renderCaptureUI(container, building, onSaved) {
    let ocrAvailable = false;
    let detectAvailable = false;
    let engineMessage = i18n.t("print.engineNone");
    try {
      const status = await api.ocrStatus();
      ocrAvailable = status.available;
      detectAvailable = status.stockpile_detect_available;
      // Which engine reads the numbers is picked in Configurações; say which
      // one is actually in use (it falls back when the chosen one is down).
      const name = (key) => i18n.t(`settings.provider.${key}`);
      if (!status.effective_provider) engineMessage = i18n.t("print.engineNone");
      else if (status.effective_provider !== status.provider)
        engineMessage = i18n.t("print.engineFallback", { chosen: name(status.provider), engine: name(status.effective_provider) });
      else engineMessage = i18n.t("print.engine", { engine: name(status.effective_provider) });
    } catch (_) {}

    const resources = await api.listResources();

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

    const dropzone = el("div", {
      tabindex: "0",
      class: "border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center text-sm text-zinc-400 focus:outline-none focus:border-emerald-500 cursor-pointer",
    }, i18n.t("print.dropzone"));

    const fileInput = el("input", { type: "file", accept: "image/png,image/jpeg,image/webp", class: "hidden" });

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
    container.appendChild(cropsListEl);
    container.appendChild(saveBtn);

    dropzone.addEventListener("click", () => fileInput.click());
    dropzone.addEventListener("dragover", (e) => e.preventDefault());
    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    });
    dropzone.addEventListener("paste", (e) => {
      const item = [...e.clipboardData.items].find((i) => i.type.startsWith("image/"));
      if (item) handleFile(item.getAsFile());
    });
    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) handleFile(fileInput.files[0]);
    });

    async function handleFile(file) {
      try {
        const uploaded = await api.uploadBuildingImage(building.id, file);
        image = uploaded;
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
        ctx.strokeStyle = "#34d399";
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
      ctx.strokeStyle = "#10b981";
      ctx.lineWidth = 2;
      ctx.font = "12px monospace";
      ctx.fillStyle = "#10b981";
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
          const result = await api.readImageCrop(image.id, box);
          if (result.guess) {
            crop.quantityRaw = result.guess;
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
      redrawCanvas();
      ui.toast(i18n.t("print.detecting"));
      try {
        const result = await api.detectStockpile(image.id, box);
        if (!result.available) {
          ui.toast(i18n.t("print.detectUnavailable"), true);
          return;
        }
        if (result.items.length === 0) {
          ui.toast(i18n.t("print.detectNone"), true);
          return;
        }
        result.items.forEach(addDetectedCrop);
        redrawCanvas();
        renderCropsList();
        ui.toast(i18n.t("print.detected", { n: result.items.length }));
      } catch (err) {
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

      const existing = resources.find((r) => r.resource_def_key === item.resource_def_key);
      const catalogName = i18n.getCatalogLang() === "en-US" ? item.name_en : item.name_pt || item.name_en;

      crops.push({
        localId: nextLocalId++,
        displayX: box.x / scaleX,
        displayY: box.y / scaleY,
        displayW: box.width / scaleX,
        displayH: box.height / scaleY,
        box,
        thumbDataUrl: thumbCanvas.toDataURL("image/png"),
        resourceName: existing ? existing.name : catalogName,
        resourceDefKey: item.resource_def_key,
        // quantity_guess strips non-digit characters, which also strips a
        // k/K/m/M magnitude suffix ("53k" -> "53") -- using it as the
        // pre-fill would silently save a value 1000x too small. Prefer the
        // full raw OCR text (keeps the suffix) whenever it found a real
        // digit at all; quantity_guess is only truthy in that same case
        // (see ocr_service.read_crop), so this never shows raw garbage.
        quantityRaw: item.quantity_guess ? item.quantity_raw : "",
        ambiguous: item.ambiguous,
        rivalNameEn: item.rival_name_en,
      });
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
        nameInput.addEventListener("input", () => (crop.resourceName = nameInput.value));

        const qtyInput = el("input", {
          placeholder: i18n.t("print.qtyPlaceholder"),
          class: "w-28 shrink-0 bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500",
        });
        qtyInput.value = crop.quantityRaw;
        qtyInput.addEventListener("input", () => (crop.quantityRaw = qtyInput.value));

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
        if (crop.ambiguous) {
          wrap.appendChild(
            el("p", { class: "text-[11px] text-amber-400 mt-1 ml-6" }, i18n.t("print.ambiguousNote", { rival: crop.rivalNameEn }))
          );
        }
        cropsListEl.appendChild(wrap);
      });

      if (!document.getElementById("print-resources-datalist")) {
        const datalist = el(
          "datalist",
          { id: "print-resources-datalist" },
          resources.map((r) => el("option", { value: r.name }))
        );
        container.appendChild(datalist);
      }

      saveBtn.classList.toggle("hidden", crops.length === 0);
    }

    saveBtn.addEventListener("click", async () => {
      const entries = crops
        .filter((c) => c.resourceName.trim() && c.quantityRaw.trim())
        .map((c) => ({
          resource_name: c.resourceName.trim(),
          quantity_raw: c.quantityRaw.trim(),
          source: "ocr",
          source_image_id: image.id,
          resource_def_key: c.resourceDefKey || null,
        }));
      if (entries.length === 0) {
        ui.toast(i18n.t("print.fillOneCrop"), true);
        return;
      }
      try {
        await api.addBuildingStock(building.id, entries);
        ui.toast(i18n.t("print.saved", { n: entries.length }));
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
