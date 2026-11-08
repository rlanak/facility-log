(function () {
  const app = document.getElementById("app");

  // Web mode (Discord login) — null until /api/me answers. In local mode
  // auth_enabled is false and nothing below changes how the app behaves.
  let me = null;

  // What the server keeps about people (web mode) — so whoever logs in
  // knows what they're trusting the server's admin with.
  function showPrivacy() {
    ui.openModal(i18n.t("privacy.title"), (body) => {
      const items = ["discord", "entries", "webhook", "apiKey", "private", "none"];
      body.innerHTML = `<ul class="space-y-3 text-sm text-zinc-300">${items
        .map((k) => `<li><span class="font-semibold">${i18n.t(`privacy.${k}Title`)}</span> — ${i18n.t(`privacy.${k}`)}</li>`)
        .join("")}</ul>`;
    });
  }

  function renderLogin() {
    const params = new URLSearchParams(location.search);
    const error = params.get("auth_error");
    app.innerHTML = `
      <div class="max-w-sm mx-auto mt-16 bg-zinc-900 border border-zinc-800 rounded-lg p-6 text-center">
        <h1 class="text-lg font-bold mb-2">${i18n.t("auth.title")}</h1>
        <p class="text-sm text-zinc-400 mb-4">${i18n.t("auth.intro")}</p>
        ${error ? `<p class="text-sm text-amber-400 mb-4">${ui.escapeHtml(i18n.t(`auth.error.${error}`))}</p>` : ""}
        <a href="/auth/login" class="inline-block bg-indigo-600 hover:bg-indigo-500 px-4 py-2 rounded text-sm font-semibold">${i18n.t("auth.login")}</a>
        <div class="mt-4"><button id="privacy-link" class="text-xs text-zinc-500 hover:text-zinc-300 underline">${i18n.t("privacy.title")}</button></div>
      </div>`;
    document.getElementById("privacy-link").addEventListener("click", showPrivacy);
  }

  function renderUserBox() {
    const box = document.getElementById("user-box");
    if (!me || !me.user) return;
    box.innerHTML = "";
    if (me.user.avatar_url) box.appendChild(ui.el("img", { src: me.user.avatar_url, class: "w-6 h-6 rounded-full" }));
    box.appendChild(ui.el("span", { class: "text-xs text-zinc-300" }, me.user.name));
    box.appendChild(
      ui.el("button", { class: "text-zinc-500 hover:text-zinc-200", title: i18n.t("privacy.title"), onclick: showPrivacy, html: ui.icon("shield") })
    );
    box.appendChild(
      ui.el(
        "button",
        {
          class: "text-xs text-zinc-500 hover:text-zinc-200",
          onclick: async () => {
            await fetch("/auth/logout", { method: "POST" });
            location.href = "/";
          },
        },
        i18n.t("auth.logout")
      )
    );
    box.classList.remove("hidden");
    box.classList.add("flex");
  }

  async function router() {
    if (me === null) {
      try {
        me = await api.me();
      } catch (_) {
        me = { auth_enabled: false, user: null };
      }
      window.appMe = me; // views read it for owner-only controls (private facility)
      renderUserBox();
    }
    if (me.auth_enabled && !me.user) {
      renderLogin();
      return;
    }
    const hash = location.hash || "#/";
    const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);

    try {
      if (parts.length === 0) {
        await views.facilities.render(app);
      } else if (parts[0] === "settings") {
        await views.settings.render(app);
      } else if (parts[0] === "facilities" && parts[1]) {
        const facilityId = parts[1];
        const tab = parts[2] || "buildings";
        await views.facilityDetail.render(app, facilityId, tab);
      } else {
        app.innerHTML = `<p class="text-zinc-500">${i18n.t("app.notFound")}</p>`;
      }
    } catch (err) {
      console.error(err);
      app.innerHTML = `<p class="text-red-400">${i18n.t("app.error", { message: ui.escapeHtml(err.message) })}</p>`;
    }
  }

  function setupLangSwitcher() {
    const select = document.getElementById("lang-switcher");
    select.value = i18n.getLang();
    select.addEventListener("change", () => {
      i18n.setLang(select.value);
      location.reload();
    });

    const catalogSelect = document.getElementById("catalog-lang-switcher");
    catalogSelect.value = i18n.getCatalogLang();
    catalogSelect.addEventListener("change", () => {
      i18n.setCatalogLang(catalogSelect.value);
      location.reload();
    });
  }

  document.documentElement.lang = i18n.getLang();
  i18n.applyStaticText();
  document.getElementById("brand").insertAdjacentHTML("afterbegin", ui.logo());
  document.querySelectorAll("[data-icon]").forEach((e) => e.insertAdjacentHTML("afterbegin", ui.icon(e.dataset.icon)));
  setupLangSwitcher();

  // api.js fires this on a 401 (session expired / role removed in Discord).
  window.addEventListener("auth-required", () => {
    me = { auth_enabled: true, user: null };
    renderLogin();
  });
  window.addEventListener("hashchange", router);
  window.addEventListener("DOMContentLoaded", router);
})();
