const ui = (() => {
  function toast(message, isError = false) {
    const container = document.getElementById("toast");
    const el = document.createElement("div");
    el.className = `px-4 py-2 rounded shadow-lg text-sm ${
      isError ? "bg-red-900 text-red-100 border border-red-700" : "bg-emerald-900 text-emerald-100 border border-emerald-700"
    }`;
    el.textContent = message;
    // Click = read it, gone.
    el.classList.add("cursor-pointer", "max-w-md");
    el.addEventListener("click", () => el.remove());
    container.appendChild(el);
    // An error is read, not glanced at: it stays for as long as its text
    // takes (the two-sentence ones used to vanish in 3s, mid-reading).
    const ms = isError ? Math.min(15000, Math.max(5000, String(message).length * 75)) : 3000;
    setTimeout(() => el.remove(), ms);
  }

  // "25.7k", "1,8k", "32000", "32.000" → number; NaN when it isn't one. The
  // same rules as the server's number_parser.parse_quantity (keep the two in
  // step): k/M multiply, a comma is a decimal separator, and without k/M a
  // single dot before exactly 3 digits is a thousands separator ("2.000" is
  // two thousand — that's also how this page prints numbers in pt-BR).
  function parseQuantity(text) {
    const m = /^\s*([\d.,]+)\s*([kKmM]?)\s*$/.exec(String(text ?? ""));
    if (!m) return NaN;
    let num = m[1];
    const dots = () => num.split(".").length - 1;
    if (m[2]) {
      num = num.replaceAll(",", ".");
      if (dots() > 1) return NaN;
      return Number(num) * (m[2].toLowerCase() === "k" ? 1e3 : 1e6);
    }
    if (num.includes(",") && num.includes(".")) return NaN;
    if (num.includes(",")) return Number(num.replaceAll(",", "."));
    if (dots() === 1) {
      const [whole, decimals] = num.split(".");
      return decimals.length === 3 ? Number(whole + decimals) : Number(num);
    }
    return dots() > 1 ? NaN : Number(num);
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
    // Closes on a click that both starts and ends on the dark area. A drag
    // that starts inside the form (selecting text, marking the panel on a
    // print) and is released outside also "clicks" the overlay — that used
    // to close the modal and throw away everything typed in it.
    let pressedOnOverlay = false;
    overlay.addEventListener("mousedown", (e) => {
      pressedOnOverlay = e.target === overlay;
    });
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay && pressedOnOverlay) close();
    });
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    buildContent(body, close);
    return { close, body };
  }

  // Line icons (24×24, stroke = currentColor) — one consistent set instead of
  // emoji, which every OS draws differently. icon(name, cls) → SVG string.
  const ICONS = {
    plus: '<path d="M12 5v14M5 12h14"/>',
    camera: '<path d="M3 8a2 2 0 0 1 2-2h2l2-2h6l2 2h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13" r="3.5"/>',
    pin: '<path d="M9 3h6l-1 6 4 4H6l4-4z"/><path d="M12 13v8"/>',
    mapPin: '<path d="M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    factory: '<path d="M3 21V10l5 3v-3l5 3V4h5l1.5 17z"/><path d="M2 21h20"/>',
    sliders: '<path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1"/><circle cx="15" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="17" cy="18" r="2"/>',
    pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M14 6l4 4"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4"/>',
    upload: '<path d="M12 15V4M7 9l5-5 5 5M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    boxes: '<path d="M3 8l9-5 9 5v8l-9 5-9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>',
    target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
    chart: '<path d="M4 20V11M10 20V5M16 20v-6M2 20h20"/>',
    file: '<path d="M6 2h9l5 5v15H6z"/><path d="M14 2v6h6M9 13h6M9 17h6"/>',
    clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    arrowUp: '<path d="M12 19V5M5 12l7-7 7 7"/>',
    lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20a7 7 0 0 1 14 0M16 4.5a3.5 3.5 0 0 1 0 7M22 20a6 6 0 0 0-4-5.6"/>',
    shield: '<path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z"/>',
    logout: '<path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3"/>',
    alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
    check: '<path d="M5 12l5 5 9-10"/>',
    grip: '<circle cx="9" cy="6" r="1.2" fill="currentColor"/><circle cx="15" cy="6" r="1.2" fill="currentColor"/><circle cx="9" cy="12" r="1.2" fill="currentColor"/><circle cx="15" cy="12" r="1.2" fill="currentColor"/><circle cx="9" cy="18" r="1.2" fill="currentColor"/><circle cx="15" cy="18" r="1.2" fill="currentColor"/>',
  };
  function icon(name, cls = "w-4 h-4") {
    return `<svg class="${cls} shrink-0 inline-block" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
  }
  // The mark: a map hex (Foxhole's world is hexes) with a factory in it.
  function logo(cls = "w-7 h-7") {
    return `<svg class="${cls} shrink-0" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 1.5l9.1 5.25v10.5L12 22.5l-9.1-5.25V6.75z" fill="rgb(var(--c-emerald-600))" stroke="rgb(var(--c-emerald-400))" stroke-width="1"/><path d="M6.5 16.5v-5l3.2 2v-2l3.2 2V7.5h2.6l.9 9z" fill="rgb(var(--c-zinc-950))"/></svg>`;
  }

  return { toast, copyText, escapeHtml, el, openModal, icon, logo, parseQuantity };
})();
