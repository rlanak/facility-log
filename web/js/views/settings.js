window.views = window.views || {};

// Configurações: which engine reads quantities from screenshots (see
// app/services/capture) — server-wide — plus, on the web version, the
// per-browser "IA do meu computador" (web/js/personalAI.js).
views.settings = (() => {
  const el = (tag, attrs, children) => ui.el(tag, attrs, children);
  const inputClass =
    "w-full bg-zinc-950 border border-zinc-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-emerald-500";
  const PROVIDERS = ["rapidocr", "local_vlm", "api_vlm"];

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
    const s = await api.getCaptureSettings();
    // Web version: each person can read with the AI on their own PC.
    if (window.appMe && window.appMe.auth_enabled) app.appendChild(myAISection());
    const wrap = el("div");
    app.appendChild(wrap);
    draw(wrap, s);
  }

  // "IA do meu computador" — saved in this browser only, talks to the
  // user's own Ollama from the page (the server never sees it).
  function myAISection() {
    const cfg = personalAI.get();
    const enabled = el("input", { type: "checkbox", class: "mt-1" });
    enabled.checked = cfg.enabled;
    const url = el("input", { class: inputClass, value: cfg.url });
    const model = el("select", { class: inputClass });
    const status = el("p", { class: "text-xs mt-1" });
    const fillModels = (names, current) => {
      model.innerHTML = "";
      model.appendChild(el("option", { value: "" }, `— ${i18n.t("settings.pickModel")} —`));
      for (const n of names) model.appendChild(el("option", { value: n }, n));
      if (current && !names.includes(current)) model.appendChild(el("option", { value: current }, current));
      model.value = current || (names.includes("glm-ocr:latest") ? "glm-ocr:latest" : "");
    };
    fillModels([], cfg.model);

    async function probe() {
      status.className = "text-xs mt-1 text-zinc-400";
      status.textContent = i18n.t("settings.myAI.checking");
      try {
        const names = await personalAI.visionModels(url.value.trim());
        fillModels(names, model.value || cfg.model);
        status.className = "text-xs mt-1 " + (names.length ? "text-emerald-400" : "text-amber-400");
        status.textContent = names.length
          ? `✓ ${i18n.t("settings.myAI.connected", { n: names.length })}`
          : `⚠ ${i18n.t("settings.ollamaNoModels")}`;
      } catch (_) {
        status.className = "text-xs mt-1 text-amber-400";
        status.textContent = `⚠ ${i18n.t("settings.myAI.unreachable")}`;
      }
    }

    const testBtn = el("button", { type: "button", class: "px-3 py-1.5 rounded text-xs bg-zinc-800 hover:bg-zinc-700" }, i18n.t("settings.myAI.test"));
    testBtn.addEventListener("click", probe);
    const saveBtn = el(
      "button",
      { type: "button", class: "bg-emerald-700 hover:bg-emerald-600 px-3 py-1.5 rounded text-xs font-semibold" },
      i18n.t("settings.myAI.save")
    );
    saveBtn.addEventListener("click", () => {
      if (enabled.checked && !model.value) {
        ui.toast(i18n.t("settings.myAI.needModel"), true);
        return;
      }
      personalAI.set({ enabled: enabled.checked, url: url.value.trim() || personalAI.defaults.url, model: model.value });
      ui.toast(i18n.t("settings.myAI.saved"));
    });

    const origin = location.origin;
    const steps = el("details", { class: "mt-3 text-xs text-zinc-400" }, [
      el("summary", { class: "cursor-pointer text-zinc-300" }, i18n.t("settings.myAI.howTo")),
    ]);
    const list = el("ol", { class: "list-decimal ml-5 mt-2 space-y-1" });
    list.innerHTML = [
      i18n.t("settings.myAI.step1"),
      i18n.t("settings.myAI.step2"),
      i18n.t("settings.myAI.step3", { cmd: `<code class="bg-zinc-950 px-1 rounded select-all">setx OLLAMA_ORIGINS "${ui.escapeHtml(origin)}"</code>` }),
      i18n.t("settings.myAI.step4"),
      i18n.t("settings.myAI.step5"),
    ]
      .map((t) => `<li>${t}</li>`)
      .join("");
    steps.appendChild(list);

    // Shown as soon as the box is ticked: the one step people miss. The
    // address is this page's own origin — whatever server runs the app.
    const originCmd = `setx OLLAMA_ORIGINS "${origin}"`;
    const copyBtn = el("button", { type: "button", class: "px-2 py-1 rounded text-xs bg-zinc-800 hover:bg-zinc-700 shrink-0" }, i18n.t("settings.myAI.copy"));
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(originCmd);
        ui.toast(i18n.t("settings.myAI.copied"));
      } catch (_) {
        ui.toast(originCmd);
      }
    });
    const originBox = el("div", { class: "bg-zinc-950 border border-amber-900 rounded p-3 mb-3 text-xs text-zinc-300" }, [
      el("p", { class: "mb-2" }, i18n.t("settings.myAI.originIntro")),
      el("div", { class: "flex gap-2 items-center" }, [
        el("code", { class: "flex-1 min-w-0 break-all bg-zinc-900 px-2 py-1 rounded select-all" }, originCmd),
        copyBtn,
      ]),
      el("p", { class: "mt-2 text-zinc-500" }, i18n.t("settings.myAI.originAfter")),
    ]);
    const syncOrigin = () => originBox.classList.toggle("hidden", !enabled.checked);
    enabled.addEventListener("change", syncOrigin);
    syncOrigin();

    const box = el("div", { class: "bg-zinc-900 border border-sky-900 rounded-lg p-4 mb-6" }, [
      el("h2", { class: "font-semibold text-sm mb-1" }, i18n.t("settings.myAI.title")),
      el("p", { class: "text-xs text-zinc-400 mb-3" }, i18n.t("settings.myAI.intro")),
      el("label", { class: "flex gap-2 items-start text-sm mb-3 cursor-pointer" }, [enabled, i18n.t("settings.myAI.enable")]),
      originBox,
      field(i18n.t("settings.ollamaUrl"), url),
      field(i18n.t("settings.ollamaModel"), model),
      el("div", { class: "flex flex-wrap gap-2 items-center" }, [testBtn, saveBtn]),
      status,
      steps,
    ]);
    if (cfg.enabled) probe();
    return box;
  }

  function draw(wrap, s) {
    wrap.innerHTML = "";
    let provider = s.capture_provider;

    const list = el("div", { class: "grid gap-2 mb-5" });
    if (window.appMe && window.appMe.auth_enabled) {
      wrap.appendChild(el("h2", { class: "font-semibold text-sm mb-1" }, i18n.t("settings.serverTitle")));
      wrap.appendChild(el("p", { class: "text-xs text-zinc-400 mb-2" }, i18n.t("settings.serverIntro")));
    }
    // The server's own Ollama only shows where it can exist (local mode, or a
    // server set up for it — FACILITY_LOG_SERVER_OLLAMA).
    for (const key of PROVIDERS.filter((k) => k !== "local_vlm" || s.server_local_ai)) {
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
