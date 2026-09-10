# facility-log

App local para gerar relatórios de estoque de facilities do Foxhole, formatados em Markdown
prontos para colar no Discord.

Projeto pessoal — roda 100% local, sem serviços pagos, sem deploy.

## Como rodar

Windows (PowerShell ou Git Bash):

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

Abra http://localhost:8000

## Estrutura

- `app/` — backend FastAPI (SQLite via SQLAlchemy)
  - `models.py` / `schemas.py` / `crud.py` — dados
  - `routers/` — endpoints da API
  - `services/report_generator.py` — geração do relatório em Markdown e recomendação de farm
  - `services/number_parser.py` — interpreta valores tipo `25.7k`, `1,8k`, `32000`
- `web/` — frontend estático (HTML/JS puro + Tailwind via CDN), servido pelo próprio FastAPI
- `data/` — banco SQLite e uploads de prints (gitignored)

## Status

- [x] Fase 1 — CRUD de facilities/prédios/catálogo de recursos + lançamento manual de estoque
- [x] Fase 2 — geração de relatório em Markdown, recomendação de farm, split automático pro limite de 2000 caracteres do Discord, histórico
- [ ] Fase 3 — upload de print + recorte manual + OCR (Tesseract)
