// "IA do meu computador": on the web version, the *browser* reads the numbers
// of a screenshot with the Ollama running on the user's own PC — the server
// never talks to it (it can't reach anyone's PC, and rarely has a GPU). The
// server still finds the items; only the number crops go from this page
// straight to http://localhost:11434. Per browser (localStorage), off by default.
//
// Mirrors app/services/capture/readers.py (read_ollama + sanitize): same
// prompt, same JSON schema, same cleanup — keep the two in step.
window.personalAI = (() => {
  const KEY = "personalAI";
  const DEFAULTS = { enabled: false, url: "http://localhost:11434", model: "" };

  // No example numbers in the prompt: given "like 5.1k", models answered
  // "5.1k" for empty slots.
  const PROMPT =
    "Transcribe the number written in white in this crop from the game Foxhole, exactly as shown: digits, " +
    "an optional decimal point and an optional k suffix. Part of an item icon may be visible; ignore it. " +
    "If there are no digits in the image, answer NONE.";
  const SCHEMA = { type: "object", properties: { quantity: { type: "string" } }, required: ["quantity"] };
  const CONFUSABLES = { O: "0", o: "0", I: "1", l: "1", "|": "1", T: "1", S: "5", B: "8" };

  function get() {
    try {
      return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(KEY) || "{}") };
    } catch (_) {
      return { ...DEFAULTS };
    }
  }

  function set(cfg) {
    try {
      localStorage.setItem(KEY, JSON.stringify({ ...get(), ...cfg }));
    } catch (_) {}
  }

  // The config to read with, or null when off / not set up.
  function active() {
    const cfg = get();
    return cfg.enabled && cfg.model ? cfg : null;
  }

  function base(url) {
    return (url || DEFAULTS.url).replace(/\/+$/, "");
  }

  async function call(url, path, body, timeoutMs) {
    const res = await fetch(base(url) + path, {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) throw new Error(`Ollama HTTP ${res.status}`);
    return res.json();
  }

  // Installed models that read images. Throws when Ollama can't be reached
  // (not running, or this site not allowed in OLLAMA_ORIGINS).
  async function visionModels(url) {
    const tags = await call(url, "/api/tags", null, 4000);
    const names = (tags.models || []).map((m) => m.name);
    const out = [];
    for (const name of names) {
      try {
        const info = await call(url, "/api/show", { model: name }, 5000);
        if ((info.capabilities || []).includes("vision")) out.push(name);
      } catch (_) {}
    }
    return out;
  }

  function sanitize(raw) {
    raw = raw || "";
    if (raw.toUpperCase().includes("NONE")) return "";
    const mapped = [...raw].map((c) => CONFUSABLES[c] || c).join("");
    const kept = (mapped.match(/[0-9.,kKmM]/g) || []).join("");
    const m = kept.match(/\d[\d.,]*[kKmM]?/);
    return m ? m[0] : "";
  }

  // 4x crop, smoothed — same as the server's _crop_png.
  function cropBase64(img, box, scale = 4) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, box.width * scale);
    canvas.height = Math.max(1, box.height * scale);
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, box.x, box.y, box.width, box.height, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/png").split(",")[1];
  }

  // The quantity text ("12.5k") or "" — throws if Ollama didn't answer.
  async function read(img, box, cfg = active()) {
    const data = await call(
      cfg.url,
      "/api/chat",
      {
        model: cfg.model,
        stream: false,
        think: false,
        format: SCHEMA,
        // A quantity is a few tokens; without a cap glm-ocr loops on crops
        // with no number until Ollama aborts.
        options: { temperature: 0, num_predict: 32 },
        messages: [{ role: "user", content: PROMPT, images: [cropBase64(img, box)] }],
      },
      120000
    );
    let quantity = "";
    try {
      quantity = JSON.parse(data.message.content).quantity || "";
    } catch (_) {
      quantity = (data.message && data.message.content) || "";
    }
    return sanitize(quantity);
  }

  return { get, set, active, visionModels, read, sanitize, defaults: DEFAULTS };
})();
