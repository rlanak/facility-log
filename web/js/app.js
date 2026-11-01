(function () {
  const app = document.getElementById("app");

  async function router() {
    const hash = location.hash || "#/";
    const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);

    try {
      if (parts.length === 0) {
        await views.facilities.render(app);
      } else if (parts[0] === "resources") {
        await views.resources.render(app);
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
  setupLangSwitcher();

  window.addEventListener("hashchange", router);
  window.addEventListener("DOMContentLoaded", router);
})();
