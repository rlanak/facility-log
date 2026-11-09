# facility-log — contexto para o Claude Code

Arquivo versionado e **público**: só entra aqui o que qualquer um pode ler. Nada de contexto
pessoal, IDs do Discord, nome do regimento, localização no mapa do jogo, hardware ou detalhes de
onde o app está rodando — nem aqui nem em nenhum arquivo versionado. Commits sempre com o e-mail
noreply do GitHub.

## O que é

App que transforma o estoque das facilities do jogo **Foxhole** (lançado à mão, lido de prints do
painel STOCKPILE ou do save do jogo) em relatório Markdown pronto pro Discord, com o cálculo do que
falta produzir/farmar pra bater Metas. Roda local (padrão) ou na web com login pelo Discord.

**Regras que não mudam:**
- **Modo local sempre funciona sozinho:** sem conta, login, serviço pago ou IA. Web e IA são opcionais,
  ligados por configuração — nunca pré-requisito.
- IA paga só com a chave do próprio usuário, escolhida por ele em Configurações.
- Valor lido por OCR, IA ou save **nunca salva sozinho**: sempre pré-preenche um campo editável que o
  usuário confirma.
- Relatório pro Discord respeita 2000 caracteres por mensagem (partes numeradas, sem cortar bloco).
- **Só itens Colonial** (ou das duas facções) no catálogo; nada exclusivo de Warden.
- Acompanhamento de mSupps/túneis de manutenção está fora do escopo — não reintroduzir.

## Como rodar

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/build_save_parser.py   # opcional: leitor do save (precisa de cargo)
.venv/Scripts/python.exe scripts/create_shortcut.py     # opcional: atalho com ícone na bandeja
.venv/Scripts/python.exe run.py                         # dev: console + auto-reload
```

`http://localhost:8000` — um processo uvicorn serve API e frontend. `run.py --tray` (o atalho) roda
sem console via `pythonw`, com ícone na bandeja; como `pythonw` não tem stdout/stderr, o modo bandeja
redireciona os dois pra `data/facility_log.log` antes de subir o servidor. Abrir o atalho com o app já
rodando só abre a página.

Modo web: `.env` (ver `.env.example`) ou Docker (`docker compose up -d`, imagem publicada). Ver "Modo web".

## Stack e estrutura

Python + FastAPI + SQLite (SQLAlchemy, migrações manuais em `database.apply_migrations()`). Frontend
HTML/JS puro + Tailwind via CDN, sem build — o FastAPI serve `web/` como estático (sem cache).

```
app/
  main.py, auth.py (login Discord), envfile.py (.env), crypto.py (segredos no banco),
  database.py, models.py, schemas.py, crud.py, paths.py
  routers/   facilities, buildings, private_orders, resources, stock, reports, foxhole, images, save,
             settings, auth
  services/
    report_generator.py   relatório Markdown + versão Discord
    material_chain.py     cadeia de produção pra bater uma Meta + tempo total
    production.py         estimativa de ciclos/tempo por prédio
    projection.py         estimativa do Dashboard (estoque projetado pelas filas)
    private_orders.py     filas privadas: quantos faltam, quando fica pronta, 28h
    discord_dashboard.py  painel no Discord por webhook + laço de 60s
    icon_match_service.py detecção de itens no print (template matching)
    capture/              quem lê o número no servidor: RapidOCR, Ollama ou API
    save_reader.py        lê o save via tools/save-parser
    foxhole_data.py       catálogo data/foxhole/*.json, nomes localizados
    number_parser.py      "25.7k", "1,8k", "32000"
    errors_i18n.py        mensagens de erro pt-BR/en-US
web/js/  api.js (sempre anexa ?lang&catalog_lang), ui.js (toast, el(), openModal()), app.js (router),
         personalAI.js (leitura com a IA do PC da pessoa, pelo navegador),
         i18n.js, views/ (facilities, facilityDetail, targets, itemPanel, print, report, saveImport,
         settings, dashboard, privateOrders)
data/foxhole/  resources.json, building_types.json — catálogo versionado
data/          banco, uploads, icon_exemplars — dados do usuário, gitignored
tools/save-parser/  leitor do save em Rust (CLI) — tem o próprio CLAUDE.md
scripts/       build_save_parser.py, create_shortcut.py
```

## Modelo de dados

- `resources` — catálogo global. `name` em inglês **nunca muda**; exibição localizada é resolvida na
  hora. `nickname` (apelido global), `resource_def_key` (link pro catálogo), flags de origem padrão
  `farmable` / `imported` / `unlimited` (prioridade: unlimited > imported > farmable). `target_max` é
  legado e não é lido.
- `facility_item_origins` — origem do item **por facility** (produced/farmed/imported/unlimited); sem
  linha vale o padrão global. `crud.resources_for_facility()` devolve **cópias** (`SimpleNamespace`,
  nunca linhas do ORM) com os flags da facility — é o que relatório, estimativa, Metas e
  `GET /api/resources?facility_id=` usam.
- `facilities` — nome, `owner_id`, `private`.
- `facility_targets` — Meta por facility (`facility_id`, `resource_id`, `target_max`).
- `buildings` — `building_type_key`, `production_slots` (JSON `[{recipe_key, queue_count}]`),
  `position`, `upgrade` (módulo instalado; NULL = base), `location` (texto livre), `save_pin_key`.
- `private_orders` — fila privada (Personal) lançada à mão: `owner_name` (texto livre), `recipe_key`,
  `inputs_json` (insumos carregados), `cycle_left_seconds`, `done_before` (número na saída quando foi
  lançada = já fabricado), `started_at`, `closed_at` (retirada). Ver
  "Filas privadas".
- `stock_entries` — **log append-only**: estoque atual = linha mais recente de
  prédio+recurso+`storage` (`"normal"` ou `"tank"`). Excluir (`DELETE .../stock/{resource_id}?storage=`)
  apaga todo o histórico daquela combinação ("não devia ter lançado"), sem afetar relatórios já gerados.
  `created_by_id` no modo web.
- `reports` — snapshot congelado: `markdown_content`, `discord_content` (versão consolidada do Discord),
  `stock_snapshot`, `lang` (idioma da geração), `created_by_id`.
- `upload_images`, `codename_aliases` (código do jogo → recurso escolhido pelo usuário), `users`
  (só ID, nome e avatar do Discord), `facility_webhooks`, `app_settings`.

## Catálogo Foxhole (`data/foxhole/*.json`)

168 recursos e 10 tipos de prédio: 8 de produção + Material Transfer Station e Resource Transfer
Station (`storage: true`, sem filas). Cada recurso tem `name: {en, pt}`, `codename` (nome interno do
jogo, o que o save guarda — ex: Construction Materials = `FacilityMaterials1`), `category` e, nas
estações, `accepts` (o que cada uma guarda, da tabela "Storage" da wiki; o "Lançar estoque" de uma
estação só mostra esses itens).

Fontes: wiki (`foxhole.wiki.gg`, via MediaWiki API — `action=parse`, nunca scraping de página
renderizada, nunca adivinhar nome de arquivo de ícone) e o catálogo extraído do jogo pelo projeto FIR
(`github.com/GICodeWarrior/fir`). Ícones do FIR vêm sem transparência: converter pra RGBA (alfa =
canal mais claro), porque o detector lê o alfa. Quando FIR e wiki discordam, **a wiki vale**.

**Receita com líquido: `qty` no JSON é em Litros, nunca em unidades.** Toda leitura de quantidade de
receita pra cálculo passa por `foxhole_data.recipe_io_qty(io)` (converte por `liters_per_unit`);
ler `io["qty"]` direto dá estoque de líquido 30-50x errado.

Depois de atualização do jogo, conferir receitas contra a wiki (tempo, insumo, produto).

## i18n — duas camadas independentes

Idioma da **interface** (`localStorage["lang"]`) e do **catálogo** (`localStorage["catalogLang"]`,
segue a interface até o usuário escolher outro). Todo endpoint recebe `lang` (mensagens) e
`catalog_lang` (nomes de item/prédio); relatório e estimativa misturam os dois na mesma string, por
isso recebem ambos. Relatório gerado fica no idioma da geração. Idioma novo: chave em `STRINGS`
(`i18n.js`), `_STRINGS` (`report_generator.py`, `errors_i18n.py`), `LANG_CODES` (`foxhole_data.py`),
opções nos dois seletores e tradução do catálogo.

## Data, hora e fuso

O banco guarda UTC (SQLite devolve sem offset — no navegador sempre `i18n.parseDate()`, que lê ISO sem offset como UTC; exibir com `i18n.formatDateTime()`/`formatTime()`, nunca `new Date(x).toLocale...`). Fuso do usuário: o do navegador ou o escolhido em Configurações (`localStorage["timeZone"]`); `api.js` manda `tz` em toda chamada, e todo horário que o servidor escreve em texto (cabeçalho do relatório, "pronto ~21:37") usa `timezones.user_now(tz)` — o servidor Docker roda em UTC. `tzdata` no requirements (Windows não tem base de fusos). Discord usa `<t:unix>`, que já sai no fuso de quem lê.

## Produção, tanques e estimativas

- Um prédio roda várias receitas ao mesmo tempo, até `queue_slots`. Na exibição, slots com a mesma
  receita são somados. Estimativa é aproximada: cada slot é calculado contra o mesmo estoque.
- Upgrade: cada prédio instala no máximo um, que **acrescenta** receitas às da base; o modal de
  produção só oferece base + upgrade. Receita já em fila que o upgrade não oferece fica marcada ⚠,
  nunca é apagada calada. Prédio sem `upgrade` salvo tem o upgrade inferido da receita em produção.
- **Líquidos** (`is_liquid`, `liters_per_unit`): tanque (cap 5000L por líquido por prédio) e caixa são
  quantidades **independentes** (`storage`); cálculo de produção soma as duas. Quais tanques aparecem
  vem das receitas ativas. Validação do cap arredonda os dois lados pra 2 casas (senão um tanque cheio
  dá falso "não cabe"). O "+" do tanque aceita unidades ou litros ("5000L"). Todo líquido **exibido**
  no relatório sai em Litros (`report_generator._display_qty()`); o banco guarda unidades.
- Modelo de produção (wiki): até 5 ordens em paralelo por prédio; **1 ciclo = 1 execução da receita**;
  tempo = `ceil(ciclos ÷ filas) × tempo do ciclo`. O texto sempre mostra a conta. Tempo de ciclo usa
  `format_cycle_time()` (mantém segundos), não `format_duration()`.
- Mensagem "estoque insuficiente" lista só os insumos realmente abaixo do necessário.

## Filas privadas (`private_orders.py`, `routers/private_orders.py`, `web/js/views/privateOrders.js`)

No jogo (wiki): até 5 ordens por prédio, públicas e privadas juntas; uma ordem por jogador por prédio;
na privada o jogador carrega os insumos à mão (líquido sai do tanque) e a saída fica num slot dele; não
retirada vai pro estoque público do prédio **28h depois de pronta**. No app:
- Lançada à mão no card ("Fila privada"): quem fez, receita (base + upgrade), insumos carregados, quanto
  falta no ciclo atual, hora do print (HH:MM no fuso do usuário; hora depois de agora = ontem).
- Conta: ciclos = mínimo de `carregado ÷ por ciclo` dos insumos sólidos, **+1 se há ciclo rodando**
  (suposição: o ciclo em andamento já tirou os insumos); pronto = início + resto do ciclo + ciclos ×
  tempo. Status `running` → `ready` → `released` (28h). O formulário repete a conta como prévia.
- **Nunca mexe no estoque público** (projeção, relatório e cadeia ignoram); só ocupa fila: públicas +
  privadas `running` ≤ `queue_slots`, conferido nos dois sentidos (salvar Produção e salvar fila privada).
- "Retirado" fecha a fila (`closed_at`) e opcionalmente lança a saída num prédio (estações primeiro):
  valor = estoque atual do destino + o que saiu, editável. "✕" apaga (lançada por engano).
- **Fabricado** = `done_before` + ciclos completos desde o lançamento; card, Dashboard e Discord mostram
  "fabricado X de Y". Fica no slot de quem fez: **não é estoque** — a Meta só conta o que está no estoque
  público de um prédio ou numa MTS/RTS; ao lado dela aparece só "N já fabricados em fila privada".
- **Print da ordem** (colar/arrastar/escolher no formulário): sobe como imagem do prédio e
  `POST .../private-orders/read-print` usa o mesmo detector dos prints de estoque, limitado aos itens das
  receitas do prédio (`only_keys`), lê os números com o leitor escolhido e o tempo com RapidOCR na imagem
  inteira (`readers.read_clock`, **só h:mm:ss** — "19:46" de um print do Discord é a hora da mensagem).
  Receita = a que explica mais itens com a saída **à direita** de todos os insumos; empate de ícone conta
  pro rival, e nível da mesma família (Assembly Materials I-V) vale pro que a receita pede — aí volta
  `unsure` e o formulário pede pra conferir. Só pré-preenche.
- Rotas ficam sob `/api/buildings/{id}/...` e `/api/facilities/{id}/...` (cobertas pelo bloqueio de
  facility privada).

## Meta → cálculo de cadeia (`material_chain.py`)

Pra cada Meta da facility abaixo do estoque, percorre as receitas de trás pra frente abatendo estoque
em cada nível, até folhas:
- `farmable` → "Farm necessário" (nunca decomposto em receita, mesmo que exista);
- `imported` → "Importar";
- `unlimited` → sempre disponível (também nunca limita estimativa e some do relatório);
- sem receita no catálogo → Farm;
- resto → "Produção necessária" e recursão nos insumos.

**De onde vem o estoque:** o produto da Meta conta em qualquer prédio; os **insumos** só nos prédios
que rodam aquela receita (mesmo tipo + mesma receita), mais as estações de armazenamento (MTS/RTS,
compartilhadas). Receita que ninguém roda usa os prédios do tipo sem nada em produção.

**Receita ambígua** (mais de uma produz o item): a que a facility já tem em produção > módulo Base >
primeiro candidato.

**Cuidado (bug já corrigido):** o resolver recebe a Meta **cheia**; o pool já tem o estoque atual. Passar
o déficit já subtraído desconta o mesmo estoque duas vezes. A subtração acontece uma vez, dentro de
`resolve()`.

**Tempo total** (`compute_production_time()`): calculado com 5 filas (referência, sempre mostrado) e com
as filas atuais (só se algum nó tem menos de 5); filas configuradas = soma de todos os slots/prédios da
receita. É em pipeline: um nó termina em `max(1º insumo pronto + tempo dele, último insumo pronto + 1
ciclo)`, o total é o término mais tarde, e o caminho crítico aparece como cadeia.

**Não modelado (de propósito):** produção em andamento não abate déficit (o app é gerador de relatório a
partir de estoque lançado, não tracker ao vivo); receitas disputando as mesmas filas; energia;
overflow automático tanque→caixa; transferência de líquido entre prédios.

## Relatório e Discord

`report_generator.generate_report(..., targets)` gera os blocos do app (cabeçalho, estoque por prédio,
recomendação) e, separado, `discord_content`: total consolidado da facility (`build_totals_block()`) +
recomendação com uma linha por item (`bulleted=True`). O Histórico remonta as partes do Discord a
partir de `discord_content`.

Pegadinha do Pydantic: campo novo num dict de `production.py` precisa ir no schema
(`ProductionEstimateOut`/`Item`), senão o `response_model` filtra calado.

## Captura de prints

Modal "Enviar print": Ctrl+V em qualquer lugar da página cola a imagem; arrastar e "Escolher arquivo"
também. Dois modos:
1. **Recorte manual** de cada número.
2. **Detecção automática** (`icon_match_service.detect_items`): o usuário marca o painel inteiro; template
   matching acha cada ícone e recorta o número.

Decisões do detector (medidas em prints reais — não desfazer sem medir de novo):
- Compara por **brancura** (`min(B,G,R)`), não cinza: fundos coloridos de mod viram escuro.
- Várias posições por ícone; descarta posição sem texto branco no canto do número (slot cinza = item
  zerado); decide por slot e resolve conflito (cada item num slot só).
- Slot vazio: `MIN_WHITE_FRACTION` 0,01. Caixa do número começa em `-0,25×tamanho` à esquerda.
- **Exemplos aprendidos** (`data/icon_exemplars/<item>/`, máx. 8): recorte de slot confirmado pelo
  usuário. Servem pra achar ícones que mods redesenham e pra desempatar itens do mesmo desenho
  (Assembly Materials I-V diferem só num selinho no canto — `BADGE_REGION`, `EXEMPLAR_MIN`,
  `EXEMPLAR_LEAD`). Empate não resolvido sempre fica marcado "confira". O `print.js` salva exemplo com o
  item **confirmado**, e só manda o código detectado se o nome não foi mexido (`confirmedDefKey()`).
- Slot com número que nenhum ícone explicou volta como "item não reconhecido" (grade deduzida dos
  slots reconhecidos; precisa de ≥ 2).
- Inventário de veículo (mesmo item em vários slots) não é suportado.
- **Zerar o que não está no print** (caixa no modal, lembrada em `localStorage["printZeroMissing"]`, ligada por padrão): o painel STOCKPILE lista tudo que existe, então item lançado no prédio que o print não mostra ganha uma linha **0** (`POST .../stock?zero_missing=true`, `crud.add_stock_entries`) — nunca apaga histórico, nunca mexe em tanque. A caixa mostra antes quais itens vão zerar. Linha com 0 some do card e do relatório (o cálculo ainda a vê).

**Quem lê o número no servidor** é escolhido em Configurações (`app_settings`, global): `rapidocr`
(padrão), `local_vlm` (Ollama na máquina do app) e `api_vlm` (Anthropic ou endpoint compatível com
OpenAI, chave do usuário). Indisponível → `capture.resolve_reader()` cai pro RapidOCR e o modal avisa.
Erro vira "não leu", nunca 500. A API devolve só `api_key_set` + 4 últimos caracteres. Tesseract foi
removido (acertava 18/106).

**A ideia da IA local é a IA do PC de cada pessoa, não a do servidor.** No modo local o servidor É o PC
dela, então `local_vlm` aparece normal. **No modo web** (login ligado) `local_vlm` some
(`capture.server_local_ai_allowed()`; `FACILITY_LOG_SERVER_OLLAMA=1` traz de volta, pra um servidor com
GPU) e uma escolha salva de `local_vlm` é lida como `rapidocr` (`effective_provider_choice`). No lugar,
cada pessoa pode ligar **"IA do meu computador"** em Configurações (`web/js/personalAI.js`,
`localStorage["personalAI"]`, só naquele navegador): o servidor só acha os itens
(`detect-stockpile?read=false`, cada item traz `number_x/y/width/height`) e o **navegador** manda cada
recorte pro Ollama da pessoa em `http://localhost:11434` — o servidor nunca fala com o PC dela. Mesmo
prompt, schema e limpeza do `readers.py` (manter os dois iguais). Se o Ollama não responder, a leitura
cai pro servidor (`readNumber` em `print.js`). Pré-requisito da pessoa: Ollama + `ollama pull glm-ocr` +
`OLLAMA_ORIGINS` com o endereço do site (senão o Ollama recusa o pedido do navegador); o Chrome pode
pedir permissão de acesso à rede local. Testado com a página em localhost (origem já liberada por
padrão no Ollama): leitura pelo navegador igual à do servidor nos 10 números de um print.

Medido em 32 prints reais (106 valores):

| Leitor | Roda em | Memória de vídeo | Acertos | Tempo relativo |
|---|---|---|---|---|
| RapidOCR | CPU | — | 91 | 1x |
| **glm-ocr** | Ollama | ~2,7 GB | 97 | ~1,1x |
| qwen3.5:9b | Ollama | ~6,3 GB | 98 | ~3x |
| qwen3-vl:4b | Ollama | não medida | 98 | ~10x |
| qwen3-vl:8b | Ollama | mais de 8 GB | não terminou no limite de 120s por número | — |

Escolha pela memória de vídeo livre (o jogo divide a placa): sem placa → RapidOCR; ~4 GB → `glm-ocr`
(recomendado); 8 GB+ → `qwen3.5:9b` também serve.

Decisões da IA: vê **só o recorte do número** (identificar itens no painel inteiro dá ~5/30); prompt
**sem números de exemplo** (senão ela repete o exemplo em slot vazio); slot sem texto branco é pulado
antes de chamar o leitor; Ollama com `num_predict: 32` (sem isso o glm-ocr entra em loop e o Ollama
devolve 500); `readers.sanitize()` troca letra parecida por dígito, aceita letra só como sufixo k/M e
trata "NONE" como vazio. Modelos do RapidOCR vêm no pacote pip.

## Leitura do save do jogo (`save_reader.py`, `tools/save-parser/`)

O save local (`%LOCALAPPDATA%\Foxhole\Saved\SaveGames\<steamid>_MapData.sav`, GVAS do UE4) guarda, pra
cada local **pinado** no mapa (até 25 por facção), o estoque que o jogo mostrou no tooltip da última vez
+ `LastUpdated`. Só atualiza quando o jogador abre o tooltip. O parse é do CLI Rust
(`foxhole-save-parser --json`) — **não reimplementar GVAS em Python**; o JSON é contrato (ver o
`CLAUDE.md` do parser). `pin_key()` = `"{map_id}:{x:.4f}:{y:.4f}"`, única identidade de um pin.
Binário procurado em `tools/save-parser/target/release/` ou `FOXHOLE_SAVE_PARSER`.

"📌 Importar do save" em todo card de prédio: lista pins com estoque (código do jogo → recurso pelo
`codename` ou por `codename_aliases`), pré-seleciona o pin vinculado (`save_pin_key`) ou o mais recente
do mesmo tipo, mostra linhas editáveis, salva com `source="save"`. Prédio vinculado não mostra seletor
(só "Vinculado a … · Desvincular"); pin sumido do save volta o seletor. Ao vincular, prédio sem local
recebe região + quadrado do pin. No modo web o save "deste PC" seria o do servidor: só é oferecido a um
navegador na própria máquina (`auth.is_local_request`); usuário remoto envia o `.sav`.
`crud.get_or_create_resource()` casa primeiro por `resource_def_key`, depois por nome.

- **Arquivo lembrado** (`web/js/saveFile.js`, modo web): Chrome/Edge guardam o *handle* do `.sav` no IndexedDB (File System Access API) — depois é só "Ler de novo", sempre o conteúdo atual (o navegador pode pedir permissão uma vez por sessão; com permissão já dada, lê sozinho ao abrir). Firefox não deixa site guardar arquivo: reaproveita o `File` enquanto a aba estiver aberta. Navegador nunca acessa a pasta sem o usuário escolher o arquivo uma vez.
- O seletor de pin mostra os 2 primeiros itens de cada pin (vários pins com o mesmo nome e quadrado) e "📌 já é <prédio (local)>" pros pins vinculados a outro prédio da facility; a pré-seleção pula esses.
- Pin do save lista tudo que há no estoque: item lançado no prédio que sumiu do pin ganha 0 (caixa, ligada por padrão; linha desmarcada não zera).
- **"📌 Atualizar vinculados do save"** (aba Prédios, só aparece com algum prédio vinculado; `saveImport.renderBulkUI`): lê o save uma vez e mostra, por prédio vinculado, atual → save (editável, prédio desmarcável), incluindo os zeros. Código que o catálogo não conhece fica de fora (resolve no formulário do prédio).

Bug do jogo: tooltip pinado para de atualizar se a estrutura for melhorada — despinar e pinar de novo.
Não conferido: se `Quantity` é item ou caixa em stockpile que guarda caixa.

## Telas

- **Visual:** ícones em SVG de linha (`ui.icon(nome, classes)`, lista em `ui.js`) no lugar de emoji em botões, abas e cabeçalhos — emoji muda de desenho em cada sistema; logo = hexágono do mapa com fábrica (`ui.logo()`, `web/assets/logo.svg` é o favicon). Títulos, nomes de prédio e números do card na fonte de títulos. Home: card por facility com ícones dos tipos de prédio, filas rodando/paradas e Metas em % (`GET .../dashboard` de cada uma, carregado depois da lista).
- **Modais** (`ui.openModal`) pra formulários grandes (lançar estoque, print, produção, editar prédio).
- **Cards de prédio** agrupados (por tipo — padrão —, tipo+upgrade, local, local+tipo;
  `localStorage["buildingGrouping"]`). Grade `repeat(auto-fill, minmax(280px, 1fr))` sem `items-start`,
  card `flex flex-col h-full`, rodapé `mt-auto`. **Nada de `overflow-hidden` no card inteiro** (já cortou
  conteúdo calado); toda linha de texto com `min-w-0`/`truncate`. Arrastar ⠿ reordena só dentro do
  grupo: soltar num card toma o lugar dele (pra frente cai depois, pra trás cai antes); espaço vazio
  manda pro fim.
- **Metas** (`targets.js`): tabela por facility, ordenada pelo mais longe da meta; busca no catálogo
  inteiro; aceita `3k`, `1,5k`; líquido em litros. `GET/PUT /api/facilities/{id}/targets`.
- **Painel do item** (`itemPanel.js`): apelido (global) + origem de escolha única, gravada por facility
  (`PUT /api/facilities/{id}/item-origins`).
- **Histórico**: relatórios com "Excluir".
- **Aparência** (Configurações, `web/js/theme.js`, `localStorage["theme"]`, só naquele navegador): o `tailwind.config` aponta toda cor usada (`zinc` = neutro, `emerald` = destaque, mais red/amber/sky/indigo) pra variáveis CSS `--c-<cor>-<tom>`; um tema só troca as variáveis. Temas prontos (**Colonial** = padrão, verde-oliva; **Clássico** = Tailwind original zinc/emerald) + cor de destaque, tom do fundo, claro/escuro, fonte dos títulos ("Militar" = Saira Condensed do Google Fonts, cai pra fonte do texto offline; h1/h2/`.font-display` usam `--display-font`), fonte e tamanho do texto; "código do tema" (JSON sanitizado) pra compartilhar. Por isso: **usar só essas famílias de cor nas telas** (cor fora delas não acompanha o tema), nada de `text-white` em fundo neutro (some no claro) e cor em canvas/estilo inline via `theme.rgb("emerald", 500)`. No claro, o neutro é por papel (950 = página, 900 = card), os tons 300/400 coloridos escurecem (texto) e 800-950 clareiam (fundos), e ícones do jogo ganham contorno escuro (`style.css`).
- **Dashboard** (`dashboard.js`, `projection.py`; rota `#/facilities/<id>/dashboard`, o antigo `/live`
  ainda abre): estoque projetado supondo que as filas rodaram sem parar desde o último lançamento de cada
  prédio (só rodadas completas; para quando um insumo acaba). **Nunca é gravado** — conta feita na leitura,
  a cada 30s; o próximo lançamento real zera a projeção. Mostra resumo (filas rodando/paradas, o que
  falta), Metas com %, horários com data quando não são de hoje, aviso em prédio com lançamento de mais
  de 24h, onde mais na facility tem o insumo que acabou (`missing_keys`) e as estações (MTS/RTS) com o
  estoque lançado.

## Painel no Discord por webhook (`discord_dashboard.py`)

Sem bot: o webhook posta uma mensagem e depois só a **edita**. Configurado por facility (caixa "📣 No
Discord" da aba Dashboard; `facility_webhooks`). Único processo em segundo plano do app: tarefa asyncio
no `lifespan` que a cada 60s edita a mensagem de cada facility com webhook (pula webhook enviado há
menos de 55s). Contagens usam `<t:unix:R>`, que o Discord redesenha sozinho. PATCH 404 → posta outra;
"Parar" apaga a mensagem; erro vai pra `last_error`, nunca derruba o laço. Tópico opcional
(`thread_id`, `?thread_id=` em toda chamada). Texto no idioma da interface, nomes no do catálogo. Embed
mostra o mesmo que a aba (resumo, Metas com %, filas privadas, aviso de lançamento antigo, onde mais tem o insumo que
acabou, estações com estoque); cor verde = tudo rodando, âmbar = algo parado, vermelho = nada rodando.
Passou de ~5800 caracteres → tira primeiro as estações, depois as linhas de estoque; máx. 21 prédios. Só aceita URL
`https://discord.com/api/webhooks/...` (e ptb/canary/discordapp).

## Modo web (`auth.py`, `routers/auth.py`)

Desligado por padrão; liga com `DISCORD_CLIENT_ID` (env ou `.env`; env real vence). Ligado faltando
`DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`, `DISCORD_GUILD_ID`, `DISCORD_ALLOWED_ROLE_IDS` ou
`SESSION_SECRET` → **não sobe** (meio configurado poderia deixar todos entrarem).
- OAuth2 authorization code, scopes `identify guilds.members.read`; cargo checado com o token do próprio
  usuário em `GET /users/@me/guilds/{guild}/member` — **sem bot**, e o app do Discord não precisa estar
  no servidor nem ser verificado.
- **Nenhum token do Discord é guardado:** usado no login (cargo, nome, avatar) e **revogado na hora**.
  Cargo conferido só no login; sessão (cookie assinado, `https_only` com redirect https) vale 7 dias a
  partir do `login_at` (`auth.SESSION_SECONDS`). `access_token`/`refresh_token` em `users` ficam vazios.
- `auth.gate`: todo `/api/*` e `/uploads/*` exige sessão (401); estáticos públicos; `/api/me` sempre
  responde. Janela "O que fica guardado" (`showPrivacy` em `app.js`) — manter em dia.
- **Facility privada/compartilhada:** compartilhada (padrão) = todos com o cargo veem e editam; privada =
  só o dono vê; só o dono exclui, troca a visibilidade, configura webhook ou **transfere** (sem volta;
  `PUT /api/facilities/{id}/owner`, lista de `GET /api/users`). Sem dono = de todos; quem marca como
  privada vira dono. Bloqueio no `auth.gate` (`_private_facility_blocked`, padrões em `_FACILITY_PATHS`):
  facility alheia privada responde 404. Rota nova com outro formato de caminho precisa entrar ali.
- Configurações (motor de captura, chave de API) são globais.

**Segurança mínima:**
- Segredos (URL do webhook, `app_settings`) criptografados no banco (`crypto.py`, Fernet, coluna
  `EncryptedText`); valor antigo em texto é criptografado uma vez + `VACUUM`; `PRAGMA secure_delete`.
  Chave: `FACILITY_LOG_SECRET_KEY` (recomendado no servidor, fora do volume de dados) ou
  `data/secret.key`. Perder a chave = esses segredos viram vazio.
- A API nunca devolve a URL do webhook (só "…abcd").
- Modo local só responde a este PC: pedido com cabeçalho de proxy ou de outra máquina leva 403
  (`FACILITY_LOG_ALLOW_OPEN=1` libera pra LAN). O Dockerfile define `FACILITY_LOG_REQUIRE_LOGIN=1`.
- Cabeçalhos `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`; compose publica só em
  `127.0.0.1`.
- **Content-Security-Policy** (`main.CSP`): script só do próprio site e do Tailwind CDN **com versão fixa** (`cdn.tailwindcss.com/3.4.17`), **nenhum `<script>` inline** (a config do Tailwind fica em `web/js/tailwind-config.js`), `connect-src` só o site e `localhost:*` (Ollama da pessoa). Recurso externo novo (fonte, imagem, API chamada pelo navegador) precisa entrar no CSP, senão o navegador bloqueia calado.
- **Upload de print** (`routers/images.py`): a imagem é decodificada (Pillow) e só PNG/JPEG/WEBP de verdade fica, salva com a extensão do formato real — nunca a do nome enviado (um `.html` disfarçado virava página do próprio site). Máx. 20 MB e 40 Mpx. `/uploads` só serve `.png/.jpg/.jpeg/.webp` (`ImageOnlyStaticFiles`). `.sav` lido no máximo até `MAX_SAVE_BYTES`.
- **Configurações são de todos com o cargo**: mudar `api_base_url` ou `api_kind` sem digitar a chave de novo **apaga a chave salva** (senão qualquer membro mandava a chave do dono pra outro endereço); endereços só `http(s)://`.
- **Container sem root**: `docker-entrypoint.sh` entra como root só pra dar `/data` ao usuário `app` (uid/gid 1000) e roda o app com `setpriv`; compose com `no-new-privileges` e só as capabilities `CHOWN`/`SETUID`/`SETGID` (o processo do app fica sem nenhuma). Comando dentro do container que escreve em `/data` (backup) vai com `docker compose exec -u app` — o root de lá não tem permissão nos arquivos.
- Conferir CVEs: `pip-audit` (local e com o `pip freeze` do container), OSV pro `Cargo.lock` do parser e grype/trivy na imagem publicada.

**Deploy:**
1. PC + Cloudflare Tunnel (`.env` + `cloudflared` → `http://127.0.0.1:8000`); única opção em que a IA
   local funciona pra quem acessa pela web.
2. Docker: `docker compose up -d` usa a imagem `ghcr.io/rlanak/facility-log` (publicada pelo
   workflow `.github/workflows/docker-image.yml` só quando uma tag `vX.Y.Z` é enviada; só amd64). Build
   local: `docker build -t ghcr.io/rlanak/facility-log:latest .`. O Dockerfile compila o parser num
   estágio Rust; dados em `./data-docker`
   via `FACILITY_LOG_DATA_DIR` (nunca sobre `/app/data`, que esconderia o catálogo).
3. Sem abrir porta: opção 2 numa VM pequena (2 vCPU / 2 GB) + **Tailscale Funnel**
   (`sudo tailscale funnel --bg 8000`) — HTTPS e endereço `*.ts.net` fixos, grátis. Isolar com tag na
   VM, sem ela como origem de nenhuma regra da política do Tailscale, e só ela com o atributo `funnel`.

## Pegadinhas de desenvolvimento

- Dois uvicorn na porta 8000 (um de terminal, outro de preview) fazem requisição bater no processo
  velho; `--reload` às vezes não pega edição. Antes de concluir "não funcionou", reiniciar com um
  processo só.
- No navegador de preview, navegar pra mesma hash reaproveita estado JS antigo — abrir aba nova.
- `prompt()`/`confirm()` nativos não são automatizáveis: sobrescrever `window.prompt`/`window.confirm`
  antes de clicar.

## Em aberto

- Captura com mod: 120mm confundido com 300mm; níveis de Assembly Materials sem exemplo dependem do
  aviso "confira".
- Ponto decimal perdido no OCR ("1.4k" → "14k") — por isso nada salva sem confirmação.
- Captura por API de nuvem não testada com chave real.
- Receita ambígua sem nenhuma ativa pode não bater com a escolha real do jogador.
