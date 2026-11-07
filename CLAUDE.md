# facility-log — contexto do projeto

> Este arquivo existe pra qualquer sessão nova do Claude Code (ou o próprio autor) conseguir
> retomar o trabalho aqui sem depender do histórico de chat. Mantenha atualizado conforme o
> projeto evolui — é a fonte de verdade, não o histórico de conversas.

## ⚠️ Repositório público — leia isso primeiro

Projeto pessoal (`github.com/rlanak/facility-log`), **público** desde 07/11/2026. Este
arquivo é versionado: só entra aqui o que pode ser lido por qualquer um. Contexto pessoal, onde o app
está rodando, IDs do Discord, nomes do regimento e detalhes de infra ficam no **`CLAUDE.local.md`**
(gitignored, existe só no PC do autor — leia ele também, se existir). Commits sempre com o e-mail
noreply do GitHub, nunca um e-mail pessoal ou de trabalho.

## O que é / por quê

App 100% local que transforma prints do painel "STOCKPILE" do jogo **Foxhole** em relatório de
estoque formatado em Markdown, pronto pra colar no Discord — com recomendação de foco de farm.
O autor usa pra acompanhar o estoque das facilities do regimento dele sem fazer isso à mão.

É o **app único** dos projetos Foxhole do autor (decisão de 31/10/2026): o `foxhole-msupps-tray`
e todo o acompanhamento de mSupps/túneis foram **aposentados de vez** — não reintroduzir. Do
ecossistema antigo só sobrou o parser do save, movido pra `tools/save-parser/` (os repos
`foxhole-msupps-parser` e `foxhole-msupps-tray` foram apagados), usado como leitor do save do
jogo — ver seção "Leitura do save do jogo".

**Restrições que não mudam** (revistas em 31/10/2026 — antes era "100% local, nada de IA paga"):
- **Rodar local continua sendo o padrão e funcionando sozinho:** um comando (ou o atalho da bandeja), sem
  conta, sem login, sem serviço pago, sem IA. Web (login Discord) e IA (local ou por API) são
  **opcionais**, ligados por configuração — nunca podem virar pré-requisito pro modo local.
- IA paga só com a chave do próprio usuário e escolhida explicitamente por ele em Configurações —
  nunca padrão, nunca chamada sem ele ter escolhido.
- Valor lido por OCR, IA ou save **nunca** salva sozinho — sempre pré-preenchido num campo editável
  que o usuário confirma antes de salvar.
- Limite de 2000 caracteres do Discord tem que ser respeitado ao gerar relatório (split em partes
  numeradas, sem cortar um bloco Markdown no meio).

## Como rodar

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe scripts/build_save_parser.py   # leitor do save (precisa de cargo); opcional
.venv/Scripts/python.exe scripts/create_shortcut.py     # atalho "Facility Log" na área de trabalho
.venv/Scripts/python.exe run.py                         # modo dev (console + auto-reload)
```

Abre em `http://localhost:8000`. Um processo só (uvicorn) serve API + frontend estático juntos. No
dia a dia, usar o atalho (modo bandeja, sem janela preta) — ver seção "Uso no dia a dia".

**Leitura automática de prints:** o padrão é o RapidOCR (vem no `requirements.txt`, nada a
instalar). Tesseract (`winget install UB-Mannheim.TesseractOCR`) e IA local (Ollama) são opcionais —
ver seção "Captura". OpenCV (`opencv-python-headless` + `numpy`) faz a detecção de itens.

**Modo web (opcional):** um `.env` na pasta do app com as variáveis do `.env.example` liga o login
pelo Discord — ver seção "Modo web". Sem `.env`, roda local como sempre.

## Uso no dia a dia — ícone na bandeja, sem janela preta (`run.py --tray`)

Desde 31/10/2026 o jeito normal de usar é o atalho **"Facility Log"** na área de trabalho, criado
por `scripts/create_shortcut.py` (rodar de novo se a pasta do projeto mudar). Ele roda
`.venv\Scripts\pythonw.exe run.py --tray`: **sem janela de console**, com um ícone na bandeja do
Windows (perto do relógio) — clique duplo/"Abrir Facility Log" abre o navegador, "Ver log" abre
`data/facility_log.log`, "Sair" desliga o servidor. Abrir o atalho com o app já rodando só abre a
página (não sobe um segundo servidor). `python run.py` (sem `--tray`) continua sendo o modo dev, com
console e auto-reload.

Pontos não óbvios:
- `pythonw` não tem console: `sys.stdout`/`stderr` são `None` e o logging do uvicorn quebraria —
  por isso o modo bandeja redireciona os dois pro `data/facility_log.log` antes de subir o servidor.
  Erro que antes aparecia na janela preta agora está nesse arquivo.
- O ícone (bandeja e atalho) é desenhado com Pillow em `run._tray_image()`; o `.ico` do atalho é
  gerado em `data/facility_log.ico` (gitignored).
- Tudo roda do código-fonte: atualizar é só editar/`git pull` e reabrir pelo atalho. Não tem
  build.

**O `.exe` (PyInstaller) foi aposentado nessa mesma data** a pedido do autor: dava trabalho
recompilar a cada mudança e deixava a janela de console aberta. Foram removidos `facility_log.spec`,
`requirements-build.txt`, `scripts/prepare_tesseract_vendor.py`, o Tesseract embutido e o modo
"frozen" de `app/paths.py` (que agora só tem `APP_DIR`, a pasta do projeto). Pra outros membros do
regimento o caminho é o **modo web** (seção abaixo) — ninguém precisa instalar nada. Se um dia
quiser o `.exe` de volta, está no histórico do git (commit que adicionou PyInstaller).

**Leitor do save (Rust):** `scripts/build_save_parser.py` roda `cargo build --release` em
`tools/save-parser/` — precisa de `cargo` (rustup). Só "Importar do save" depende dele; o resto do
app funciona sem.

## Modo web — login pelo Discord (`app/auth.py`, `app/routers/auth.py`)

Pedido do autor (31/10/2026): acessar pela web, login pelo Discord, só quem tem um cargo no
servidor do regimento. **Desligado por padrão** — liga quando `DISCORD_CLIENT_ID` existe no ambiente
(ou num `.env` ao lado do `run.py`, carregado por `app/envfile.py`; variável de ambiente real
vence). Se ligar faltando alguma das outras (`DISCORD_CLIENT_SECRET`, `DISCORD_REDIRECT_URI`,
`DISCORD_GUILD_ID`, `DISCORD_ALLOWED_ROLE_IDS`, `SESSION_SECRET`), o app **não sobe** (de propósito:
meio configurado poderia deixar todo mundo entrar).

- OAuth2 authorization code, scopes `identify guilds.members.read`. O cargo é checado com o token do
  próprio usuário em `GET /users/@me/guilds/{guild}/member` — **não precisa de bot**.
- Sessão em cookie assinado (`SessionMiddleware` + `itsdangerous`), `https_only` quando o redirect é
  https. Vale **7 dias a partir do login** (`auth.SESSION_SECONDS`, conferido pelo `login_at` dentro do
  cookie — o max-age do cookie desliza a cada resposta, o `login_at` não).
- **Nenhum token do Discord é guardado** (03/11/2026, pedido do autor: quem usa não precisa confiar
  a conta Discord a quem administra o servidor). No login o token serve pra conferir o cargo e pegar
  nome/avatar, e é **revogado na hora** (`auth.revoke_token`). `users` guarda só ID, nome e avatar
  (`access_token`/`refresh_token` ficaram como colunas sempre vazias; a migração apaga os antigos).
- `auth.gate`: com login ligado, todo `/api/*` e `/uploads/*` exige sessão (401 senão); arquivos
  estáticos (o SPA) ficam públicos pra tela de login carregar; `/api/me` responde sempre.
- Cargo conferido **só no login**: quem perde o cargo no Discord sai em até 7 dias (quando a sessão
  vence). Antes era rechecado a cada 6h com o token guardado — trocado pela decisão acima.
- **"O que fica guardado"**: janela aberta pelo link na tela de login e pelo 🔒 ao lado do nome no topo
  (`showPrivacy` em `app.js`), explicando o que o servidor guarda e quem consegue ver. Manter em dia se
  mudar o que é guardado. A caixa do webhook também diz que quem administra o servidor consegue ler a
  URL e que o controle é de quem criou o webhook no Discord.
- Autoria: `stock_entries.created_by_id` e `reports.created_by_id` (NULL no modo local e em dado
  antigo). O card mostra "lançado por X" no tooltip; o Histórico mostra "por X".
- "Importar do save" no modo web: o save "deste PC" seria o do **servidor** — só é oferecido pra um
  navegador na própria máquina (`auth.is_local_request`: loopback **e** sem cabeçalho de proxy,
  porque o cloudflared também conecta via localhost). Usuário remoto envia o próprio `.sav`.
- Configurações (motor de captura, chave de API) são globais: qualquer um com o cargo muda.
- **Facility privada ou compartilhada** (03/11/2026): `facilities.owner_id` (quem
  criou, no modo web) + `facilities.private`. Decisões do autor: **compartilhada** (padrão) = todos com o
  cargo veem e editam; **privada** = só o dono vê; só o dono exclui ou troca privada/compartilhada.
  Facility sem dono (criada no modo local ou antes disso) é de todos, e quem marcar como privada vira o
  dono. O bloqueio fica no `auth.gate` (`_private_facility_blocked`): todo `/api/facilities/<id>`,
  `/api/buildings/<id>`, `/api/images/<id>`, `/api/reports/<id>` e `?facility_id=` de uma privada alheia
  responde 404 (igual a facility inexistente) — rota nova com esse formato já fica coberta; rota nova
  com outro formato precisa entrar em `_FACILITY_PATHS`. `GET /api/facilities` filtra a lista. No modo
  local (sem login) nada disso aparece nem vale. O webhook do Discord de uma privada continua postando
  no canal (é escolha do dono). Arquivos em `/uploads/` não são filtrados (nome é UUID aleatório).
  Testado com dois usuários simulados (`TestClient` + `_load_user` trocado) e as telas no navegador.
- **Transferir a facility** (pedido do autor, mesmo dia): botão "Transferir" (só pro dono, modo web) →
  escolhe alguém da lista de quem já fez login (`GET /api/users`) → `PUT /api/facilities/<id>/owner`.
  É **sem volta**: o antigo dono perde excluir/privada/webhook e só volta a ser dono se alguém passar de
  volta (pedir de volta não existe). Privada vai junto: o antigo dono deixa de ver. A pessoa precisa ter
  entrado no app pelo menos uma vez pra aparecer na lista.

**Deploy — duas opções, as duas prontas:**
1. **PC do autor + Cloudflare Tunnel** (grátis, só online com o PC ligado): `.env` ao lado do
   `run.py` (rodando pelo atalho da bandeja), `cloudflared tunnel` apontando pra `http://127.0.0.1:8000`,
   `DISCORD_REDIRECT_URI=https://<domínio do túnel>/auth/callback`. Única opção em que a IA local
   (GPU dele) funciona pra quem acessa pela web.
2. **VPS/nuvem com Docker**: `docker compose up -d --build` nesta pasta (o build compila
   `tools/save-parser` pra Linux num estágio Rust; dados em `./data-docker` via
   `FACILITY_LOG_DATA_DIR`, nunca sobre `/app/data`, que esconderia o catálogo). Lá não tem GPU:
   captura por RapidOCR ou API.

Pré-requisito que só o dono do app pode fazer: criar a aplicação no Discord Developer Portal (client
id/secret, cadastrar a redirect URI) e pegar o ID do servidor e do(s) cargo(s).

**Publicar sem abrir porta (o que está em uso, detalhes no `CLAUDE.local.md`):** opção 2 numa VM
pequena (2 vCPU / 2 GB bastam) + **Tailscale Funnel** (`sudo tailscale funnel --bg 8000`): HTTPS e
endereço `*.ts.net` fixos, grátis, sem domínio, sem porta aberta nem proxy reverso. Quem acessa não
instala nada. Pra isolar: tag na VM e política do Tailscale em que ela não é origem de nenhuma regra
(não alcança os outros aparelhos) e só ela tem o atributo `funnel`. O app do Discord não precisa de bot
nem de verificação (verificação só é exigida de bot em 100+ servidores) e não precisa estar no
servidor do regimento: quem entra é decidido só por `DISCORD_GUILD_ID` + `DISCORD_ALLOWED_ROLE_IDS`.
`scripts/oracle_create_vm.py` ficou de registro de uma tentativa na Oracle Always Free (A1 sem
capacidade em São Paulo).

**Testado:** fluxo inteiro com as chamadas do Discord simuladas (`TestClient` + monkeypatch: sem
login → 401, sem cargo → recusado (token revogado igual), com cargo → entra sem guardar token,
autoria gravada, sessão de 8 dias → 401, remoto não lê o save do servidor) e as duas telas no navegador. **Não testado:** login com um app
Discord de verdade e o `docker build` (Docker não está instalado nesta máquina).

## Segurança mínima (03/11/2026)

Pedido do autor: sem segurança rigorosa, mas um mínimo pra entrada e pros dados sensíveis (o webhook
do Discord posta qualquer coisa no canal, inclusive @everyone).
- **Segredos criptografados no banco** (`app/crypto.py`, Fernet, coluna `EncryptedText`): URL do
  webhook e `app_settings` (tem a chave de API). Tokens do Discord nem são mais guardados (ver "Modo
  web"). Valor antigo em texto puro
  é criptografado uma vez no `apply_migrations()`, seguido de `VACUUM`; `PRAGMA secure_delete` zera o
  que é sobrescrito. Chave: `FACILITY_LOG_SECRET_KEY` (env/.env — recomendado na VPS, fora do volume de
  dados) senão `data/secret.key` (gitignored, criado sozinho). As duas são tentadas na leitura. **Perder
  a chave = perder esses segredos** (viram vazio, não quebra): webhook e chave de API teriam de ser
  colados de novo, usuários logam de novo. Não é cofre (a chave fica na mesma máquina): protege uma
  cópia/backup do `.db` sozinho.
- **Webhook só o dono configura** (salvar, trocar, parar); os outros veem só "…abcd" e podem "Enviar
  agora". A API nunca devolve a URL.
- **Nunca aberto sem login por acidente:** modo local (sem login) só responde a este PC — pedido vindo
  de túnel/proxy (cabeçalho de encaminhamento) ou de outra máquina leva 403 (`FACILITY_LOG_ALLOW_OPEN=1`
  libera, de propósito, pra LAN). O Dockerfile define `FACILITY_LOG_REQUIRE_LOGIN=1`: sem o login do
  Discord configurado o app nem sobe no servidor.
- Cabeçalhos: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`.
  Já existiam: cookie de sessão assinado e `httponly` (https-only com redirect https), `state` no OAuth,
  `docker-compose` publica só em `127.0.0.1`.
- Testado numa cópia do banco: segredos não aparecem em texto no arquivo, app lê de volta, não-dono
  leva 403, túnel/outra máquina levam 403 em modo local, `REQUIRE_LOGIN` recusa subir.

## Stack

Python + FastAPI + SQLite (SQLAlchemy) no backend. Frontend é HTML/JS puro + Tailwind via CDN
(zero build step) — o próprio FastAPI serve `web/` como static files.

## Estrutura de pastas

```
app/
  main.py            — monta a app, serve static files sem cache (NoCacheStaticFiles), liga o login se configurado
  auth.py            — login Discord opcional (OAuth2, checagem de cargo, gate de /api)
  envfile.py         — carrega .env da pasta do app
  database.py         — engine SQLite + apply_migrations() (ALTER TABLE manual, sem framework)
  models.py / schemas.py / crud.py
  routers/
    facilities.py, buildings.py, resources.py, stock.py, reports.py, foxhole.py, images.py,
    save.py (importar do save), settings.py (motor de captura), auth.py (login Discord)
  services/
    number_parser.py       — interpreta "25.7k", "1,8k", "32000"
    report_generator.py    — gera o Markdown do relatório + Recomendação de Farm/Discord
    material_chain.py       — resolvedor recursivo de cadeia de produção pra bater uma Meta
                               (ver seção "Recomendação de Farm virou cálculo de cadeia")
    ocr_service.py          — wrapper do Tesseract (pytesseract), fallback gracioso
    icon_match_service.py   — detecção automática de item via template matching (ver seção OCR)
    production.py           — estimativa de ciclos/tempo de produção por prédio
    foxhole_data.py          — carrega data/foxhole/*.json, resolve nomes localizados
    errors_i18n.py           — mensagens de erro do backend em pt-BR/en-US
    save_reader.py           — acha/recebe o save do jogo + chama o CLI tools/save-parser (--json)
    capture/                 — quem lê o número dos prints: RapidOCR, Ollama, API ou Tesseract
    projection.py            — estimativa "Ao vivo" (estoque projetado pelas filas)
    discord_dashboard.py     — painel no Discord por webhook + o laço de 60s
web/
  index.html
  css/style.css
  js/
    api.js   — fetch wrapper, sempre anexa ?lang=X&catalog_lang=Y
    ui.js    — toast, escapeHtml, el() (helper de DOM), openModal() (ver seção Modais)
    app.js   — hash router + wiring dos dois seletores de idioma
    i18n.js  — strings de interface (pt-BR/en-US) + resolução de nomes do catálogo
    views/
      facilities.js, facilityDetail.js, targets.js (aba Metas), itemPanel.js (apelido/origem do item),
      print.js, report.js, saveImport.js, settings.js
data/
  facility_log.db, uploads/   — gitignored (dados reais do usuário)
  foxhole/resources.json, building_types.json   — catálogo Foxhole, versionado no git
tools/save-parser/   — leitor do save do jogo em Rust (CLI, `--json`), ver "Leitura do save do jogo"
print/   — prints reais pra medir a captura (mod/, vanilla/, truth.json, boxes.json), gitignored (nomes reais)
FacilityIcons/   — pasta de trabalho onde o autor larga ícones novos antes de eu copiar pra
                    web/assets/foxhole/structures/ (pode ser esvaziada a qualquer momento)
```

## Modelo de dados (SQLite)

- `resources` — catálogo global compartilhado entre facilities: `name` (nome-padrão em inglês,
  **nunca muda** depois de criado), `nickname` (apelido opcional, sobrepõe o nome na exibição),
  `resource_def_key` (link pro catálogo Foxhole), `target_max` (**legado, não é mais lido** — a Meta
  virou por facility, ver `facility_targets`), `farmable` (bool — só recursos
  que você farma no mundo; desmarcado = produzido/intermediário), `imported` (bool — recurso
  obtido de fora, de um aliado/coalizão, em vez de farmado ou produzido localmente; tem
  prioridade sobre `farmable` se os dois estiverem marcados). Os dois flags controlam a cadeia
  de recomendação — ver seção "Recomendação de Farm virou cálculo de cadeia" abaixo.
  `unlimited` (bool, origem "Abundante (∞)" no painel do item — pedido do autor em 01/11/2026):
  recurso que **sobra** na facility, ex: Água (poucas filas de bomba já enchem e transbordam).
  Conta como **sempre disponível**: nunca limita a estimativa de ciclos (`production.estimate_production`
  ignora o insumo, então nunca aparece "Faltando: Água"), a cadeia da Meta não pede produzir/farmar
  (`material_chain.resolve` retorna na hora), e sai do relatório inteiro (`generate_report` filtra
  as entradas: sem linha de estoque, de tanque, de total nem Meta). O card do prédio esconde o
  tanque dele. Prioridade sobre `farmable`/`imported`. Padrão do catálogo: `"unlimited": true` só na
  Água (`resources.json`; aplicado uma vez nos recursos já existentes quando a coluna foi criada).
  O autor comentou que Óleo Pesado também costuma sobrar e só o Petróleo Enriquecido fica escasso —
  marcar Óleo Pesado (ou outros) é decisão dele, no painel do item. `crud.unlimited_resource_keys()` dá o
  conjunto de chaves (linha do usuário vence o padrão do catálogo).
- `facilities` — nome, timestamps.
- `facility_targets` — a **Meta** de um recurso numa facility (`facility_id`, `resource_id`,
  `target_max`, único por par). Ver "Metas por facility e fim do Catálogo de Recursos" abaixo.
- `buildings` — pertence a uma facility: `name`, `building_type_key` (link pro catálogo),
  `production_slots` (JSON: lista de `{recipe_key, queue_count}`, ver seção Produção),
  `position` (ordem no grid, drag-to-reorder).
  `upgrade` (nome do módulo instalado, ex: `"Forge Upgrade"`; NULL = só base) — ver "Upgrade do
  prédio" abaixo.
  `location` (texto livre, onde o prédio fica dentro da facility — ex: "Norte", "Porto"; NULL = sem
  local) — ver "Local do prédio" abaixo.
- `stock_entries` — **log append-only**, nunca dá update. "Estoque atual" de um
  prédio+recurso+`storage` = a linha mais recente daquela combinação. É isso que permite comparar
  evolução do estoque sem tabela de histórico separada. `storage` é `"normal"` (estoque em
  caixa/prateleira, sem limite — o padrão, usado por todo recurso) ou `"tank"` (tanque de líquido,
  capado em 5000L) — ver seção "Tanques de líquido". **Exclusão é diferente de update:**
  `DELETE /api/buildings/{id}/stock/{resource_id}?storage=X` (`crud.delete_stock_entries()`)
  apaga **todo** o histórico daquele resource+storage naquele prédio — não é "voltar pro valor
  anterior" (isso seria só logar um novo valor), é "eu não devia ter lançado isso aqui" (recurso
  errado, prédio errado, teste). Cada linha no card do prédio (estoque normal e tanque) tem um
  "✕" pra isso. Não afeta relatórios já gerados (o snapshot é congelado à parte,
  `Report.stock_snapshot`).
- `upload_images` — prints enviados (building_id + file_path).
- `reports` — histórico de relatórios gerados: facility_id, generated_at, markdown_content
  (alimenta os blocos in-app: Cabeçalho/Estoque Atual/Recomendação), stock_snapshot (JSON —
  histórico continua correto mesmo se um recurso/prédio for renomeado ou apagado depois),
  discord_content (parágrafos usados pra montar as partes do Discord — separado do
  markdown_content porque a versão Discord é consolidada/diferente, ver seção Discord), lang
  (idioma em que o relatório foi gerado, pra reconstruir corretamente o rótulo "Parte X/Y" ao
  reabrir no Histórico).

## Catálogo Foxhole (`data/foxhole/*.json`)

168 recursos (todos os itens de inventário Colonial/neutros do jogo), 8 prédios de produção (Coal Refinery, Materials Factory, Metalworks Factory, Oil
Refinery, Ammunition Factory, Infantry Kit Factory, Aircraft Maintenance Factory, Concrete Mixer) +
2 de armazenamento (Material Transfer Station e Resource Transfer Station — esta guarda matéria-prima
solta, 15 slots/30.000, codename `FacilityTransferResource`, ícone `MaterialTransferStationIcon.png` da wiki — o nome engana: o da MTS é `FacilityResourceTransfer3Icon.png`; as duas com
`queue_slots: 0`, `recipes: []`, `storage: true`),
gerados via pesquisa na wiki (`scripts/generate_foxhole_seed.py`, `scripts/download_foxhole_icons*.py`).

**O que cada estação aceita** (`accepts` em `building_types.json`, copiado da tabela "Storage" da
página de cada uma na wiki em 03/11/2026, itens Warden de fora): **MTS** = itens grandes (armas e
munição pesada, utilitários grandes, Assembly Materials, peças de avião…) + Construction Materials, 54
itens, até 1000 no total; **RTS** = só recurso solto (Salvage, Coal, Components, Damaged Components,
Sulfur, Gravel, Explosive Powder, Heavy Explosive Powder, Coke, Rare Metal — **não** aceita Iron,
Copper nem Aluminum), até 30.000. O "Lançar estoque" de uma estação mostra só esses itens (prédio de
produção continua mostrando os itens das receitas); lista com mais de 12 itens ganha um campo de
busca (casa nome em pt e en). Não há trava no backend — import do save/print grava o que vier.

`codename` (recursos e prédios) = nome interno do jogo, o que o save guarda (ex: Construction
Materials = `FacilityMaterials1`, Coke = `FacilityCoal1`, Salvage = `Metal`, MTS =
`FacilityTransferMaterial`). Dos recursos, preenchido por `scripts/map_resource_codenames.py` a partir
do catálogo extraído do jogo pelo projeto FIR (`github.com/GICodeWarrior/fir`, pasta
`foxhole/airborne-63/catalog.json`), casando por nome em inglês e depois por ícone. 102/103 casaram;
Naval Buoy não existe nesse catálogo (item mais novo que a v1.63). Rodar de novo quando o FIR publicar
pasta de guerra mais nova. O da MTS veio do infobox da wiki (`codename = FacilityTransferMaterial`).

Os 65 itens que faltavam (armas leves, utilitários, médicos, Basic/Refined Materials, minérios…) foram
importados em 02/11/2026 por `scripts/import_fir_items.py`, do mesmo catálogo do FIR: só itens com
`ItemCategory` (inventário — veículos e estruturas ficaram de fora) e não exclusivos de Warden. Nome
em inglês nas duas línguas (o FIR não tem pt; o jogador pode pôr apelido), `farmable` só nos minérios
(Iron, Copper, Aluminum), ícone do FIR (`icons/<CodeName>.png`). Os ícones do FIR vêm **sem
transparência** (desenho sobre preto) — foram convertidos pra RGBA (alfa = canal mais claro), porque
o detector (`_white_template`) lê o canal alfa e a lista ficaria com quadrados pretos. Se rodar o
script de novo com item novo, converter o ícone do mesmo jeito. Todo item ganhou `category`
(`small_arms`, `heavy_ammo`, `supplies`…; sem categoria = material de facility), usada pra agrupar a
busca da aba Metas. Medido depois da importação (`benchmark_capture.py rapidocr`): mesmos acertos de
antes (36/47 com mod, 25/29 sem mod); 2 falsos positivos novos (Buckhorn/baioneta) em prints com mod.

**Regra dura: só Colonial.** Itens exclusivos de Warden foram removidos (5 recursos removidos
depois de auditoria via `faction` field da wiki — ver `data/foxhole/resources.json`). Itens
compartilhados entre as duas facções ficam. Conferido de novo em 02/11/2026, depois de importar os
itens do FIR: os 168 itens são Colonial ou das duas facções. Única divergência: o FIR (v1.63) marca a
Quillback Torpedo como Warden, mas a wiki atual diz "Both" — **a wiki vale** (é mais nova). O
`import_fir_items.py` já pula todo item com `FactionVariant` Warden. Pra achar ícone de item novo: usar a MediaWiki API
(`action=parse&prop=wikitext`), não fazer scraping de página renderizada (rate-limita rápido) —
nunca adivinhar o nome do arquivo pelo nome do item.

Cada recurso tem `name: {en, pt}`; cada prédio tem `name_en`/`name_pt`. O `name` salvo no banco
**nunca muda** (fica sempre o padrão em inglês) — a exibição localizada é resolvida
dinamicamente (ver seção i18n abaixo), nunca gravada no dado do usuário.

**Receita com insumo/produto líquido: o `qty` no JSON é sempre em Litros, nunca em unidades.**
A wiki mostra cada receita como `"75 x Coke"` (sólido, contagem de unidade) ou `"66L of Heavy
Oil"` (líquido, valor em **Litros** — confirmado célula a célula em
`foxhole.wiki.gg/wiki/Metalworks_Factory`, `Materials_Factory`, `Coal_Refinery`, `Oil_Refinery`,
v1.66). O catálogo foi montado copiando o número mostrado, então todo `qty` de um insumo/produto
líquido numa receita É o valor em Litros — **nunca** leia esse `qty` diretamente como quantidade
de unidades. `foxhole_data.recipe_io_qty(io)` faz essa conversão (`qty / liters_per_unit` quando
o recurso é líquido) e é o único ponto que deveria ler `io["qty"]`/`io.get("qty")` de uma receita
pra fins de cálculo — `material_chain.py` e `production.py` já passam por ele; qualquer código
novo que leia uma receita (ex: um script de importação, uma nova rota) precisa fazer o mesmo, ou
vai reproduzir o bug de estoque de líquido computado ~50x maior que o correto (Água/Óleo/Petrol,
50L por unidade) ou ~30x (Óleo Pesado/Óleo Enriquecido, 30L por unidade) que foi encontrado e
corrigido numa auditoria — ver histórico do commit que adicionou esta nota.

**Auditoria das receitas (02/11/2026):** `scripts/audit_recipes_wiki.py` compara cada receita de
`building_types.json` com a tabela da página do prédio na wiki (HTML renderizado via MediaWiki API —
o wikitext usa templates e não dá pra ler): tempo, quantidade de insumo e de produto ("10 of 15 x" =
10 caixas de 15). Achou e foi corrigido: **120mm e 94.5mm com a Heavy Explosive Powder trocada**
(120mm gasta 2, 94.5mm gasta 8 — o relatório pedia 4x mais pólvora pra Meta de 120mm) e as 4
receitas do Special-Issue Firearms Assembly montadas ao contrário (elas **convertem** uma caixa da
arma base na versão especial: 20 Dusk → 3 Dawn, 20 Catara → 3 Quickhatch, 20 Argenti → 5 KRR3-792
Auger, 15 Shrapnel Mortar → 15 Incendiary; o catálogo tinha a arma base como produto). Todos os
tempos batiam. Sobram 3 "não achados" só por grafia (Abisme AT-99 Mine, AP⧸RPG, ARC⧸RPG), conferidos
à mão. Rodar de novo depois de atualização do jogo.

## i18n — duas camadas independentes

Duas configurações de idioma **separadas**, cada uma com seu próprio seletor no header:

1. **Idioma da interface** (`localStorage["lang"]`) — textos de botão, labels, mensagens de erro.
2. **Idioma do catálogo** (`localStorage["catalogLang"]`) — nomes de prédio/recurso. Por padrão
   segue o idioma da interface até o usuário escolher explicitamente algo diferente (ex: quer a
   interface em pt-BR mas os nomes de item sempre em inglês, como é falado no jogo/Discord).

`web/js/api.js`'s `withLang()` anexa `?lang=X&catalog_lang=Y` em toda chamada automaticamente.
No backend, praticamente todo endpoint recebe os dois parâmetros — `lang` controla mensagens de
erro (`errors_i18n.err()`), `catalog_lang` controla `crud.resolve_resource_name()` /
`resolve_building_name()` / `foxhole_data.resource_display_name()` / `building_display_name()`.
Isso vale também dentro do relatório gerado (`report_generator.py`) e da estimativa de produção
(`production.py`) — ambos misturam texto de interface com nomes de catálogo na mesma string, por
isso recebem os dois idiomas separadamente.

**Um relatório já gerado é um snapshot congelado** — guarda o idioma escolhido no momento da
geração; visualizar depois no Histórico sempre mostra o mesmo idioma, só o chrome da tela de
Histórico (labels, "expandir") segue o idioma atual da interface.

Pra adicionar um idioma novo: terceira chave em `STRINGS` (`i18n.js`), terceiro `<option>` nos
dois `<select>` do header, terceira chave em `_STRINGS` (`report_generator.py` e
`errors_i18n.py`), terceiro mapeamento em `LANG_CODES` (`foxhole_data.py`), e tradução de
`resources.json`/`building_types.json` (168 + 8 entradas) — essa parte é o grosso do trabalho.

## Produção multi-fila

`Building.production_slots` é uma lista de `{recipe_key, queue_count}` — um prédio roda **várias
receitas diferentes ao mesmo tempo**, até o limite `queue_slots` do tipo de prédio (ex: Materials
Factory tem 5 slots, pode rodar "3x Construction Materials + 2x Metal Beam" junto).

`production.estimate_building_slots()` **une** slots que repetem a mesma `recipe_key` (soma o
`queue_count`) antes de estimar — se o usuário adicionar a mesma receita em duas linhas do
formulário em vez de aumentar a quantidade de uma só, o card mostra uma linha "Nx" combinada, não
duas linhas "1x" separadas. O formulário de edição continua mostrando as linhas como o usuário
criou (não funde ali, só na exibição da estimativa).

Estimativa é "ballpark", não simulação precisa — cada slot é calculado contra o mesmo snapshot de
estoque atual; se duas receitas ativas competem pelo mesmo insumo, os números podem superestimar
o tempo de vida combinado. Decisão consciente (do autor: "não precisa ser preciso").

## Tanques de líquido

Água/Óleo/Petróleo/Óleo Pesado/Óleo Enriquecido têm `is_liquid: true` +
`liters_per_unit` em `resources.json`. Tanque tem cap fixo de **5000L** por líquido por prédio
(`foxhole_data.LIQUID_TANK_CAPACITY_LITERS`).

Quais líquidos aparecem como tanque **não é uma configuração separada** — é derivado das receitas
atualmente ativas em `production_slots` (`foxhole_data.active_liquid_keys()` /
`activeLiquidKeys()` no frontend).

**Tanque e caixa são duas quantidades independentes do mesmo líquido** (`StockEntry.storage`:
`"tank"` ou `"normal"`) — no jogo, quando o tanque de um prédio enche, a produção excedente passa
a empilhar em caixas normais, junto do resto do estoque. `crud.get_current_stock_for_building()`
agrupa a "última entrada" por `(resource_id, storage)`, não só por `resource_id`, então as duas
convivem sem uma sobrescrever a outra. O botão "+" do tanque sempre grava com `storage="tank"`; o
formulário normal de "Lançar estoque" grava com `storage="normal"` — e **inclui líquidos** (antes
excluía líquidos por completo do formulário normal, só o tanque conseguia registrar estoque
deles). O cap de 5000L só é validado quando `storage="tank"` — estoque de líquido em caixa não
tem limite, igual qualquer outro recurso.

Pra cálculo de produção (`crud.get_current_stock_by_resource_def()` e o `combined_stock` dentro de
`report_generator.build_building_paragraph()`), tanque + caixa são **somados** — uma receita pode
consumir de qualquer um dos dois, o app não distingue de onde exatamente o insumo veio.

O prompt de "+ adicionar" no tanque aceita **unidades (galões)** ou **litros com sufixo "L"**
(ex: "5000L" converte automaticamente pra unidades via `liters_per_unit` antes de salvar) — os
dois formatos funcionam, conversão feita client-side em `facilityDetail.js`.

**Cuidado com float na validação do cap:** o frontend arredonda a conversão L→unidades pra 2 casas
antes de mandar pro backend; se o backend comparar contra o cap sem arredondar do mesmo jeito, um
tanque exatamente cheio pode disparar falso-positivo de "não cabe" (166.67 arredondado > 166.666...
sem arredondar). `crud.add_stock_entries()` arredonda os dois lados pra 2 casas antes de comparar
— se mexer nessa validação de novo, manter esse cuidado.

Todo valor de líquido **exibido como texto no relatório** (Estoque Atual, Total da Facility,
Meta, Produção necessária/Farm/Importar, insumos/saídas/sobras de produção) é convertido pra
**Litros** via `report_generator._display_qty()` — inclusive estoque de caixa, que fica salvo em
unidades no banco mas nunca aparece em unidades no texto. Só a exibição converte; o valor salvo
continua em unidades (galões).

**Deliberadamente não modelado:** a mecânica exata de overflow automático (produção só vai pra
caixa depois que a tubulação/tanque enche de verdade) — o campo `storage` só permite *logar* as
duas quantidades separadamente à mão, não simula esse comportamento sozinho. Também não modela:
múltiplos tanques do mesmo líquido no mesmo prédio, cap do tanque limitando o cálculo de ciclos de
produção, Liquid Transfer Stations movendo líquido entre prédios.

## Recomendação de Farm virou cálculo de cadeia (`app/services/material_chain.py`)

A recomendação do relatório **não é mais** "top-3 recursos farmáveis com menos estoque". Agora,
pra cada recurso com uma Meta cadastrada **nesta facility** (`facility_targets`) e cujo estoque atual da
facility esteja abaixo dela, `material_chain.resolve_requirements()` percorre a árvore de receitas
**de trás pra frente** (do recurso final até os insumos) recursivamente, abatendo o estoque já
existente da facility em **cada nível** da cadeia (não só no topo), até chegar em folhas:

- Recurso marcado `farmable` → vira "🌾 Farm necessário" — reportado como está, **nunca**
  decomposto numa receita mesmo que uma exista tecnicamente (ex: Components tem uma receita de
  reciclagem de Damaged Components, mas se está marcado farmable o relatório sempre recomenda
  "farmar mais Components", não reciclar). Foi um pedido explícito do autor depois de ver a
  recomendação sugerir "Damaged Components" quando ele nem produz por reciclagem.
- Recurso marcado `imported` → vira "📦 Importar (produção externa)" — mesma lógica de folha, pro
  caso de o regimento importar um item pronto de um aliado/coalizão em vez de produzir
  localmente. `imported` tem prioridade sobre `farmable` se os dois estiverem marcados.
- Recurso sem receita conhecida no catálogo → também cai em "Farm" (fallback defensivo).
- Qualquer outro recurso → soma ciclos de produção em "🏭 Produção necessária" e recursa nos
  insumos da receita escolhida.

**De onde vem o estoque abatido (03/11/2026, pedido do autor — um prédio não usa o recurso de
outro):** o produto da Meta conta em **qualquer** prédio da facility (MTS inclusive). Já os
**insumos** de uma receita só abatem o estoque dos prédios que **rodam aquela receita**
(mesmo tipo + mesma receita nas filas — duas Fábricas de Munição fazendo 3C dividem; a que faz 120mm
não empresta pólvora pra de 3C). Receita que nenhum prédio roda ainda usa os prédios daquele tipo
sem nada em produção. **Estações de armazenamento (MTS, RTS — `storage: true`) são compartilhadas**
por toda receita: servem justamente pra guardar insumo e produto da facility (o próprio prédio é
usado primeiro, depois as estações). Estoque em outra fábrica **não** conta como insumo.
`resolve_requirements()` recebe `{building_id: {chave: qtd}}` + os prédios
(`material_chain._building_pools`). Os cards e o "Estoque Atual" já calculavam por prédio.

**Meta antiga incluía recursos não-farmáveis?** Não — a recomendação antiga excluía por completo
qualquer recurso com `farmable=False`, então uma Meta cadastrada num item produzido (ex: Assembly
Materials IV) nunca aparecia. Esse é o motivo de toda essa seção existir: o autor queria saber "o
que falta produzir pra bater essa Meta", não só sugestão de farm.

**Desambiguação de receita:** 15 recursos do catálogo podem ser produzidos por mais de uma
receita (ex: Heavy Oil sai do Advanced Coal Liquefier *ou* do Cracking Unit). A escolha, em
ordem de prioridade:
1. A receita que a facility **já tem configurada** em produção pra esse output
   (`material_chain.active_recipes_by_output()`, olha `production_slots` de todos os prédios).
2. Se nenhuma está ativa, prefere módulo `"Base"` (sem upgrade) como padrão menos arriscado.
3. Se ainda ambíguo, pega o primeiro candidato — determinístico, mas não necessariamente o que
   o jogador escolheria à mão. Assim que o prédio certo tiver a receita configurada em produção,
   o cálculo passa a usar ela automaticamente.

**Deliberadamente não modelado (o autor confirmou que é aceitável por ora):**
- Produção **já em andamento** não é creditada contra o déficit — só estoque já logado abate.
  Creditar produção em andamento precisaria casar timing de ciclo contra o alvo, problema bem
  maior. **Por quê, na prática:** isso exigiria o app virar um *tracker ao vivo* (saber a hora
  real de início/fim de cada ciclo e ir ajustando o estoque sozinho conforme o tempo passa),
  não um *gerador de relatório a partir de snapshot* — que é o que o app é hoje, por decisão de
  arquitetura (ver "Restrições que não mudam" no topo deste arquivo: 100% local, sem processo em
  segundo plano, sem relação com hora real do servidor do jogo). Enquanto essa restrição existir,
  a Meta só pode confiar no que já foi logado, nunca no que uma fila *vai* produzir. Se um dia
  isso mudar de decisão, é uma mudança de escopo do projeto inteiro, não um ajuste pontual no
  resolver.
- Liquid Transfer Stations movendo líquido entre prédios — o autor mencionou como possível próximo
  passo pra deixar o cálculo de líquidos mais preciso.

**Bug já corrigido aqui, cuidado se mexer de novo:** o resolver recebe o alvo (a Meta)
**cheio**, não como déficit pré-calculado (`target_max - estoque_atual`). O `stock_pool` passado
pro resolver já contém o estoque atual intacto — se você passar o déficit já subtraído, o
`resolve()` interno abate esse MESMO estoque de novo (`have` vs `needed`), podendo zerar
silenciosamente a necessidade real de produção sempre que o próprio recurso da Meta já tiver algum
estoque. A subtração "quanto falta" deve acontecer uma única vez, dentro de `resolve()`.

### Tempo total de produção

`material_chain.compute_production_time()` — não é o tempo unitário por fila (isso já existe por
prédio em `production.estimate_building_slots()`, mostrado no bloco Estoque Atual). É o tempo da
árvore inteira, calculado **duas vezes** (refeito em 02/11/2026, pedido do autor: "a FAC normalmente
roda com 5 filas, o mais importante é ver o tempo com as 5"):
- **Com 5 filas** (`FULL_QUEUES`) — o número de referência, sempre mostrado. Nó que já roda mais de 5
  filas (vários prédios) usa o número real.
- **Com as filas atuais** — só aparece quando algum nó está configurado com menos de 5. Nó que a
  facility ainda não produz conta 5 nas duas (antes contava **1 fila**, pior caso, com `*`).
- Filas configuradas = **soma** de todos os slots e prédios rodando aquela receita
  (`active_recipes_by_output`; antes pegava só o primeiro slot achado).
- O total é **em paralelo/pipeline**, não em série: uma receita começa assim que sai o primeiro ciclo
  do insumo, não espera o lote todo. Cada nó termina em `max(1º insumo pronto + tempo dele, último
  insumo pronto + 1 ciclo dele)`; o total é o término mais tarde. Antes somava a cadeia ("10h24 de
  foguete + 2h01 de Cmat = 12h25", quando na prática dá ~10h30).
- Não modela: duas receitas diferentes disputando as mesmas 5 filas de um mesmo prédio (cada receita
  conta com as próprias 5), nem produção mais lenta por falta de energia (a wiki diz que a velocidade
  cai proporcional ao déficit de energia). Ciclos de um insumo pedidos por dois produtos diferentes
  são arredondados pra cima em cada um (pode sobrar 1 ciclo a mais por produto).

### Como o relatório explica ciclos/tempo (o autor achava confuso — reescrito em 31/10/2026)

Modelo (confirmado na wiki, página Facilities): até 5 ordens de produção rodam **em paralelo** por
prédio; cada ordem repete a receita enquanto houver insumo. **1 ciclo = 1 execução da receita.**
Tempo = `ceil(ciclos ÷ filas) × tempo de 1 ciclo`. Antes o texto dizia só "120 ciclos, pronto em
16min" e misturava total de ciclos com rodadas paralelas. Agora toda linha mostra a conta:
- Card/Estoque Atual: `⚙️ 5 filas → 11 ciclos com o estoque atual (até 3 por fila × 4min30) = 13min`
  ("até" quando os ciclos não dividem igual entre as filas; com 1 fila some o "por fila").
  `production.estimate_production()` devolve `rounds` e `cycle_seconds` pra isso (espelhados no
  schema `ProductionEstimateOut` — lembrar da pegadinha do Pydantic filtrar campo não declarado).
- Produção necessária: `Foguete 3C: 3k ciclos em Fábrica de Munição — fila atual (2 filas) → 1498 por
  fila × 25s = 10h24 · Estimativa com 5 filas → até 600 por fila × 25s = 4h10`. Sem fila configurada,
  só a "Estimativa com 5 filas"; com 5 ou mais configuradas, só a "fila atual".
- Tempo total: `⏱️ Tempo total com 5 filas: **4h10** (com as filas atuais: **10h24**)` + o caminho
  crítico como cadeia (`compute_production_time()` devolve `nodes`, `full`, `current`), e uma legenda curta no fim do bloco Foco explica ciclo/fila.
- Tempo de 1 ciclo usa `format_cycle_time()` (mantém os segundos: 90s = "1min30"), não
  `format_duration()` (que arredonda pra "1min" e faria a conta exibida não bater).

## Mensagem do Discord — consolidada, separada do relatório in-app

`report_generator.build_totals_block()` gera um total consolidado da facility inteira (soma de
cada recurso + filas de produção ativas somadas por receita) especificamente pra mensagem do
Discord — o detalhamento prédio-por-prédio (que já existe no bloco "Estoque Atual"/`blocks.stock`)
não é repetido lá, era isso que fazia a mensagem ficar enorme antes.

`build_recommendation_block()` aceita um parâmetro `bulleted` — quando `True` (só na chamada que
monta o texto do Discord dentro de `generate_report()`), cada item das listas (Produção
necessária/Importar/Farm) vira uma linha com "• " em vez de tudo junto numa linha só com " • ",
bem mais fácil de ler no Discord. O bloco "Recomendação de Farm" mostrado na aba Relatório do app
continua no formato compacto original — só o texto que vai pro Discord foi reformatado.

`Report.discord_content` guarda esses parágrafos (header + totals + recomendação-com-bullets)
separadamente de `markdown_content` — o Histórico reconstrói as partes do Discord a partir desse
campo, não mais tentando fatiar o `markdown_content` cheio de detalhe por prédio.

## Recurso "importado" e mensagens de produção mais específicas

Ver seção "Recomendação de Farm virou cálculo de cadeia" acima pro flag `imported`.

A mensagem de "estoque insuficiente pra 1 ciclo" (tanto no relatório quanto no card do prédio)
antes listava **todos** os insumos da receita, mesmo que só um estivesse baixo — isso confundiu o
autor uma vez, achando que o líquido não estava sendo contabilizado quando na real era outro
insumo zerado. Agora só lista os insumos **realmente** abaixo do necessário, comparando
`inputs_per_cycle[i].available` contra `.qty`. Isso exigiu adicionar `available` no schema
`ProductionEstimateItem` (Pydantic filtra silenciosamente campos não declarados no
`response_model` — já rolou esse bug exato uma vez aqui, cuidado ao adicionar campo novo num dict
retornado por `production.py` sem espelhar no schema).

## Histórico — excluir relatório

`DELETE /api/reports/{id}` (+ `crud.delete_report`) — cada item do Histórico tem um botão
"Excluir" (com `confirm()`) ao lado de "expandir ▾"; apaga só aquele relatório.

## OCR / detecção automática de estoque

Duas formas de lançar estoque a partir de um print, no mesmo modal "Enviar print (OCR)":

1. **Recorte manual** — usuário desenha um retângulo em volta de cada número, Tesseract lê.
   Sempre funcionou, é o fallback pra qualquer item que a detecção automática errar/pular.
2. **Detecção automática** (`app/services/icon_match_service.py`) — usuário desenha **um**
   retângulo em volta do painel STOCKPILE inteiro; o backend faz *template matching* (OpenCV,
   `cv2.matchTemplate`, escala de cinza, múltiplas escalas) contra os ícones do catálogo pra
   achar cada item e sua posição, recorta automaticamente a região do número (heurística
   calibrada contra prints reais) e manda pro Tesseract (PSM 11, não PSM 7 — recorte automático
   pega mais borda de ícone que um recorte manual cuidadoso, e PSM 11 tolera isso melhor).

   **Validado, não é 100%:** identificação do item funciona muito bem (~0.85-0.97 de confiança
   nos testes reais). Leitura da quantidade continua imperfeita (ponto decimal é o ponto fraco —
   às vezes "1.4k" vira "14k", um erro de 10x) — por isso o valor lido **sempre** vem como
   pré-preenchimento editável, nunca salva sozinho, igual ao recorte manual sempre foi.

   Itens de uma mesma família que compartilham o desenho (ex: Assembly Materials I-V) podem ficar
   ambíguos — o item é marcado com aviso âmbar "pode ser X — confira antes de salvar" em vez de
   escolher silenciosamente. Ver "Detector de ícones" abaixo pra como isso é resolvido.

### Detector de ícones (refeito em 01/11/2026 — `icon_match_service.detect_items`)

Antes acertava o item em 25/30 dos valores confirmados; os erros eram Sulfur nunca encontrado e
Assembly Materials trocando de nível. Mudanças, cada uma medida nos 12 prints reais:
1. **Comparação por "brancura"** (`min(B,G,R)`) em vez de escala de cinza. O desenho do item é
   branco; o fundo do slot pode ser triângulo amarelo (Sulfur), losango azul (Assembly
   Materials)... Em cinza o amarelo parece quase tão claro quanto o desenho — por isso o Sulfur
   nunca era achado. Em brancura qualquer fundo colorido fica escuro. (Sulfur: 0/3 → 3/3.)
2. **Várias posições por ícone + descarte de slot cinza antes de escolher.** Antes cada ícone só
   tinha a melhor posição, e slots cinza (itens zerados, sem número) "roubavam" o ícone do slot
   real. Agora posições sem texto branco no canto do número são descartadas na hora.
3. **Decisão por slot**, depois resolução de conflitos (cada item em um slot só).
   - Filtro de slot vazio (`MIN_WHITE_FRACTION`) baixado de 0,02 pra **0,01**: um "2" sozinho tem
     1,3% de pixels brancos e era descartado. Medido em 1100+ caixas de 32 prints: números reais
     ≥ 0,0126, slots cinza < 0,004 (um caso de 0,0066).
   - Caixa do número começa em `-0,25×tamanho` à esquerda (era -0,10): nos ícones que o mod desenha
     dentro de círculo, "258" virava "58".
4. **Exemplos aprendidos** (`data/icon_exemplars/<item>/*.png`, gitignored): os 5 níveis de
   Assembly Materials são o mesmo desenho e só diferem num selinho colorido no canto superior
   esquerdo que o jogo desenha — e o selinho dos ícones da wiki (e do FIR) **não** é igual ao do
   jogo, então comparar forma não separa os níveis (testado, piorou). O que funciona: recortes
   reais de slots que o usuário já confirmou. Quando ícones quase iguais empatam num slot, compara
   a região do selinho (`BADGE_REGION`) com os exemplos, em cor; resolve se a similaridade passa
   de `EXEMPLAR_MIN` com folga de `EXEMPLAR_LEAD`. Comparar o ícone inteiro não servia (0,97 vs
   0,94 entre níveis); só o canto: 1,00 vs ≤0,84. Slot empatado que exemplo não resolveu **sempre**
   fica marcado "confira", mesmo que os outros itens empatados já tenham ido pra outros slots.
   - Exemplos são salvos quando o usuário salva um print (`POST /api/images/{id}/exemplars`,
     chamado pelo `print.js` só pros slots vindos da detecção automática, com o item que o usuário
     **confirmou**, não o que o detector chutou). Máximo 8 por item.
   - `scripts/seed_icon_exemplars.py` gera exemplos dos prints confirmados no passado (rotula o
     slot pelo valor confirmado que bate com o número lido). Rodado em 01/11: 28 exemplos.
   - Níveis sem nenhum exemplo ainda (no caso do autor, Assembly Materials III e IV) continuam
     dependendo do aviso "confira" até a primeira confirmação.
   - **Exemplos também são usados pra *achar* itens**, não só desempatar: cada recorte salvo vira um
     template extra (em brancura). É o único jeito de achar ícones que o mod **redesenha** — Typhon,
     Lamentum, Flame Ammo pontuavam 0,57-0,75 contra a arte da wiki. Testado: depois de nomear
     Typhon e Lamentum uma vez num print, o print seguinte reconheceu os dois sozinho.
5. **Slot não reconhecido não some** (`_grid_slots`): a partir dos slots reconhecidos o detector
   deduz a grade (tamanho e passo são regulares) e devolve todo slot com número que nenhum ícone
   explicou como item `resource_def_key: None`, com o número lido. O `print.js` mostra "item não
   reconhecido — escolha qual é"; a lista de nomes inclui o catálogo inteiro (não só os recursos já
   cadastrados), e ao salvar o recorte vira exemplo. Precisa de ≥ 2 slots reconhecidos pra deduzir
   a grade.

**Ícones com mod:** o autor usa o mod `War-WindowsNoEditor_CleanIconsEssential_FULLPACKAGE_v2.5.0.pak`,
que **colore** os ícones (fundo amarelo no Sulfur, losango azul + selinho colorido por nível nos
Assembly Materials, e redesenha algumas armas/munições com o nome escrito). No jogo sem mod os
ícones são desenhos brancos sem cor (estilo dos ícones da wiki). Medido nos dois estilos em
01/11/2026: **sem mod 29/29** (glm-ocr), com mod 40/47 + 4 como "não reconhecido". O que falha com
mod é ícone redesenhado (resolvido pelo aprendizado depois da primeira confirmação) e 120mm
confundido com 300mm. Exemplos de prints com e sem mod convivem (o detector usa o mais parecido).

**Bug corrigido junto (introduzido em 31/10):** o `print.js` mandava o código do item detectado
mesmo quando o usuário corrigia o nome — e como `get_or_create_resource()` passou a casar primeiro
pelo código, a correção era ignorada e o estoque ia pro item errado. Agora `confirmedDefKey()` só
usa o código detectado se o nome não foi mexido.

   `GET /api/ocr/status` retorna `stockpile_detect_available` (checa se OpenCV está instalado) —
   se não, o botão de detecção automática nem aparece, só o recorte manual.

### Captura: quem lê o número é escolhido pelo usuário (`app/services/capture/`)

Desde 31/10/2026 o ícone continua sendo identificado por template matching, mas **quem lê o
número** é configurável em "⚙️ Configurações" (`#/settings`, tabela `app_settings`, global do
servidor): `rapidocr` (padrão), `local_vlm` (Ollama, GPU do usuário), `api_vlm` (Anthropic ou
qualquer endpoint compatível com OpenAI, chave do usuário, cobrado por uso) e `tesseract` (antigo).
Vale pro recorte manual e pra detecção automática. Se o escolhido não estiver disponível (Ollama
fechado, sem chave), `capture.resolve_reader()` cai pro melhor OCR local e o modal de print avisa
qual está sendo usado. Erro de rede/engine vira "não leu", nunca 500. A chave de API fica só no
banco e a API devolve só `api_key_set` + os 4 últimos caracteres.

**Medição (01/11/2026, com o detector novo)** — 32 prints reais, 106 valores conferidos:

| Leitor | 12 antigos (mod) | 10 novos com mod | 10 novos sem mod | Total | Tempo (12 prints) |
|---|---|---|---|---|---|
| Tesseract | 5/30 | 8/47 | 5/29 | 18 | — |
| RapidOCR | 28/30 | 35/47 | 28/29 | 91 | 70s |
| **glm-ocr** | 28/30 | 40/47 | 29/29 | 97 | 77s |
| qwen3.5:9b | 29/30 | 40/47 | 29/29 | 98 | 223s |
| qwen3-vl:4b | 29/30 | 40/47 | 29/29 | 98 | 708s |
| qwen3-vl:8b | estoura o timeout de 120s por número (não cabe nos 8GB da RTX 5060) | | | | |

**`glm-ocr` é o modelo local recomendado** (e o configurado no PC do autor): mesmo acerto na
prática, ~3x mais rápido que o qwen3.5 e 9x que o qwen3-vl:4b, e ocupa ~2,7GB de VRAM (o Foxhole
roda na mesma placa; qwen3.5 ocupa 6,3GB). O `qwen3-vl` "pensa" antes de responder mesmo com
`think: false` (~110 tokens por número) — por isso é lento. `num_predict: 32` nas opções do Ollama:
sem isso o glm-ocr às vezes entrava em loop num recorte sem número e o Ollama abortava com HTTP 500
"token repeat limit reached".

Bases de teste: (1) `data/uploads` + `stock_entries` com `source='ocr'` (12 prints antigos, valores
que o autor confirmou no app); (2) `print/mod/` e `print/vanilla/` com gabarito em
`print/truth.json` + caixas do painel em `print/boxes.json` (20 prints de 01/11/2026, gabarito
montado olhando cada print; um slot de Assembly Materials com selinho não identificado ficou de
fora, e o 224 é inventário de caminhão — itens repetidos em vários slots, fora do escopo).
**`scripts/benchmark_capture.py <motor>`** mede a base (2). `print/` é gitignored (nomes de
jogador/clã).

Decisões que custaram teste, não desfazer sem medir de novo:
- A IA **só vê o recorte do número**, nunca o painel inteiro: pedindo pra ela identificar os itens
  sozinha no painel deu 5/30 (não distingue os ícones estilizados).
- Prompt da IA **sem números de exemplo**: com "like 5.1k" o qwen respondia "5.1k" em slot vazio.
- Slot sem número é pulado antes de chamar qualquer leitor (`icon_match_service._has_white_text`:
  < 2% de pixels quase brancos na caixa do número). Slots com número reais tinham ≥ 3%, vazios ~0%.
  Sem isso a IA respondia "1" pra slot cinza (71 falsos positivos → 5, e os 5 eram números reais).
- `readers.sanitize()` troca letras parecidas por dígito (RapidOCR leu "3T.9k" pra "31.9k"), aceita
  letra só como sufixo k/M depois dos dígitos (RapidOCR leu "1" como "M1") e trata "NONE" (resposta
  da IA pra "sem número") como vazio — antes virava "N0NE" → "0".
- Modelos do RapidOCR vêm dentro do pacote pip (sem download em runtime).
- API por nuvem **não foi testada com chave real** (só o caminho de salvar/mascarar a chave).

## Leitura do save do jogo (`app/services/save_reader.py`)

O save local do Foxhole (`%LOCALAPPDATA%\Foxhole\Saved\SaveGames\<steamid>_MapData.sav`, GVAS do
UE4) guarda, pra cada local **pinado** no mapa (Ctrl+A no jogo, até 25 por facção), o estoque que o
jogo mostrou no tooltip da última vez + o `LastUpdated` do próprio jogo. O cache só atualiza quando
o jogador abre o tooltip daquele pin no jogo. É número exato, sem OCR.

Quem parseia é o CLI Rust em `tools/save-parser/` (veio do repo `foxhole-msupps-parser`, que foi
apagado; tem o próprio `CLAUDE.md` explicando o formato GVAS) (`--json`, validado contra saves reais
inclusive da v1.67) — **não reimplementar GVAS em Python**. `read_pinned_locations()` sem argumento
lê o save mais recente deste PC; com `save_bytes` parseia um `.sav` enviado pelo navegador (no modo
web o servidor não enxerga o PC do jogador). O `--json` é um contrato: `PinnedLocation` do parser +
`grid_coordinate` — renomear campo lá quebra aqui. `pin_key()` = `"{map_id}:{x:.4f}:{y:.4f}"`, a
única identidade que o jogo dá a um pin.

Onde o binário é procurado (`_PARSER_CANDIDATES`, ou env `FOXHOLE_SAVE_PARSER`):
`tools/save-parser/target/release/` (depois de `scripts/build_save_parser.py`).

Bug do próprio jogo (v1.67): o tooltip pinado para de atualizar se a estrutura for melhorada — se
um pin "congelar", despinar e pinar de novo.

### "Importar do save" (MTS e qualquer stockpile pinado)

Botão "📌 Importar do save" em todo card de prédio (`web/js/views/saveImport.js`, rotas em
`app/routers/save.py`). Motivo: desde a v1.67 dá pra pinar uma Material Transfer Station reservada
pro squad e ver o estoque dela no tooltip — então ela aparece no save. Fluxo:
1. `POST /api/save/pins` (sem arquivo = save deste PC; com arquivo = `.sav` enviado, modo web) →
   pins com estoque, itens já traduzidos pra recurso do catálogo (`codename` do `resources.json`, ou
   apelido salvo em `codename_aliases`).
2. Usuário escolhe qual pin é aquele prédio. Pré-seleção: o pin vinculado da última vez
   (`buildings.save_pin_key`), senão o mais recente do mesmo tipo de prédio, senão o mais recente.
3. Itens viram linhas editáveis (mesma regra do OCR: nada salva sozinho). Código desconhecido vira um
   `<select>` pro usuário escolher o recurso, e a escolha fica em `codename_aliases`.
4. Salvar grava `StockEntry` com `source="save"`, vincula o pin e salva os apelidos.

`crud.get_or_create_resource()` agora casa primeiro por `resource_def_key` (antes só pelo nome) —
evita criar "Construction Materials" duplicado quando o usuário já tem o recurso salvo como "Cmat".

**Validado com save real em 02/11/2026:** o autor importou as MTSs de uma FAC pelo
save — o pin da MTS é reconhecido pelo tipo de prédio (aparece como "Estação de Transferência de
Materiais — Westgate G5"). Ainda não conferido: se `Quantity` é item ou caixa em stockpile que
guarda caixa (MTS guarda item solto, então não afeta MTS).

**Prédio "travado" no pin (02/11/2026, pedido do autor — MTS quase nunca muda de lugar):** com
`save_pin_key` preenchido e o pin presente no save, o modal **não mostra o seletor de pin** — mostra
"📌 Vinculado a <pin> · atualizado há X" e um botão **Desvincular** (confirma, grava `pin_key: null`,
volta o seletor). Se o pin vinculado sumiu do save (despinado no jogo), avisa e mostra o seletor. O
card do prédio mostra 📌 na linha de upgrade/local quando está vinculado.

## Modais

**Enviar print:** o print normalmente já está na área de transferência — **Ctrl+V em qualquer lugar da
página** (enquanto o modal está aberto) carrega a imagem; colar texto num campo passa direto. Clicar
na área tracejada **não** abre mais o explorer do Windows (atrapalhava quem só queria colar); o
explorer só abre pelo botão "📁 Escolher arquivo". Arrastar imagem continua funcionando.

Formulários grandes (Lançar estoque, Enviar print/OCR, Produção) abrem em modal
(`ui.openModal(titulo, buildFn, {maxWidth})`) em vez de expandir inline dentro do card do prédio.
Motivo: um grid responsivo de cards + formulário grande inline nunca fica bonito — um card com
15 itens no catálogo fica muito mais alto que o vizinho, e inputs brigam por espaço com a largura
da coluna do grid. O card em si fica curto e uniforme (ícone, nome, resumo de estoque atual,
botões); o formulário ganha sua própria largura quando aberto. `onChange` passado pro formulário
já fecha o modal + atualiza a lista de prédios depois de salvar.

## Cards de prédio — layout refeito em 01/11/2026 (antes nunca alinhava)

Os cards sempre ficavam desalinhados: a grade tinha `items-start` (cada card com a altura só do
próprio conteúdo) e o painel de ícone lateral comia metade da largura, então nomes como "Materiais
de Montagem I:" quebravam em 3-4 linhas e cada card tinha uma altura diferente. Agora
(`facilityDetail.js`, `buildingCard` + `renderBuildingsList`):
- **Prédios agrupados por tipo** (seção com ícone, nome do tipo e contagem; prédios sem tipo em
  "Outros prédios"). Mesmo tipo = itens parecidos, então as linhas de cada grupo saem uniformes.
  Grupos na ordem do primeiro prédio de cada um; dentro do grupo vale o `position`.
- Grade `repeat(auto-fill, minmax(280px, 1fr))` **sem** `items-start` → os cards de uma linha esticam
  até a mesma altura; o card é `flex flex-col h-full` e o rodapé de botões tem `mt-auto`, então os
  botões ficam na mesma altura entre vizinhos. `auto-fill` (não `auto-fit`) pra um grupo de 1 card
  não esticar na largura toda.
- Sem painel de ícone lateral (o cabeçalho do grupo mostra o ícone). Estoque = uma linha por item:
  miniatura, nome com `truncate` (nome inteiro no `title`), quantidade à direita com
  `tabular-nums` e separador de milhar (`formatQty`). O ✕ de excluir aparece no hover.
- Editar/excluir viraram ícones (✎ 🗑) no cabeçalho do card. Rodapé com 4 botões curtos numa linha
  (`flex-auto` + `truncate`; texto completo no `title`) — `flex-wrap` quebrava em 2 linhas e colunas
  iguais cortavam "⚙️ Produção".
- **Reordenar:** arrastar pela alça ⠿ só **dentro do mesmo grupo**. Soltar em cima de um card
  **toma o lugar dele**: arrastando pra frente cai depois dele, pra trás cai antes (corrigido em
  02/11/2026 — a regra antiga de "metade esquerda/direita" fazia o primeiro card quase nunca chegar
  ao último lugar, porque soltar na metade esquerda do último deixava em penúltimo). Soltar no espaço
  vazio da grade manda pro fim. Uma barra verde na lateral do card mostra onde vai cair. Salva
  `position` de todos os prédios na ordem da página.
- Formulário "novo prédio" empilha no celular (`grid-cols-1 sm:grid-cols-[...]`) — antes estourava a
  largura da tela.

### Upgrade do prédio (02/11/2026)

No jogo cada prédio de facility instala **no máximo um** upgrade (não dá pra desinstalar), que
**acrescenta** receitas às da base (wiki, página Coal Refinery). O modal "⚙️ Produção" tem um
seletor "Upgrade instalado" e as filas só oferecem receitas da base + desse upgrade
(`upgradeOptions`/`buildingUpgrade` em `facilityDetail.js`; módulo "base" = vazio ou começando com
"Base", ex: "Base (Uniforms)"; tipo com um módulo só, como o Aircraft Maintenance Hangar, não mostra
seletor). Salvo em `buildings.upgrade` junto com a produção. Prédio antigo sem `upgrade` salvo tem o
upgrade **inferido** da receita não-base que já está em produção. Uma receita já numa fila que o
upgrade escolhido não oferece continua na lista marcada ⚠ (trocar o upgrade nunca apaga fila
calado). O card mostra "⬆ <upgrade>" embaixo do nome.

**Agrupamento:** padrão continua "por tipo" (pedido do autor: segmentar demais atrapalha). Um
seletor "Agrupar: por tipo / por tipo e upgrade" acima da lista troca pra um grupo por
tipo+upgrade; preferência por navegador (`localStorage["buildingGrouping"]`). Arrastar continua
só dentro do grupo exibido.

### Local do prédio (02/11/2026)

Pedido do autor: uma FAC tem MTSs em dois lugares (nomeadas tipo "MTS01 - Norte",
"MTS01 - Sul"). `buildings.location` é texto livre, editado no ✎ do card (que virou um modal com
apelido + local, em vez do `prompt()`) e no formulário de novo prédio (o campo **mantém** o valor
depois de adicionar, pra cadastrar vários do mesmo lugar em seguida). Os dois campos sugerem os locais
já usados na facility (`<datalist id="locations-datalist">`). O card mostra "📍 local" ao lado do
"⬆ upgrade". Espaços nas pontas são cortados no backend (`crud.update_building`; vazio vira NULL).

Ao vincular um pin do save ("Importar do save"), se o prédio ainda não tem local, ele recebe a região
+ quadrado do pin (`SavePinOut.location`, ex: "Westgate G5"); local já preenchido nunca é
trocado.

Agrupamento tem 4 modos: por tipo (padrão), por tipo e upgrade, **por local**, **por local e tipo**.
Nos modos por local os grupos saem em ordem alfabética do local, com "sem local" por último.

Continua valendo: **nada de `overflow-hidden` no card inteiro** (já cortou conteúdo calado duas
vezes); toda linha nova com texto precisa de `min-w-0`/`truncate`.

## Metas por facility e fim do Catálogo de Recursos (02/11/2026)

Pedido do autor: a aba "Catálogo de Recursos" confundia (a "Meta" não dizia o que era, 3 caixinhas
repetidas em toda linha) e a Meta era global — agora há duas FACs que querem quantidades diferentes.
- **A aba saiu do menu** (`resources.js` apagado). Ela não era necessária: recurso é criado sozinho
  ao lançar estoque/print/save, e o catálogo já dá a origem certa de quase todo item.
- **Aba "Metas" dentro de cada facility** (`web/js/views/targets.js`, `#/facilities/<id>/targets`):
  tabela Item / Estoque / Meta / Falta / barra, ordenada pelo que está mais longe da meta (atingidas
  e abundantes no fim). "+ Adicionar meta" busca no catálogo inteiro (e em itens livres criados à
  mão), agrupado por categoria; escolher um item de catálogo que ainda não é recurso cria o recurso.
  A meta é editada na própria célula: aceita `3000`, `3k`, `1,5k`; líquido é sempre em **litros**
  (`5000L` ou só `5000`), convertido pra unidades antes de salvar. Vazio remove (com confirmação).
- API: `GET /api/facilities/{id}/targets` (com `current` = estoque da facility inteira, tanque +
  caixa, por chave de catálogo — mesma soma que o relatório usa) e `PUT` com `{resource_id |
  resource_def_key, target_max}` (`null`/0 apaga). `crud.get_facility_targets()` dá
  `{resource_id: meta}`, que `generate_report(..., targets)` recebe.
- **Migração:** `apply_migrations()` copiou cada `resources.target_max` antigo pra **todas** as
  facilities e zerou a coluna (então roda uma vez só). As metas antigas (120mm e Foguete 3C, 3000
  cada) existem agora nas duas FACs.
- **Painel do item** (`web/js/views/itemPanel.js`): clicar no nome de um item no card do prédio ou na
  aba Metas abre apelido + **Origem** de escolha única — 🏭 Produzido / 🌾 Farmado / 📦 Importado /
  ∞ Abundante — gravada nos mesmos três flags (`farmable`/`imported`/`unlimited`), um por vez (antes
  dava pra marcar combinações sem sentido). O apelido é **global**.
- **Origem por facility (02/11/2026):** uma FAC pode importar o que outra produz. Tabela
  `facility_item_origins` (`facility_id`, `resource_id`, `origin` = produced/farmed/imported/unlimited);
  sem linha, vale o padrão global (os flags de `resources`, que continuam existindo e não são mais
  editados pela tela). `crud.resources_for_facility()` devolve **cópias** (`SimpleNamespace`, nunca
  linhas do ORM — mexer nelas não grava nada) com os flags da facility aplicados; é o que o relatório,
  a estimativa de produção (`/production-estimate`), a aba Metas e `GET /api/resources?facility_id=`
  usam. O painel grava com `PUT /api/facilities/{id}/item-origins`.

## Aba "Ao vivo" — dashboard com estimativa (03/11/2026)

Pedido do comando do regimento: uma tela que se atualiza sozinha, parecida com o bot de mSupps do
regimento. **É estimativa, nunca é gravada:** `app/services/projection.py` pega o estoque lançado de cada
prédio e o horário do último lançamento dele, supõe que as filas configuradas rodaram sem parar desde
então (só rodadas completas contam; para quando um insumo acaba; produto cai no mesmo prédio; várias
receitas no mesmo prédio consomem o estoque uma depois da outra) e devolve o estoque projetado + "insumo
acaba às X". `GET /api/facilities/{id}/dashboard` calcula na hora (sem `response_model`), junto com as
Metas comparadas ao total projetado. `web/js/views/dashboard.js` (`#/facilities/<id>/live`) pede de novo
a cada 30s e para de pedir quando sai da aba. Relatório, Metas, cards e cálculo de cadeia continuam
usando **só** estoque lançado — o próximo lançamento real zera a projeção. Não sabe de fila pausada ou
trocada, falta de energia, nem material levado entre prédios. Não reintroduz nada de mSupps.

Decisão de arquitetura (ver "Deliberadamente não modelado" na cadeia): isso **não** transforma o app num
tracker ao vivo — não há escrita automática de estoque; é uma conta feita na leitura.
Juntada na main em 03/11/2026, a pedido do autor; a projeção ainda não foi comparada com o jogo por vários dias.

### Painel no Discord por webhook (sem bot)

Pedido do autor no mesmo dia: o painel aparecendo e se atualizando num canal, como o bot do regimento, mas
**sem bot** — um webhook do canal posta uma mensagem e depois só **edita** a mesma
(`app/services/discord_dashboard.py`). Configurado por facility na caixa "📣 No Discord" da aba Ao vivo
(tabela `facility_webhooks`: URL, id da mensagem, idioma da página na hora de salvar, último envio/erro).
- **Único processo em segundo plano do app:** uma tarefa asyncio iniciada no `lifespan` de `main.py` que a
  cada `INTERVAL_SECONDS` (60s) edita a mensagem de cada facility com webhook. Sem webhook nenhum, não faz
  nada. Só grava o próprio controle do webhook — estoque continua só o lançado. Pula webhook enviado há
  menos de 55s, então dois servidores no mesmo banco (bandeja + teste) não dobram as edições.
- Contagens usam timestamp do Discord (`<t:unix:R>`), que cada cliente redesenha sozinho — "insumo acaba
  em 12 minutos" anda entre as edições. Por isso 60s basta.
- Mensagem apagada no Discord (PATCH 404) → posta outra. "Parar" apaga a mensagem do canal. Erro (webhook
  apagado, sem internet) fica em `last_error` e aparece na caixa; nunca derruba o laço.
- A URL funciona como senha do canal: a API nunca devolve, só os 4 últimos caracteres. Só aceita
  `https://discord.com/api/webhooks/...` (e ptb/canary/discordapp).
- **Tópico (thread):** campo opcional (link do tópico ou ID → `facility_webhooks.thread_id`). O webhook é
  do canal onde o tópico está, e `?thread_id=` vai em todo POST/PATCH/DELETE. Criar webhook precisa da
  permissão "Gerenciar webhooks" no canal — quem não tem essa permissão pede pra alguém do comando, que
  cria e passa a URL. Trocar só o tópico não exige colar a URL de novo (vazio = mantém); trocar
  canal/tópico apaga a mensagem antiga e posta uma nova.
- Texto da mensagem segue o idioma da interface, nomes de item o idioma do catálogo (bug corrigido: as
  linhas dos prédios saíam no idioma do catálogo).
- Embed: Metas com barra, um campo por prédio com fila (🟢 rodando / 🔴 parado, falta X, produzido desde o
  lançamento, estoque projetado). Se passar de ~5800 caracteres tira as linhas de estoque; máx. 22 prédios.
- Só atualiza com o servidor ligado — por isso roda numa VM (ver "Modo web"). Com o servidor
  desligado a mensagem para no último valor (o "Atualizado há X" mostra isso).
- **Testado** com um Discord falso local (POST/PATCH/404→novo POST/DELETE, laço de 60s) numa cópia do
  banco. **Validado com webhook real** em 03/11/2026, num tópico de um servidor de teste
  (canal + tópico, edição a cada minuto).

## Pegadinhas do ambiente de dev (Windows)

- **Processos duplicados do uvicorn:** `python run.py` usa `reload=True`. Se um servidor foi
  iniciado via Bash em background E outro via `preview_start` do Browser tool, os dois podem
  ficar escutando na porta 8000 e uma requisição pode bater no processo errado (código
  desatualizado) mesmo depois do log dizer "Reloading...". Também houve caso de `--reload` não
  pegar uma edição mesmo com processo único. **Solução:** `preview_stop` + `preview_start` pra
  garantir processo único e fresco antes de confiar num resultado de teste "não funcionou".
- **`navigate()` do Browser pane pra mesma hash não recarrega de verdade** — reusa estado JS
  antigo (closures, listeners, variáveis globais) se a URL só muda de hash e já foi visitada
  antes. Se um resultado de teste parecer bizarro (elemento com tamanho 0, estado que deveria
  estar fresco não está), abrir uma aba nova (`tabs_create` + `navigate`) em vez de assumir bug
  de timing/reflow.
- **`prompt()`/`confirm()` nativos do navegador não são interativos** via automação — pra testar
  um fluxo que usa `prompt()`, sobrescrever `window.prompt = () => 'valor'` via `javascript_tool`
  antes de clicar no botão, em vez de tentar digitar no diálogo nativo.

## Git — workflow sem `gh` CLI

Nem `gh` nem token do GitHub estão disponíveis neste ambiente, e o repo (`rlanak/facility-log`) é
privado — abrir PR pela web também não dá. **O que funciona:** merge local + push direto pra
`main` (`git merge --no-ff <branch>`, `git push origin main`) — reproduz o efeito de um merge de
PR sem passar pela UI do GitHub. Sempre `git fetch` + comparar `main` local com `origin/main`
antes de mergear (`main` local pode estar desatualizada mesmo com a branch de feature em dia).

Padrão atual: features maiores (ex: detecção automática de OCR) ganham branch própria até o autor
validar num teste real; correções pequenas/testadas vão direto pra `main`. O autor já disse "já
podemos trabalhar na main" — não precisa mais perguntar antes de commitar ali quando o trabalho
já foi testado no navegador.

## Status atual

Fases 1-3 (CRUD, relatório, OCR manual) completas e testadas há tempo. Sessões seguintes
adicionaram: presets do catálogo Foxhole, produção multi-fila, tanques de líquido, i18n de duas
camadas, detecção automática de item via template matching, refatoração pra modais, correção de
ícones de prédio errados/duplicados, correção do ícone de Construction Materials.

Sessão mais recente (a que motivou a seção "Recomendação de Farm virou cálculo de cadeia" acima)
foi um retrabalho grande em cima de feedback de uso real do autor: tanque e caixa de líquido
virando quantidades independentes (`StockEntry.storage`), cap de 5000L com bug de arredondamento
corrigido, mensagens de "produção insuficiente" apontando só o insumo realmente baixo, a
Recomendação de Farm reescrita como um resolvedor recursivo de cadeia de produção
(`material_chain.py`) com os flags `farmable`/`imported` como folhas, tempo total estimado (caminho
crítico, não soma flat), mensagem do Discord consolidada num total de facility em vez de repetir o
detalhamento por prédio, líquidos sempre exibidos em Litros no texto do relatório, e botão de
excluir relatório no Histórico. Um bug real de double-counting de estoque na Meta foi encontrado e
corrigido durante essa sessão — ver o aviso na seção da cadeia de recomendação antes de mexer ali
de novo.

Sessão de 31/10/2026 (grande): o autor aposentou o tray e os mSupps de vez; o facility-log virou o
app único e ganhou, em commits separados: leitura do save do jogo (`--json` novo no parser, depois
movido pra `tools/save-parser/`), relatório explicando a conta de ciclos/filas/tempo, Material Transfer
Station + "Importar do save", motor de captura escolhível (RapidOCR/IA local/API/Tesseract, medido
em prints reais), modo web opcional com login Discord + Docker, e o `.exe` trocado por atalho com ícone na bandeja (sem janela preta). Wiki conferida: jogo na v1.67
(01/10/2026), nenhuma receita dos 8 prédios do catálogo
mudou desde a v1.66; novidade relevante é o **Pipe (Transfer Point)** (move líquido sozinho pra
redes de cano ligadas a facilities) e Liquid Silo ligando em Liquid Silo — mesmo assunto do item
"Liquid Transfer Stations" abaixo.

**Em aberto / não resolvido ainda:**
- Importar do save: `Quantity` de stockpile que guarda caixa (não MTS) ainda não conferido — item ou
  caixa.
- Captura com mod: 120mm confundido com 300mm (o mod redesenha os dois); Assembly Materials III/IV
  sem exemplo ainda (dependem do aviso "confira" até a primeira confirmação). Inventário de veículo
  (mesmo item em vários slots) não é suportado — o detector assume um item por slot e cada item
  uma vez.
- Modo web: login com app Discord real e `docker build` não testados (sem Docker na máquina).
- Captura por API de nuvem não testada com chave real.
- Overflow automático caixa↔tanque não é simulado — só dá pra logar as duas quantidades à mão
  (ver seção Tanques de líquido).
- Desambiguação de receita quando mais de uma produz o mesmo recurso e nenhuma está ativa em
  produção (usa módulo Base ou primeiro candidato — pode não bater com a escolha real do
  jogador). Liquid Transfer Stations (mover líquido entre prédios) ainda não existem no catálogo —
  O autor cogitou incluir pra deixar esse cálculo mais preciso.
- Cadeia de recomendação não credita produção **em andamento** contra o déficit, só estoque já
  logado (decisão consciente, ver seção da cadeia).
- Ponto decimal perdido na leitura OCR de quantidade — limitação conhecida, sem solução fácil
  (possível saída: ler estoque de pins do save em vez de OCR, ver "Leitura do save do jogo").
- Base de teste ainda pequena pra Assembly Materials (o autor saiu da facility que tinha esses itens) — quando tiver prints
  com AM II-V, acrescentar em `print/` + `print/truth.json` e rodar `scripts/benchmark_capture.py`.
