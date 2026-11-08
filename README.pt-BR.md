# facility-log

[English](README.md) · **Português**

Relatórios de estoque das facilities do **Foxhole**, prontos pra colar no Discord: estoque por prédio,
total da facility, estimativa de produção e o que falta produzir ou farmar pra bater as Metas.

- Lançamento de estoque à mão, por **print** do painel STOCKPILE (os itens são reconhecidos
  automaticamente) ou pelo **save do jogo** (locais fixados no mapa). Valor lido nunca é salvo sem
  você confirmar.
- Aba **Dashboard** com a estimativa do estoque pelas filas de produção, e painel no Discord que se
  atualiza sozinho por webhook (sem bot).
- Roda **local** (sem conta, sem serviço pago) ou na **web**, com login pelo Discord liberado por cargo.
- Visual personalizável (temas, cores, fontes) e fuso horário por pessoa, em Configurações.

Há duas formas de usar:

| | Local | Web |
|---|---|---|
| Pra quem | só você, no seu PC | o regimento todo, pelo navegador |
| Login | não tem | Discord, só quem tem o cargo |
| Precisa de | Python (Windows) | um servidor com Docker |

---

## Rodar local (Windows)

### 1. Instalar

1. Instale o **Python 3.11 ou mais novo** ([python.org/downloads](https://www.python.org/downloads/)) e
   marque **"Add python.exe to PATH"** na instalação. Confira num terminal: `python --version`.
2. Baixe o projeto — com Git (`git clone https://github.com/rlanak/facility-log.git`) ou pelo botão
   **Code → Download ZIP** do GitHub (e extraia).
3. Num terminal (PowerShell ou Git Bash), dentro da pasta do projeto:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

### 2. Abrir

```bash
.venv/Scripts/python.exe run.py
```

Abra **http://localhost:8000**. Pra fechar, `Ctrl+C` no terminal.

**Atalho na área de trabalho (recomendado pro dia a dia):**

```bash
.venv/Scripts/python.exe scripts/create_shortcut.py
```

Cria o atalho **"Facility Log"**: ele abre o app sem janela preta, com um ícone perto do relógio
(clique duplo abre o navegador; "Sair" desliga). O menu do ícone segue o idioma do Windows
(português ou inglês). Se mudar a pasta do projeto de lugar, rode o comando
de novo.

### 3. Leitura de prints

Já funciona como vem: o **RapidOCR** é instalado junto e lê os números dos prints. Em
**Configurações** dá pra trocar:

- **IA local (Ollama)** — um pouco mais precisa, usa a sua placa de vídeo. Instale o
  [Ollama](https://ollama.com), rode `ollama pull glm-ocr` e escolha "IA local" com o modelo
  `glm-ocr`. Ele ocupa uns 3 GB de memória de vídeo (o jogo divide a placa com ele). Sem placa de vídeo,
  fique no RapidOCR.
- **IA por API** — Anthropic ou qualquer serviço compatível com OpenAI, com a **sua** chave (cobrado
  por uso pelo serviço).

No envio do print, a opção **"Zerar o que não aparece no print"** (ligada por padrão) zera os itens
lançados no prédio que o print não mostra — o painel STOCKPILE lista tudo que existe.

### 4. Importar do save do jogo (opcional)

Lê o estoque exato dos locais que você fixou no mapa do jogo (por exemplo, uma Material Transfer
Station), sem print. Precisa do leitor do save, que é compilado uma vez:

1. Instale o Rust ([rustup.rs](https://rustup.rs)).
2. Rode `.venv/Scripts/python.exe scripts/build_save_parser.py`.

No jogo, fixe o local no mapa e abra o tooltip dele (é quando o jogo guarda o estoque no save). No
app, use o botão **Save** no card do prédio pra escolher o pin e vincular. Depois, **"Atualizar
vinculados do save"** (aba Prédios) atualiza todas as MTS/RTS vinculadas de uma vez.

### Atualizar

- **Com Git:** `git pull` na pasta do projeto e, se o `requirements.txt` mudou, rode o `pip install`
  de novo. Depois reabra o app.
- **Pelo ZIP:** baixe o ZIP novo, extraia por cima e **mantenha a pasta `data/`**.

### Onde ficam os seus dados

Tudo na pasta **`data/`** do projeto: `facility_log.db` (o banco), `uploads/` (prints),
`icon_exemplars/` (ícones que o app aprendeu) e `secret.key` (chave que protege segredos salvos, como
o webhook). **Backup = copiar a pasta `data/` inteira** com o app fechado.

---

## Rodar na web (servidor com Docker)

Você precisa de um servidor Linux com **Docker** (uma VM pequena basta: 2 vCPU e 2 GB de RAM) e de
um jeito de publicar com HTTPS.

### 1. Criar o app no Discord

É ele que faz o "Entrar com Discord". Não é bot e não precisa entrar no servidor.

1. Em [discord.com/developers/applications](https://discord.com/developers/applications), clique em
   **New Application**.
2. Em **OAuth2**, copie o **Client ID** e gere o **Client Secret** (*Reset Secret*; ele só aparece
   uma vez).
3. Ainda em OAuth2, em **Redirects**, adicione o endereço onde o app vai ficar, terminando em
   `/auth/callback` (ex: `https://facility-log.exemplo.ts.net/auth/callback`).
4. No Discord, ative **Configurações → Avançado → Modo desenvolvedor**. Depois, botão direito no
   servidor → **Copiar ID do servidor**; e botão direito no cargo que pode entrar (no seu perfil ou em
   Configurações do servidor → Cargos) → **Copiar ID**.

A tela "Verificação de aplicativo" do portal pode ser ignorada: verificação só é exigida de bots em
mais de 100 servidores.

### 2. Configurar

No servidor, crie uma pasta com o `docker-compose.yml` e o `.env.example` deste repositório (ou clone
o repositório) e copie o exemplo:

```bash
cp .env.example .env
nano .env
```

Preencha:

| Variável | O que é |
|---|---|
| `DISCORD_CLIENT_ID` | Client ID do app |
| `DISCORD_CLIENT_SECRET` | Client Secret do app |
| `DISCORD_REDIRECT_URI` | o mesmo endereço cadastrado em Redirects |
| `DISCORD_GUILD_ID` | ID do servidor do Discord |
| `DISCORD_ALLOWED_ROLE_IDS` | ID do cargo (vários separados por vírgula) |
| `SESSION_SECRET` | texto aleatório longo — gere com `openssl rand -base64 48` |
| `FACILITY_LOG_SECRET_KEY` | outro texto aleatório longo (protege webhooks e chaves salvos). **Guarde uma cópia**: sem ela os segredos salvos se perdem |

Proteja o arquivo: `chmod 600 .env`.

### 3. Subir

```bash
docker compose up -d
```

Baixa a imagem pronta (`ghcr.io/rlanak/facility-log`) e sobe o app em `127.0.0.1:8000` — só acessível
de dentro do servidor até você publicar. Os dados ficam em `./data-docker`. Se faltar alguma variável
do login, o app **se recusa a subir** (de propósito: nunca fica aberto sem login). Veja com
`docker compose logs`.

Prefere montar a imagem a partir do código? `docker build -t ghcr.io/rlanak/facility-log:latest .` na
pasta do repositório, e depois o mesmo `docker compose up -d`.

### 4. Publicar com HTTPS

**Tailscale Funnel** (grátis, sem domínio, sem abrir porta no roteador):

1. Crie uma conta em [tailscale.com](https://tailscale.com) e instale no servidor:
   `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`.
2. No painel do Tailscale: **DNS → HTTPS Certificates → Enable**, e garanta que a política de acesso
   dá o atributo `funnel` ao servidor.
3. `sudo tailscale funnel --bg 8000` — o endereço aparece na tela
   (`https://<nome>.<sua-rede>.ts.net`). É esse que vai no `DISCORD_REDIRECT_URI` e no Discord.

Quem acessa não instala nada: só abre o link no navegador.

**Cloudflare Tunnel** é a alternativa se você tem um domínio no Cloudflare: aponte o túnel pra
`http://127.0.0.1:8000`. Um proxy reverso com HTTPS (Caddy, Nginx) também funciona.

### Leitura de prints na web

O servidor lê os números com o **RapidOCR** (ou com IA por API, se configurada). Além disso, **cada
pessoa** pode usar a IA do **próprio computador**: em Configurações → **"IA do meu computador"**, o
navegador manda os recortes dos números pro Ollama do PC dela — o servidor nunca acessa o computador
de ninguém. Precisa do Ollama com `glm-ocr` e de liberar o endereço do site no Ollama
(`setx OLLAMA_ORIGINS "https://seu-endereco"` e reabrir o Ollama); o passo a passo aparece na própria
tela. Se a IA da pessoa não responder, a leitura do servidor assume.

Se o seu servidor tiver placa de vídeo e Ollama, `FACILITY_LOG_SERVER_OLLAMA=1` no `.env` libera a opção
"IA local" do próprio servidor pra todo mundo (fica escondida por padrão na web).

### Save do jogo na web

Cada pessoa envia o próprio arquivo `_MapData.sav`. No **Chrome e no Edge** o navegador lembra do
arquivo: depois da primeira vez é só **"Ler de novo"**. No Firefox ele fica lembrado enquanto a aba
estiver aberta.

### Atualizar

```bash
docker compose pull && docker compose up -d
```

### Backup

Copie a pasta `data-docker/` (banco, prints, ícones aprendidos) e guarde o `.env` à parte. Uma cópia
consistente com o app rodando:

```bash
docker compose exec -T -u app facility-log python -c "import sqlite3; s=sqlite3.connect('/data/facility_log.db'); d=sqlite3.connect('/data/backup.db'); s.backup(d)"
```

(gera `data-docker/backup.db`).

---

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Local: `python` não é reconhecido | Reinstale o Python marcando "Add python.exe to PATH" |
| Local: atalho não abre nada | Veja `data/facility_log.log`; se a porta 8000 estiver ocupada, defina `PORT=8001` num `.env` |
| Local: "403" ao abrir por outro PC ou por túnel | De propósito: sem login, o app só responde ao próprio PC. Pra web, configure o login do Discord |
| Web: container não sobe | `docker compose logs` — normalmente falta uma variável do `.env` |
| Web: erro no login do Discord | O `DISCORD_REDIRECT_URI` tem que ser **idêntico** ao cadastrado em Redirects (https, sem barra no fim) |
| Web: "sem permissão" no login | A conta não tem o cargo de `DISCORD_ALLOWED_ROLE_IDS` no servidor de `DISCORD_GUILD_ID` |
| Horário do relatório errado | Confira o fuso em Configurações → Fuso horário (o padrão é o do seu computador) |
| "Importar do save" diz "Leitor do save não encontrado" | Falta compilar o leitor do save (seção 4 do modo local). Na web, cada um envia o próprio arquivo `.sav` |

## Licença

MIT — ver [LICENSE](LICENSE).
