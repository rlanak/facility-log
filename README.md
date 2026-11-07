# facility-log

Relatórios de estoque das facilities do **Foxhole**, prontos pra colar no Discord: estoque por prédio,
total da facility, estimativa de produção e o que falta produzir ou farmar pra bater as Metas.

- Lançamento de estoque à mão, por **print** do painel STOCKPILE (detecção automática dos itens) ou
  pelo **save do jogo** (locais pinados no mapa). Valor lido nunca salva sem você confirmar.
- Aba "Ao vivo" com estimativa do estoque pelas filas de produção, e painel no Discord por webhook.
- Roda **local** (sem conta, sem serviço pago) ou na **web** com login pelo Discord, liberado por cargo.

## Rodar local (Windows)

Precisa de Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

Abra http://localhost:8000.

Opcionais:
- `scripts/create_shortcut.py` — atalho na área de trabalho que abre o app com ícone na bandeja, sem
  janela de console.
- `scripts/build_save_parser.py` — compila o leitor do save (precisa do Rust/`cargo`). Só o "Importar
  do save" depende dele.
- Leitura de prints: RapidOCR já vem instalado. Dá pra trocar em ⚙️ Configurações por IA local
  (Ollama), IA por API (com a sua chave) ou Tesseract.

## Rodar na web

Copie `.env.example` para `.env` e preencha (app do Discord, servidor, cargos e segredos), depois:

```bash
docker compose up -d --build
```

O app sobe em `127.0.0.1:8000`; publique por um túnel (Cloudflare Tunnel, Tailscale Funnel) ou proxy
reverso com HTTPS. Sem o login do Discord configurado, a imagem Docker se recusa a subir.

## Licença

MIT — ver [LICENSE](LICENSE).
