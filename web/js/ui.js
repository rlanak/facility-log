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
      toast("Copiado!");
    } catch (err) {
      toast("Não consegui copiar automaticamente. Selecione e copie manualmente.", true);
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

  return { toast, copyText, escapeHtml, el };
})();
