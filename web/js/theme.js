// Appearance, per browser (localStorage["theme"]). Loaded in <head> before
// the Tailwind script (web/vendor/): every Tailwind color the app uses (zinc = neutral,
// emerald = accent, plus red/amber/sky/indigo) is pointed at a CSS variable
// (see tailwindConfig()), so a theme is just a set of variables on <html> —
// no view knows about themes, and changing one repaints the page live.
// A theme is small and shareable: {accent, neutral, mode, font, display, scale}; the
// "code" in Configurações is that JSON, so people can pass their look around.
const theme = (() => {
  const SHADES = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 950];
  const STORAGE_KEY = "theme";

  // Tailwind's own values: the default theme stays pixel-identical.
  const TW = {
    zinc: ["250 250 250", "244 244 245", "228 228 231", "212 212 216", "161 161 170", "113 113 122", "82 82 91", "63 63 70", "39 39 42", "24 24 27", "9 9 11"],
    emerald: ["236 253 245", "209 250 229", "167 243 208", "110 231 183", "52 211 153", "16 185 129", "5 150 105", "4 120 87", "6 95 70", "6 78 59", "2 44 34"],
    red: ["254 242 242", "254 226 226", "254 202 202", "252 165 165", "248 113 113", "239 68 68", "220 38 38", "185 28 28", "153 27 27", "127 29 29", "69 10 10"],
    amber: ["255 251 235", "254 243 199", "253 230 138", "252 211 77", "251 191 36", "245 158 11", "217 119 6", "180 83 9", "146 64 14", "120 53 15", "69 26 3"],
    sky: ["240 249 255", "224 242 254", "186 230 253", "125 211 252", "56 189 248", "14 165 233", "2 132 199", "3 105 161", "7 89 133", "12 74 110", "8 47 73"],
    indigo: ["238 242 255", "224 231 255", "199 210 254", "165 180 252", "129 140 248", "99 102 241", "79 70 229", "67 56 202", "55 48 163", "49 46 129", "30 27 75"],
  };
  const DEFAULT_ACCENT = "#10b981"; // emerald-500
  const DEFAULT_NEUTRAL = "#71717a"; // zinc-500

  // First one is the default look. "classic" = the original zinc/emerald.
  const PRESETS = {
    colonial: { accent: "#7d9440", neutral: "#6f6b55", mode: "dark" },
    classic: { accent: DEFAULT_ACCENT, neutral: DEFAULT_NEUTRAL, mode: "dark" },
    night: { accent: "#0ea5e9", neutral: "#64748b", mode: "dark" },
    rust: { accent: "#ea580c", neutral: "#78716c", mode: "dark" },
    light: { accent: "#059669", neutral: DEFAULT_NEUTRAL, mode: "light" },
  };
  const FONTS = {
    system: 'ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"',
    rounded: 'ui-rounded, "Segoe UI Variable Display", "SF Pro Rounded", system-ui, sans-serif, "Segoe UI Emoji"',
    serif: 'ui-serif, Georgia, Cambria, "Times New Roman", serif, "Segoe UI Emoji"',
    mono: 'ui-monospace, SFMono-Regular, Consolas, Menlo, monospace, "Segoe UI Emoji"',
  };
  // Headings/names: a condensed military-style face (served by the app from
  // web/vendor/, so it needs no internet) or the text font.
  const DISPLAYS = {
    military: '"Saira Condensed", var(--app-font)',
    body: "var(--app-font)",
  };
  const SCALES = [90, 100, 110, 125];
  const DEFAULTS = { ...PRESETS.colonial, font: "system", display: "military", scale: 100 };

  // ---- color math -------------------------------------------------------
  function hexToHsl(hex) {
    const n = parseInt(hex.slice(1), 16);
    const r = ((n >> 16) & 255) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    const l = (max + min) / 2;
    if (max === min) return [0, 0, l];
    const d = max - min;
    const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    const h = max === r ? (g - b) / d + (g < b ? 6 : 0) : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return [h * 60, s, l];
  }
  function hslToRgb(h, s, l) {
    const k = (n) => (n + h / 30) % 12;
    const a = s * Math.min(l, 1 - l);
    const f = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
    return `${f(0)} ${f(8)} ${f(4)}`;
  }
  // Lightness per shade (50 … 950).
  const NEUTRAL_L = [0.98, 0.96, 0.9, 0.84, 0.65, 0.46, 0.34, 0.26, 0.16, 0.1, 0.04];
  const ACCENT_L = [0.96, 0.92, 0.85, 0.75, 0.62, 0.5, 0.42, 0.35, 0.28, 0.22, 0.13];
  // Light mode, neutral by role, not mirrored: 950 = page, 900 = card (the
  // lightest), 800/700 = borders, 600-400 = muted text, 300-50 = text.
  const NEUTRAL_L_LIGHT = [0.04, 0.1, 0.16, 0.24, 0.34, 0.45, 0.58, 0.8, 0.88, 1, 0.95];

  function neutralScale(hex, mode) {
    if (mode === "dark" && hex === DEFAULT_NEUTRAL) return TW.zinc;
    const [h, s] = hexToHsl(hex);
    const sat = Math.min(s, 0.25);
    return (mode === "light" ? NEUTRAL_L_LIGHT : NEUTRAL_L).map((l) => hslToRgb(h, sat, l));
  }
  function accentScale(hex) {
    if (hex === DEFAULT_ACCENT) return TW.emerald;
    const [h, s] = hexToHsl(hex);
    return ACCENT_L.map((l) => hslToRgb(h, Math.max(s, 0.3), l));
  }
  // Light mode for colored scales: the views use 300/400 as text (needs to
  // get dark), 500-700 as solid buttons (stay), 800-950 as tints/badges
  // (need to get light). So: text shades borrow the dark end, tints the light.
  const LIGHT_PICK = [10, 9, 8, 7, 6, 6, 6, 7, 2, 1, 0];
  const toLight = (scale) => LIGHT_PICK.map((i) => scale[i]);

  // ---- state ------------------------------------------------------------
  const HEX = /^#[0-9a-f]{6}$/i;
  function sanitize(t) {
    t = t && typeof t === "object" ? t : {};
    return {
      accent: HEX.test(t.accent) ? t.accent.toLowerCase() : DEFAULTS.accent,
      neutral: HEX.test(t.neutral) ? t.neutral.toLowerCase() : DEFAULTS.neutral,
      mode: t.mode === "light" ? "light" : "dark",
      font: FONTS[t.font] ? t.font : DEFAULTS.font,
      display: DISPLAYS[t.display] ? t.display : DEFAULTS.display,
      scale: SCALES.includes(Number(t.scale)) ? Number(t.scale) : DEFAULTS.scale,
    };
  }
  function get() {
    try {
      return sanitize(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
    } catch (_) {
      return { ...DEFAULTS };
    }
  }

  function apply(t) {
    t = sanitize(t);
    const root = document.documentElement;
    const scales = {
      zinc: neutralScale(t.neutral, t.mode),
      emerald: accentScale(t.accent),
      red: TW.red,
      amber: TW.amber,
      sky: TW.sky,
      indigo: TW.indigo,
    };
    for (const [name, scale] of Object.entries(scales)) {
      const values = t.mode === "light" && name !== "zinc" ? toLight(scale) : scale;
      values.forEach((v, i) => root.style.setProperty(`--c-${name}-${SHADES[i]}`, v));
    }
    root.style.setProperty("--app-font", FONTS[t.font]);
    root.style.setProperty("--display-font", DISPLAYS[t.display]);
    root.style.fontSize = t.scale === 100 ? "" : `${t.scale}%`;
    root.style.colorScheme = t.mode;
    root.dataset.theme = t.mode;
    return t;
  }

  function set(t) {
    const clean = apply(t);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
    } catch (_) {}
    return clean;
  }

  function reset() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (_) {}
    return apply(DEFAULTS);
  }

  // Shareable code: the theme as compact JSON. Import accepts that JSON
  // (sanitized — only known keys and valid values survive).
  const exportCode = (t) => JSON.stringify(sanitize(t || get()));
  function importCode(text) {
    const parsed = JSON.parse(String(text).trim());
    if (!parsed || typeof parsed !== "object") throw new Error("invalid");
    return set({ ...get(), ...parsed });
  }

  // "rgb(r g b)" of a theme color, for canvas drawing and inline styles.
  function rgb(name, shade) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(`--c-${name}-${shade}`).trim();
    return v ? `rgb(${v})` : "#10b981";
  }

  function tailwindConfig() {
    const colors = {};
    for (const name of Object.keys(TW)) {
      colors[name] = {};
      for (const shade of SHADES) colors[name][shade] = `rgb(var(--c-${name}-${shade}) / <alpha-value>)`;
    }
    return { theme: { extend: { colors } } };
  }

  apply(get());

  return { get, set, apply, reset, exportCode, importCode, rgb, tailwindConfig, PRESETS, FONTS, DISPLAYS, SCALES, DEFAULTS };
})();
