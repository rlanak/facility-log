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
        app.innerHTML = `<p class="text-zinc-500">Página não encontrada.</p>`;
      }
    } catch (err) {
      console.error(err);
      app.innerHTML = `<p class="text-red-400">Erro: ${ui.escapeHtml(err.message)}</p>`;
    }
  }

  window.addEventListener("hashchange", router);
  window.addEventListener("DOMContentLoaded", router);
})();
