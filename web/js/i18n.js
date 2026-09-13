const i18n = (() => {
  const DEFAULT_LANG = "pt-BR";

  const STRINGS = {
    "pt-BR": {
      "nav.facilities": "Facilities",
      "nav.resources": "Catálogo de Recursos",

      "facilities.title": "Facilities",
      "facilities.namePlaceholder": "Nome da facility (ex: Facility Weathered Expanse)",
      "facilities.add": "+ Nova Facility",
      "facilities.loading": "Carregando...",
      "facilities.empty": "Nenhuma facility cadastrada ainda.",
      "facilities.updatedAt": "Atualizada em {date}",

      "resources.title": "Catálogo de Recursos",
      "resources.intro1": "Lista de recursos compartilhada entre todas as facilities — cadastre aqui uma vez (ícone, meta de estoque opcional) e reuse em qualquer prédio. Você também pode criar um recurso novo direto na hora de lançar estoque, se preferir.",
      "resources.intro2": "Marque \"é matéria-prima\" só pros recursos que você efetivamente farma no mundo (ex: Coal, Sulfur). Desmarque pra itens que seus prédios produzem/transformam (ex: Coke, Cmat) — assim a recomendação de farm do relatório nunca sugere \"farmar\" algo que só sai de produção local.",
      "resources.importTitle": "📖 Importar do catálogo Foxhole",
      "resources.importSubtitle": "Nomes fixos (vêm da wiki), você pode dar um apelido depois de importar.",
      "resources.searchPlaceholder": "Buscar (ex: coal, coke, 20mm)...",
      "resources.searchHint": "Digite pra buscar entre {n} itens.",
      "resources.searchEmpty": "Nada encontrado.",
      "resources.produced": "(produzido)",
      "resources.alreadyImported": "já importado",
      "resources.import": "+ importar",
      "resources.imported": "{name} importado!",
      "resources.manualTitle": "Ou cadastre manualmente",
      "resources.namePlaceholder": "Nome (ex: Coal, Cmat, Am3)",
      "resources.targetPlaceholder": "Meta (opcional)",
      "resources.add": "+ Adicionar",
      "resources.farmableLabel": "é matéria-prima (farmável)",
      "resources.empty": "Nenhum recurso cadastrado ainda.",
      "resources.farmable": "matéria-prima",
      "resources.producedIntermediate": "(produzido/intermediário)",
      "resources.fromCatalog": "do catálogo Foxhole",
      "resources.target": "meta: {value}",
      "resources.nicknameBtn": "apelido",
      "resources.targetBtn": "meta",
      "resources.deleteConfirm": "Excluir esse recurso? Lançamentos de estoque associados também serão apagados.",
      "resources.nicknamePrompt": "Apelido (deixe vazio pra usar o nome padrão):",
      "resources.targetPrompt": "Meta de estoque (deixe vazio pra remover):",
      "resources.invalidNumber": "Digite um número válido.",

      "common.delete": "Excluir",
      "common.edit": "Editar",
      "common.save": "Salvar",

      "facilityDetail.rename": "Renomear",
      "facilityDetail.deleteFacility": "Excluir facility",
      "facilityDetail.tabBuildings": "Prédios & Estoque",
      "facilityDetail.tabReport": "Relatório",
      "facilityDetail.tabHistory": "Histórico",
      "facilityDetail.notFound": "Facility não encontrada.",
      "facilityDetail.renamePrompt": "Novo nome da facility:",
      "facilityDetail.deleteConfirm": "Excluir essa facility? Todos os prédios, estoques e relatórios serão apagados.",
      "facilityDetail.freeBuilding": "Prédio livre (sem tipo)",
      "facilityDetail.buildingNamePlaceholder": "Apelido (opcional — usa o nome do tipo se vazio)",
      "facilityDetail.addBuilding": "+ Prédio",
      "facilityDetail.noBuildings": "Nenhum prédio cadastrado ainda.",
      "facilityDetail.needNameOrType": "Informe um apelido ou selecione um tipo do Foxhole.",
      "facilityDetail.noEntries": "sem lançamentos",
      "facilityDetail.launchStock": "+ Lançar estoque",
      "facilityDetail.sendPrint": "📷 Enviar print (OCR)",
      "facilityDetail.production": "⚙️ Produção",
      "facilityDetail.foxholeType": "tipo Foxhole",
      "facilityDetail.dragToReorder": "arraste para reordenar",
      "facilityDetail.liquidTankTitle": "🧪 Tanque de Líquido",
      "facilityDetail.liquidPrompt": "{name} — quantidade atual no tanque (máx {max} unidades / 5000L):",
      "facilityDetail.deleteBuildingConfirm": "Excluir o prédio \"{name}\"? Estoques e imagens associados também serão apagados.",
      "facilityDetail.editNicknamePrompt": "Apelido (vazio usa o nome do tipo):",
      "facilityDetail.editNamePrompt": "Nome do prédio:",
      "facilityDetail.recipeLabel": "Receita em produção",
      "facilityDetail.noRecipe": "— nenhuma —",
      "facilityDetail.addQueue": "+ Adicionar fila",
      "facilityDetail.queueTotal": "{total} / {max} filas em uso",
      "facilityDetail.saveProduction": "Salvar Produção",
      "facilityDetail.productionHint": "Estimativa informativa (não sincroniza com o jogo) — ⚠ = receita não verificada quanto à facção, confira antes de confiar.",
      "facilityDetail.productionUpdated": "Produção atualizada!",
      "facilityDetail.saveStock": "Salvar Lançamento",
      "facilityDetail.predefinedHint": "Itens desse tipo de prédio (Foxhole). Deixe em branco o que não quiser lançar. Aceita {ex1}, {ex2} ou {ex3}.",
      "facilityDetail.fillOneQty": "Preencha pelo menos uma quantidade.",
      "facilityDetail.stockSaved": "Estoque lançado!",
      "facilityDetail.addRow": "+ Adicionar linha",
      "facilityDetail.resourcePlaceholder": "Recurso (ex: Coal)",
      "facilityDetail.qtyPlaceholder": "Qtd (ex: 25.7k)",
      "facilityDetail.freeformHint": "Aceita formatos como {ex1}, {ex2} ou {ex3}.",
      "facilityDetail.fillOneRow": "Preencha pelo menos uma linha.",
      "facilityDetail.production.insufficient": "⚙️ {queue}x em produção configurada — estoque insuficiente pra 1 ciclo (precisa de {needed} por ciclo).",
      "facilityDetail.production.line": "⚙️ {queue}x em produção — {cycles} ciclos com o estoque atual, pronto em {duration} (~{eta}): {outputs}",
      "facilityDetail.production.leftover": ". Sobra: {leftovers}",

      "print.ocrAvailable": "✓ OCR automático disponível — o valor lido vem pré-preenchido, mas sempre confirme antes de salvar.",
      "print.ocrUnavailable": "⚠ OCR automático indisponível (Tesseract não encontrado no sistema). Você ainda pode recortar a imagem e digitar os valores manualmente.",
      "print.dropzone": "Clique pra escolher um arquivo, arraste uma imagem aqui, ou cole (Ctrl+V) um print copiado.",
      "print.dragHint": "Arraste um retângulo bem rente ao número (evite pegar o ícone) — quanto mais justo o recorte, melhor a leitura automática.",
      "print.modeAuto": "🔍 Detectar painel automaticamente",
      "print.modeManual": "✏️ Recorte manual",
      "print.dragHintAuto": "Desenhe um retângulo ao redor do painel STOCKPILE inteiro (o quadro com todos os ícones de item) — os itens dentro dele são identificados automaticamente.",
      "print.detecting": "Analisando o painel...",
      "print.detected": "{n} item(ns) detectado(s) — confira antes de salvar.",
      "print.detectNone": "Nenhum item reconhecido nesse recorte. Tente um recorte mais justo ao redor do painel, ou use o recorte manual.",
      "print.detectUnavailable": "⚠ Detecção automática indisponível (OpenCV não encontrado no sistema). Use o recorte manual.",
      "print.detectFailed": "Falha ao detectar itens no painel.",
      "print.ambiguousNote": "⚠ pode ser \"{rival}\" — confira o item antes de salvar.",
      "print.uploaded": "Print enviado!",
      "print.uploadFailed": "Falha ao carregar a imagem.",
      "print.resourcePlaceholder": "Recurso",
      "print.qtyPlaceholder": "Qtd",
      "print.fillOneCrop": "Preencha recurso e quantidade em pelo menos um recorte.",
      "print.saved": "{n} lançamento(s) salvos a partir do print!",
      "print.saveEntries": "Salvar Lançamentos",

      "report.generatedAt": "Gerado em {date}",
      "report.blocksTitle": "Blocos (copiar individualmente)",
      "report.header": "Cabeçalho",
      "report.stock": "Estoque Atual",
      "report.recommendation": "Recomendação de Farm",
      "report.copy": "copiar",
      "report.discordParts": "Mensagens para o Discord ({n} partes, limite 2000 chars)",
      "report.discordReady": "Mensagem pronta para o Discord",
      "report.part": "Parte {i}/{n}",
      "report.message": "Mensagem",
      "report.generate": "📋 Gerar Relatório Agora",
      "report.generating": "Gerando...",
      "report.generated": "Relatório gerado!",
      "report.noneYet": "Nenhum relatório gerado ainda.",
      "report.reportOf": "Relatório de {date}",
      "report.expand": "expandir ▾",

      "ui.copied": "Copiado!",
      "ui.copyFailed": "Não consegui copiar automaticamente. Selecione e copie manualmente.",
      "app.notFound": "Página não encontrada.",
      "app.error": "Erro: {message}",
    },
    "en-US": {
      "nav.facilities": "Facilities",
      "nav.resources": "Resource Catalog",

      "facilities.title": "Facilities",
      "facilities.namePlaceholder": "Facility name (e.g. Facility Weathered Expanse)",
      "facilities.add": "+ New Facility",
      "facilities.loading": "Loading...",
      "facilities.empty": "No facilities registered yet.",
      "facilities.updatedAt": "Updated on {date}",

      "resources.title": "Resource Catalog",
      "resources.intro1": "Resource list shared across all facilities — register each one once (icon, optional stock target) and reuse it in any building. You can also create a new resource straight from the stock form, if you prefer.",
      "resources.intro2": "Only check \"is raw material\" for resources you actually farm from the world (e.g. Coal, Sulfur). Uncheck it for items your buildings produce/transform (e.g. Coke, Cmat) — that way the report's farm recommendation never suggests \"farming\" something that only comes from local production.",
      "resources.importTitle": "📖 Import from Foxhole catalog",
      "resources.importSubtitle": "Fixed names (from the wiki) — you can give it a nickname after importing.",
      "resources.searchPlaceholder": "Search (e.g. coal, coke, 20mm)...",
      "resources.searchHint": "Type to search {n} items.",
      "resources.searchEmpty": "Nothing found.",
      "resources.produced": "(produced)",
      "resources.alreadyImported": "already imported",
      "resources.import": "+ import",
      "resources.imported": "{name} imported!",
      "resources.manualTitle": "Or register manually",
      "resources.namePlaceholder": "Name (e.g. Coal, Cmat, Am3)",
      "resources.targetPlaceholder": "Target (optional)",
      "resources.add": "+ Add",
      "resources.farmableLabel": "is raw material (farmable)",
      "resources.empty": "No resources registered yet.",
      "resources.farmable": "raw material",
      "resources.producedIntermediate": "(produced/intermediate)",
      "resources.fromCatalog": "from the Foxhole catalog",
      "resources.target": "target: {value}",
      "resources.nicknameBtn": "nickname",
      "resources.targetBtn": "target",
      "resources.deleteConfirm": "Delete this resource? Associated stock entries will also be deleted.",
      "resources.nicknamePrompt": "Nickname (leave empty to use the default name):",
      "resources.targetPrompt": "Stock target (leave empty to remove):",
      "resources.invalidNumber": "Enter a valid number.",

      "common.delete": "Delete",
      "common.edit": "Edit",
      "common.save": "Save",

      "facilityDetail.rename": "Rename",
      "facilityDetail.deleteFacility": "Delete facility",
      "facilityDetail.tabBuildings": "Buildings & Stock",
      "facilityDetail.tabReport": "Report",
      "facilityDetail.tabHistory": "History",
      "facilityDetail.notFound": "Facility not found.",
      "facilityDetail.renamePrompt": "New facility name:",
      "facilityDetail.deleteConfirm": "Delete this facility? All buildings, stock, and reports will be deleted.",
      "facilityDetail.freeBuilding": "Free building (no type)",
      "facilityDetail.buildingNamePlaceholder": "Nickname (optional — uses the type name if empty)",
      "facilityDetail.addBuilding": "+ Building",
      "facilityDetail.noBuildings": "No buildings registered yet.",
      "facilityDetail.needNameOrType": "Enter a nickname or select a Foxhole type.",
      "facilityDetail.noEntries": "no entries",
      "facilityDetail.launchStock": "+ Log stock",
      "facilityDetail.sendPrint": "📷 Send print (OCR)",
      "facilityDetail.production": "⚙️ Production",
      "facilityDetail.foxholeType": "Foxhole type",
      "facilityDetail.dragToReorder": "drag to reorder",
      "facilityDetail.liquidTankTitle": "🧪 Liquid Tank",
      "facilityDetail.liquidPrompt": "{name} — current amount in the tank (max {max} units / 5000L):",
      "facilityDetail.deleteBuildingConfirm": "Delete building \"{name}\"? Associated stock and images will also be deleted.",
      "facilityDetail.editNicknamePrompt": "Nickname (empty uses the type name):",
      "facilityDetail.editNamePrompt": "Building name:",
      "facilityDetail.recipeLabel": "Recipe in production",
      "facilityDetail.noRecipe": "— none —",
      "facilityDetail.addQueue": "+ Add queue",
      "facilityDetail.queueTotal": "{total} / {max} queues in use",
      "facilityDetail.saveProduction": "Save Production",
      "facilityDetail.productionHint": "Informational estimate (doesn't sync with the game) — ⚠ = recipe not faction-verified, double check before relying on it.",
      "facilityDetail.productionUpdated": "Production updated!",
      "facilityDetail.saveStock": "Save Entry",
      "facilityDetail.predefinedHint": "Items for this building type (Foxhole). Leave blank what you don't want to log. Accepts {ex1}, {ex2}, or {ex3}.",
      "facilityDetail.fillOneQty": "Fill in at least one quantity.",
      "facilityDetail.stockSaved": "Stock logged!",
      "facilityDetail.addRow": "+ Add row",
      "facilityDetail.resourcePlaceholder": "Resource (e.g. Coal)",
      "facilityDetail.qtyPlaceholder": "Qty (e.g. 25.7k)",
      "facilityDetail.freeformHint": "Accepts formats like {ex1}, {ex2}, or {ex3}.",
      "facilityDetail.fillOneRow": "Fill in at least one row.",
      "facilityDetail.production.insufficient": "⚙️ {queue}x production set up — not enough stock for 1 cycle (needs {needed} per cycle).",
      "facilityDetail.production.line": "⚙️ {queue}x in production — {cycles} cycles with current stock, ready in {duration} (~{eta}): {outputs}",
      "facilityDetail.production.leftover": ". Leftover: {leftovers}",

      "print.ocrAvailable": "✓ Automatic OCR available — the read value comes pre-filled, but always confirm before saving.",
      "print.ocrUnavailable": "⚠ Automatic OCR unavailable (Tesseract not found on the system). You can still crop the image and type the values manually.",
      "print.dropzone": "Click to choose a file, drag an image here, or paste (Ctrl+V) a copied screenshot.",
      "print.dragHint": "Drag a rectangle tight around just the number (avoid the icon) — the tighter the crop, the better the automatic reading.",
      "print.modeAuto": "🔍 Auto-detect panel",
      "print.modeManual": "✏️ Manual crop",
      "print.dragHintAuto": "Draw a rectangle around the whole STOCKPILE panel (the box with every item icon) — the items inside it are identified automatically.",
      "print.detecting": "Analyzing the panel...",
      "print.detected": "{n} item(s) detected — review before saving.",
      "print.detectNone": "No items recognized in that crop. Try a tighter crop around the panel, or use manual crop.",
      "print.detectUnavailable": "⚠ Automatic detection unavailable (OpenCV not found on the system). Use manual crop.",
      "print.detectFailed": "Failed to detect items in the panel.",
      "print.ambiguousNote": "⚠ could be \"{rival}\" — double-check this item before saving.",
      "print.uploaded": "Screenshot uploaded!",
      "print.uploadFailed": "Failed to load the image.",
      "print.resourcePlaceholder": "Resource",
      "print.qtyPlaceholder": "Qty",
      "print.fillOneCrop": "Fill in resource and quantity for at least one crop.",
      "print.saved": "{n} entry(ies) saved from the screenshot!",
      "print.saveEntries": "Save Entries",

      "report.generatedAt": "Generated on {date}",
      "report.blocksTitle": "Blocks (copy individually)",
      "report.header": "Header",
      "report.stock": "Current Stock",
      "report.recommendation": "Farm Recommendation",
      "report.copy": "copy",
      "report.discordParts": "Discord messages ({n} parts, 2000 char limit)",
      "report.discordReady": "Message ready for Discord",
      "report.part": "Part {i}/{n}",
      "report.message": "Message",
      "report.generate": "📋 Generate Report Now",
      "report.generating": "Generating...",
      "report.generated": "Report generated!",
      "report.noneYet": "No reports generated yet.",
      "report.reportOf": "Report from {date}",
      "report.expand": "expand ▾",

      "ui.copied": "Copied!",
      "ui.copyFailed": "Couldn't copy automatically. Select and copy manually.",
      "app.notFound": "Page not found.",
      "app.error": "Error: {message}",
    },
  };

  function getLang() {
    return localStorage.getItem("lang") || DEFAULT_LANG;
  }

  function setLang(lang) {
    localStorage.setItem("lang", lang);
  }

  function t(key, vars) {
    const table = STRINGS[getLang()] || STRINGS[DEFAULT_LANG];
    let str = table[key] ?? STRINGS[DEFAULT_LANG][key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        str = str.replaceAll(`{${k}}`, v);
      }
    }
    return str;
  }

  function applyStaticText(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
  }

  // Foxhole catalog resource/building names live in a separate translation
  // domain from UI chrome (wiki-sourced names, not free UI copy — see project
  // notes). A resource's stored `name`/building's stored `name` is the
  // English default baked in at creation time; resolve the localized catalog
  // name instead when nothing custom (nickname / edited name) overrides it.
  // A Foxhole catalog def (resource or building type) exposes both
  // name_en/name_pt directly — this just picks the right one.
  function catalogName(def) {
    if (!def) return "";
    return (getLang() === "en-US" ? def.name_en : def.name_pt || def.name_en) || "";
  }

  function resourceName(resource, foxholeResourceDefs) {
    if (resource.nickname) return resource.nickname;
    const def = resource.resource_def_key && foxholeResourceDefs && foxholeResourceDefs[resource.resource_def_key];
    return (def && catalogName(def)) || resource.name;
  }

  function buildingName(building, foxholeType) {
    if (!foxholeType) return building.name;
    if (building.name !== foxholeType.name_en) return building.name;
    return catalogName(foxholeType) || building.name;
  }

  return { t, getLang, setLang, applyStaticText, catalogName, resourceName, buildingName };
})();
