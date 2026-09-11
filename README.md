# facility-log

App local para gerar relatórios de estoque de facilities do Foxhole, formatados em Markdown
prontos para colar no Discord.

Projeto pessoal — roda 100% local, sem serviços pagos, sem deploy.

## Como rodar

### Pré-requisito

Python 3.11 ou 3.12 instalado (baixe em [python.org/downloads](https://www.python.org/downloads/) —
marque "Add python.exe to PATH" na instalação). Confirme com `python --version` antes de seguir;
se o comando não for reconhecido, o Python não está instalado ou não está no PATH.

### Rodar

Windows (PowerShell ou Git Bash):

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe run.py
```

Abra http://localhost:8000

### OCR automático (opcional)

O recorte manual de prints funciona sem nenhuma dependência extra. Se você também quiser que o
valor do recorte venha pré-preenchido via OCR, instale o Tesseract:

```bash
winget install UB-Mannheim.TesseractOCR
```

Reinicie o `run.py` depois de instalar. Sem o Tesseract, o app detecta isso automaticamente e
mostra um aviso — o fluxo de recorte + digitação manual continua funcionando normalmente.

## Estrutura

- `app/` — backend FastAPI (SQLite via SQLAlchemy)
  - `models.py` / `schemas.py` / `crud.py` — dados
  - `routers/` — endpoints da API (`images.py` cuida de upload de prints e OCR)
  - `services/report_generator.py` — geração do relatório em Markdown e recomendação de farm
  - `services/number_parser.py` — interpreta valores tipo `25.7k`, `1,8k`, `32000`
  - `services/ocr_service.py` — leitura de recortes via Tesseract, com fallback gracioso se não estiver instalado
- `web/` — frontend estático (HTML/JS puro + Tailwind via CDN), servido pelo próprio FastAPI
  - `js/views/print.js` — upload de print + ferramenta de recorte (drag-to-crop) + confirmação manual do valor lido
- `data/` — banco SQLite e uploads de prints (gitignored)

## Status

- [x] Fase 1 — CRUD de facilities/prédios/catálogo de recursos + lançamento manual de estoque
- [x] Fase 2 — geração de relatório em Markdown, recomendação de farm, split automático pro limite de 2000 caracteres do Discord, histórico
- [x] Fase 3 — upload de print, recorte manual (drag-to-crop) com valor sempre confirmável antes de salvar, OCR automático via Tesseract quando disponível
