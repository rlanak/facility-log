"""Copies a portable subset of a local Tesseract-OCR install into vendor/tesseract/
so facility_log.spec can bundle it into the standalone .exe — end users then don't
need to install Tesseract themselves (see CLAUDE.md, "Empacotamento").

Run once before building the .exe (re-run if Tesseract gets upgraded):

    .venv/Scripts/python.exe scripts/prepare_tesseract_vendor.py

Only eng.traineddata is copied — ocr_service.py's whitelist is digits/k/m only
(see number_parser.py), so no other language data is ever read.
"""

import shutil
import sys
from pathlib import Path

DEFAULT_SOURCE = Path(r"C:\Program Files\Tesseract-OCR")
DEST = Path(__file__).resolve().parent.parent / "vendor" / "tesseract"


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    tesseract_exe = source / "tesseract.exe"
    eng_data = source / "tessdata" / "eng.traineddata"
    if not tesseract_exe.is_file() or not eng_data.is_file():
        raise SystemExit(
            f"Tesseract not found at {source}. Install it (winget install "
            f"UB-Mannheim.TesseractOCR) or pass its folder as an argument."
        )

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    (DEST / "tessdata").mkdir()

    shutil.copy2(tesseract_exe, DEST / "tesseract.exe")
    for dll in source.glob("*.dll"):
        shutil.copy2(dll, DEST / dll.name)
    shutil.copy2(eng_data, DEST / "tessdata" / "eng.traineddata")

    dll_count = len(list(DEST.glob("*.dll")))
    size_mb = sum(f.stat().st_size for f in DEST.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"Copied tesseract.exe + {dll_count} DLLs + eng.traineddata into {DEST} ({size_mb:.0f} MB)")


if __name__ == "__main__":
    main()
