const ui = (() => {
  function toast(message, isError = false) {
    const container = document.getElementById("toast");
    const el = document.createElement("div");
    el.className = `px-4 py-2 rounded shadow-lg text-sm ${
      isError ? "bg-red-900 text-red-100 border border-red-700" : "bg-emerald-900 text-emerald-100 border border-emerald-700"
    }`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast(i18n.t("ui.copied"));
    } catch (err) {
      toast(i18n.t("ui.copyFailed"), true);
    }
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  }

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (key === "class") node.className = value;
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (key === "html") node.innerHTML = value;
      else node.setAttribute(key, value);
    }
    for (const child of [].concat(children)) {
      if (child == null) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  }

  // A form with real content (an item list, an image preview, a recipe
  // editor) needs its own width to lay out sanely — it can't be squeezed
  // into whatever a responsive card grid column happens to be that week.
  // Building cards stay short/uniform; this is where the actual editing
  // surface lives, sized for its own content instead of the grid's.
  function openModal(titleText, buildContent, { maxWidth = "max-w-lg" } = {}) {
    const overlay = el("div", {
      class: "fixed inset-0 bg-black/60 z-40 flex items-start justify-center p-4 overflow-y-auto",
    });
    const panel = el("div", { class: `bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl w-full ${maxWidth} my-8` });
    const header = el("div", { class: "flex items-center justify-between px-4 py-3 border-b border-zinc-800" });
    const body = el("div", { class: "p-4" });

    header.appendChild(el("h3", { class: "font-semibold text-sm" }, titleText));
    const closeBtn = el("button", { class: "text-zinc-500 hover:text-zinc-200 text-lg leading-none px-1" }, "✕");
    header.appendChild(closeBtn);
    panel.appendChild(header);
    panel.appendChild(body);
    overlay.appendChild(panel);

    function close() {
      overlay.remove();
      document.removeEventListener("keydown", onKey);
    }
    function onKey(e) {
      if (e.key === "Escape") close();
    }
    closeBtn.addEventListener("click", close);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    buildContent(body, close);
    return { close, body };
  }

  return { toast, copyText, escapeHtml, el, openModal };
})();
