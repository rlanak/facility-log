// The game save (.sav) picked by the user, remembered so it isn't picked
// again every time:
// - Chrome/Edge (File System Access API): the file handle is kept in
//   IndexedDB — later reads are one click (the browser may ask once per
//   session to allow reading it again). Always the file's current content.
// - Firefox and others: browsers don't let a page keep a file, so the File
//   picked earlier is reused while the tab stays open.
// Local mode doesn't need any of this: the server reads this PC's save
// itself (api.listSavePins(null)).
const saveFile = (() => {
  const supported = typeof window.showOpenFilePicker === "function";
  const DB = "facility-log";
  const STORE = "handles";
  const KEY = "foxhole-save";
  let memoryFile = null;

  function withStore(mode, fn) {
    return new Promise((resolve, reject) => {
      let open;
      try {
        open = indexedDB.open(DB, 1);
      } catch (err) {
        reject(err);
        return;
      }
      open.onupgradeneeded = () => open.result.createObjectStore(STORE);
      open.onerror = () => reject(open.error);
      open.onsuccess = () => {
        const tx = open.result.transaction(STORE, mode);
        const req = fn(tx.objectStore(STORE));
        tx.oncomplete = () => resolve(req && req.result);
        tx.onerror = () => reject(tx.error);
      };
    });
  }
  const getHandle = () => (supported ? withStore("readonly", (s) => s.get(KEY)).catch(() => null) : Promise.resolve(null));
  const setHandle = (h) => withStore("readwrite", (s) => s.put(h, KEY)).catch(() => {});

  function pickWithInput() {
    return new Promise((resolve) => {
      const input = document.createElement("input");
      input.type = "file";
      input.accept = ".sav";
      input.addEventListener("change", () => resolve(input.files[0] || null));
      input.addEventListener("cancel", () => resolve(null));
      input.click();
    });
  }

  // Asks for the file. Returns a File, or null if the user cancelled.
  async function pick() {
    if (supported) {
      try {
        const [handle] = await window.showOpenFilePicker({
          id: "foxhole-save",
          types: [{ description: "Foxhole save", accept: { "application/octet-stream": [".sav"] } }],
        });
        await setHandle(handle);
        memoryFile = null;
        return await handle.getFile();
      } catch (err) {
        if (err && err.name === "AbortError") return null;
        // Blocked in this context (e.g. an iframe): fall back to the input.
      }
    }
    const file = await pickWithInput();
    if (file) memoryFile = file;
    return file;
  }

  // {name} of the remembered file, or null.
  async function remembered() {
    const handle = await getHandle();
    if (handle) return { name: handle.name };
    return memoryFile ? { name: memoryFile.name } : null;
  }

  // True when the remembered file can be read without a click (permission
  // already granted) — then it's read as soon as the form opens.
  async function readableNow() {
    const handle = await getHandle();
    if (!handle) return Boolean(memoryFile);
    try {
      return (await handle.queryPermission({ mode: "read" })) === "granted";
    } catch (_) {
      return false;
    }
  }

  // The remembered file's current content (call it from a click: Chrome may
  // ask to allow reading it again). Throws if it can't be read anymore.
  async function readRemembered() {
    const handle = await getHandle();
    if (handle) {
      let perm = await handle.queryPermission({ mode: "read" });
      if (perm !== "granted") perm = await handle.requestPermission({ mode: "read" });
      if (perm !== "granted") throw new Error(i18n.t("saveFile.denied"));
      return await handle.getFile();
    }
    if (!memoryFile) throw new Error(i18n.t("saveFile.none"));
    // A File the page can no longer read (moved, or the browser refuses a
    // changed file) has to be picked again.
    await memoryFile.slice(0, 1).arrayBuffer();
    return memoryFile;
  }

  async function forget() {
    memoryFile = null;
    if (supported) await withStore("readwrite", (s) => s.delete(KEY)).catch(() => {});
  }

  // Buttons to get the save, for any form that reads it. `onFile(file)` gets
  // a File (null = read this PC's save on the server, local mode).
  async function sourceBar({ localSave, onFile }) {
    const el = (tag, attrs, children) => ui.el(tag, attrs, children);
    const bar = el("div", { class: "mb-3" });
    const btn = "text-xs border rounded px-2 py-1 ";
    const primary = btn + "border-emerald-800 hover:border-emerald-600 text-emerald-400";
    const secondary = btn + "border-zinc-700 hover:border-zinc-500";

    async function draw() {
      bar.innerHTML = "";
      const row = el("div", { class: "flex flex-wrap items-center gap-2" });
      bar.appendChild(row);
      if (localSave) {
        const b = el("button", { type: "button", class: primary }, i18n.t("saveImport.readLocal"));
        b.addEventListener("click", () => onFile(null));
        row.appendChild(b);
      }
      const known = await remembered();
      if (known) {
        const again = el("button", { type: "button", class: localSave ? secondary : primary }, i18n.t("saveFile.readAgain", { name: known.name }));
        again.addEventListener("click", async () => {
          try {
            onFile(await readRemembered());
          } catch (err) {
            ui.toast(err.message || i18n.t("saveFile.pickAgain"), true);
            memoryFile = null;
            draw();
          }
        });
        row.appendChild(again);
      }
      const other = el("button", { type: "button", class: secondary }, known ? i18n.t("saveFile.other") : i18n.t("saveImport.upload"));
      other.addEventListener("click", async () => {
        const file = await pick();
        if (!file) return;
        await draw();
        onFile(file);
      });
      row.appendChild(other);
      if (known && supported) {
        const forgetBtn = el("button", { type: "button", class: "text-[11px] text-zinc-500 hover:text-red-400" }, i18n.t("saveFile.forget"));
        forgetBtn.addEventListener("click", async () => {
          await forget();
          draw();
        });
        row.appendChild(forgetBtn);
      }
      if (!localSave) {
        bar.appendChild(el("p", { class: "text-[11px] text-zinc-500 mt-2 break-all" }, i18n.t("saveImport.whereIsSave")));
        bar.appendChild(
          el("p", { class: "text-[11px] text-zinc-500 mt-1" }, supported ? i18n.t("saveFile.rememberedHint") : i18n.t("saveFile.firefoxHint"))
        );
      }
    }
    await draw();
    // Read right away when that needs no click: this PC's save in local
    // mode, or a remembered file the browser still lets the page read.
    if (localSave) onFile(null);
    else if (await readableNow()) readRemembered().then(onFile, () => {});
    return bar;
  }

  return { supported, pick, remembered, readRemembered, forget, sourceBar };
})();
