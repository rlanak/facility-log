window.views = window.views || {};

// Configurações: which engine reads quantities from screenshots (see
// app/services/capture). Server-wide setting.
views.settings = (() => {
  const el = (tag, attrs, children) => ui.el(tag, attrs, children);
  const inputClass =
    "w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";
  const PROVIDERS = ["rapidocr", "local_vlm", "api_vlm", "tesseract"];

  function field(label, input, hint) {
    return el("label", { class: "block mb-3" }, [
      el("span", { class: "block text-xs text-zinc-400 mb-1" }, label),
      input,
      hint ? el("span", { class: "block text-xs text-zinc-500 mt-1" }, hint) : null,
    ]);
  }

  async function render(app) {
    app.innerHTML = "";
    app.appendChild(el("h1", { class: "text-xl font-bold mb-2" }, i18n.t("settings.title")));
    app.appendChild(el("p", { class: "text-sm text-zinc-400 mb-4" }, i18n.t("settings.captureIntro")));
    const wrap = el("div");
    app.appendChild(wrap);
    draw(wrap, await api.getCaptureSettings());
  }

  function draw(wrap, s) {
    wrap.innerHTML = "";
    let provider = s.capture_provider;

    const list = el("div", { class: "grid gap-2 mb-5" });
    for (const key of PROVIDERS) {
      const status = s.providers[key];
      const radio = el("input", { type: "radio", name: "capture-provider", value: key, class: "mt-1" });
      radio.checked = key === provider;
      radio.addEventListener("change", () => {
        provider = key;
        toggleSections();
      });
      const badge = status.available
        ? el("span", { class: "text-xs text-emerald-400" }, `✓ ${i18n.t("settings.available")}`)
        : el(
            "span",
            { class: "text-xs text-amber-400" },
            `⚠ ${i18n.t(status.detail ? `settings.detail.${status.detail}` : "settings.unavailable")}`
          );
      list.appendChild(
        el("label", { class: "flex gap-3 items-start bg-zinc-900 border border-zinc-800 rounded-lg p-3 cursor-pointer" }, [
          radio,
          el("div", { class: "min-w-0" }, [
            el("div", { class: "font-semibold text-sm flex flex-wrap gap-2 items-center" }, [
              i18n.t(`settings.provider.${key}`),
              badge,
            ]),
            el("div", { class: "text-xs text-zinc-400 mt-0.5" }, i18n.t(`settings.provider.${key}.hint`)),
          ]),
        ])
      );
    }
    wrap.appendChild(list);

    // Ollama (local GPU)
    const ollamaUrl = el("input", { class: inputClass, value: s.ollama_url });
    const ollamaModel = el(
      "select",
      { class: inputClass },
      [el("option", { value: "" }, `— ${i18n.t("settings.pickModel")} —`)].concat(
        s.ollama_vision_models.map((m) => el("option", { value: m }, m))
      )
    );
    ollamaModel.value = s.ollama_model;
    const ollamaSection = el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-4" }, [
      el("h2", { class: "font-semibold text-sm mb-3" }, i18n.t("settings.provider.local_vlm")),
      field(i18n.t("settings.ollamaUrl"), ollamaUrl),
      field(
        i18n.t("settings.ollamaModel"),
        ollamaModel,
        s.ollama_vision_models.length ? i18n.t("settings.ollamaModelHint") : i18n.t("settings.ollamaNoModels")
      ),
    ]);

    // Cloud API
    const apiKind = el("select", { class: inputClass }, [
      el("option", { value: "anthropic" }, "Anthropic (Claude)"),
      el("option", { value: "openai" }, i18n.t("settings.apiOpenAICompatible")),
    ]);
    apiKind.value = s.api_kind;
    const apiBaseUrl = el("input", { class: inputClass, value: s.api_base_url, placeholder: i18n.t("settings.apiBaseUrlPlaceholder") });
    const apiModel = el("input", { class: inputClass, value: s.api_model });
    const apiKey = el("input", {
      class: inputClass,
      type: "password",
      autocomplete: "off",
      placeholder: s.api_key_set ? i18n.t("settings.apiKeyKeep", { hint: s.api_key_hint }) : i18n.t("settings.apiKeyPlaceholder"),
    });
    const clearKey = el("input", { type: "checkbox" });
    const apiSection = el("div", { class: "bg-zinc-900 border border-zinc-800 rounded-lg p-4 mb-4" }, [
      el("h2", { class: "font-semibold text-sm mb-1" }, i18n.t("settings.provider.api_vlm")),
      el("p", { class: "text-xs text-amber-400 mb-3" }, i18n.t("settings.apiCostWarning")),
      field(i18n.t("settings.apiKind"), apiKind),
      field(i18n.t("settings.apiBaseUrl"), apiBaseUrl),
      field(i18n.t("settings.apiModel"), apiModel),
      field(i18n.t("settings.apiKey"), apiKey, i18n.t("settings.apiKeyHint")),
      s.api_key_set
        ? el("label", { class: "flex gap-2 items-center text-xs text-zinc-400" }, [clearKey, i18n.t("settings.apiKeyClear")])
        : null,
    ]);

    wrap.appendChild(ollamaSection);
    wrap.appendChild(apiSection);

    function toggleSections() {
      ollamaSection.classList.toggle("hidden", provider !== "local_vlm");
      apiSection.classList.toggle("hidden", provider !== "api_vlm");
    }
    toggleSections();

    const saveBtn = el(
      "button",
      { class: "bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold" },
      i18n.t("settings.save")
    );
    saveBtn.addEventListener("click", async () => {
      try {
        const updated = await api.updateCaptureSettings({
          capture_provider: provider,
          ollama_url: ollamaUrl.value.trim(),
          ollama_model: ollamaModel.value,
          api_kind: apiKind.value,
          api_base_url: apiBaseUrl.value.trim(),
          api_model: apiModel.value.trim(),
          api_key: apiKey.value,
          clear_api_key: clearKey.checked,
        });
        ui.toast(i18n.t("settings.saved"));
        draw(wrap, updated);
      } catch (err) {
        ui.toast(err.message, true);
      }
    });
    wrap.appendChild(saveBtn);
  }

  return { render };
})();
