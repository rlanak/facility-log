window.views = window.views || {};

// Per-item settings (nickname + origin), opened by clicking an item's name in
// a building card or in the Metas tab. Replaced the old "Catálogo de
// Recursos" page: items are created on their own when stock is logged, and
// the catalog already knows the right origin for almost all of them.
views.itemPanel = (() => {
  // The three stored flags as one choice — unlimited wins over imported,
  // which wins over farmable (same priority the report uses).
  const ORIGINS = {
    produced: { farmable: false, imported: false, unlimited: false },
    farmed: { farmable: true, imported: false, unlimited: false },
    imported: { farmable: false, imported: true, unlimited: false },
    unlimited: { farmable: false, imported: false, unlimited: true },
  };
  const ORIGIN_ICONS = { produced: "🏭", farmed: "🌾", imported: "📦", unlimited: "∞" };

  function originOf(resource) {
    if (resource.unlimited) return "unlimited";
    if (resource.imported) return "imported";
    return resource.farmable ? "farmed" : "produced";
  }

  function originBadge(resource) {
    const origin = originOf(resource);
    return `<span class="text-xs text-zinc-500 whitespace-nowrap" title="${ui.escapeHtml(i18n.t(`item.originHint.${origin}`))}">${ORIGIN_ICONS[origin]} ${i18n.t(`item.origin.${origin}`)}</span>`;
  }

  // resource: a row from /api/resources; def: its catalog entry (or null).
  function open(resource, def, onChange) {
    const catalogLabel = def ? i18n.catalogName(def) : resource.name;
    ui.openModal(
      i18n.resourceName(resource, def ? { [def.key]: def } : {}),
      (body, close) => {
        const input =
          "w-full bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500";
        const current = originOf(resource);
        body.innerHTML = `
          <form class="grid gap-4">
            <div class="flex items-center gap-3">
              ${def && def.icon ? `<img src="${ui.escapeHtml(def.icon)}" class="h-10 w-10 object-contain" />` : ""}
              <span class="text-sm text-zinc-400">${ui.escapeHtml(catalogLabel)}</span>
            </div>
            <label class="grid gap-1 text-xs text-zinc-400">${i18n.t("item.nickname")}
              <input name="nickname" class="${input}" value="${ui.escapeHtml(resource.nickname || "")}" placeholder="${ui.escapeHtml(catalogLabel)}" />
              <span class="text-zinc-600">${i18n.t("item.nicknameHint")}</span>
            </label>
            <fieldset class="grid gap-1.5">
              <legend class="text-xs text-zinc-400 mb-1">${i18n.t("item.originLabel")}</legend>
              ${Object.keys(ORIGINS)
                .map(
                  (origin) => `
                <label class="flex items-start gap-2 text-sm rounded border border-zinc-800 hover:border-zinc-600 px-3 py-2 cursor-pointer has-[:checked]:border-emerald-600 has-[:checked]:bg-emerald-950/30">
                  <input type="radio" name="origin" value="${origin}" class="mt-1 accent-emerald-600" ${origin === current ? "checked" : ""} />
                  <span>
                    <span class="font-medium">${ORIGIN_ICONS[origin]} ${i18n.t(`item.origin.${origin}`)}</span>
                    <span class="block text-xs text-zinc-500">${i18n.t(`item.originHint.${origin}`)}</span>
                  </span>
                </label>`
                )
                .join("")}
              <span class="text-xs text-zinc-600">${i18n.t("item.originGlobal")}</span>
            </fieldset>
            <div><button class="bg-emerald-700 hover:bg-emerald-600 px-4 py-2 rounded text-sm font-semibold">${i18n.t("common.save")}</button></div>
          </form>`;
        const form = body.querySelector("form");
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const origin = form.querySelector('[name="origin"]:checked').value;
          try {
            await api.updateResource(resource.id, {
              nickname: form.querySelector('[name="nickname"]').value.trim() || null,
              ...ORIGINS[origin],
            });
            close();
            onChange();
          } catch (err) {
            ui.toast(err.message, true);
          }
        });
      },
      { maxWidth: "max-w-md" }
    );
  }

  return { open, originOf, originBadge };
})();
