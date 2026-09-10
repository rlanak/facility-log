window.views = window.views || {};

views.print = (() => {
  function el(tag, attrs, children) {
    return ui.el(tag, attrs, children);
  }

  async function renderCaptureUI(container, building, onSaved) {
    let ocrAvailable = false;
    try {
      const status = await api.ocrStatus();
      ocrAvailable = status.available;
    } catch (_) {}

    const resources = await api.listResources();

    let image = null; // {id, url, naturalWidth, naturalHeight}
    let crops = []; // {localId, x,y,w,h, thumbDataUrl, resourceName, quantityRaw, ocrGuess}
    let nextLocalId = 1;
    let scaleX = 1;
    let scaleY = 1;

    container.innerHTML = "";
    container.appendChild(
      el("p", { class: "text-xs mb-2 " + (ocrAvailable ? "text-emerald-400" : "text-amber-400") },
        ocrAvailable
          ? "✓ OCR automático disponível — o valor lido vem pré-preenchido, mas sempre confirme antes de salvar."
          : "⚠ OCR automático indisponível (Tesseract não encontrado no sistema). Você ainda pode recortar a imagem e digitar os valores manualmente."
      )
    );

    const dropzone = el("div", {
      tabindex: "0",
      class: "border-2 border-dashed border-zinc-700 rounded-lg p-6 text-center text-sm text-zinc-400 focus:outline-none focus:border-emerald-500 cursor-pointer",
    }, "Clique pra escolher um arquivo, arraste uma imagem aqui, ou cole (Ctrl+V) um print copiado.");

    const fileInput = el("input", { type: "file", accept: "image/png,image/jpeg,image/webp", class: "hidden" });

    const stageWrap = el("div", { class: "mt-4 hidden" });
    const stage = el("div", { class: "relative inline-block max-w-full" });
    const imgEl = el("img", { class: "max-w-full block rounded" });
    const canvas = el("canvas", { class: "absolute top-0 left-0 cursor-crosshair" });
    stage.appendChild(imgEl);
    stage.appendChild(canvas);
    stageWrap.appendChild(stage);
    stageWrap.appendChild(
      el("p", { class: "text-xs text-zinc-500 mt-2" }, "Arraste retângulos sobre cada ícone + número que quiser lançar.")
    );

    const cropsListEl = el("div", { class: "grid gap-2 mt-4" });
    const saveBtn = el("button", {
      class: "hidden bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold mt-4",
    }, "Salvar Lançamentos");

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
        ui.toast("Print enviado!");
      } catch (err) {
        ui.toast(err.message || "Falha ao carregar a imagem.", true);
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
        addCrop(rectX, rectY, rectW, rectH);
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

    function renderCropsList() {
      cropsListEl.innerHTML = "";
      crops.forEach((crop, i) => {
        const row = el("div", { class: "flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded p-2" });
        const thumb = el("img", { src: crop.thumbDataUrl, class: "h-10 w-auto rounded border border-zinc-700" });
        const label = el("span", { class: "text-xs text-zinc-500 w-4" }, String(i + 1));

        const nameInput = el("input", {
          list: "print-resources-datalist",
          placeholder: "Recurso",
          class: "flex-1 bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500",
        });
        nameInput.value = crop.resourceName;
        nameInput.addEventListener("input", () => (crop.resourceName = nameInput.value));

        const qtyInput = el("input", {
          placeholder: "Qtd",
          class: "w-28 bg-zinc-950 border border-zinc-700 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-emerald-500",
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
        cropsListEl.appendChild(row);
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
        }));
      if (entries.length === 0) {
        ui.toast("Preencha recurso e quantidade em pelo menos um recorte.", true);
        return;
      }
      try {
        await api.addBuildingStock(building.id, entries);
        ui.toast(`${entries.length} lançamento(s) salvos a partir do print!`);
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
