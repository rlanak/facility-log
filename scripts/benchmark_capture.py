"""Measures screenshot capture (icon detection + number reading) against an
answer key, so a change to the detector or a new reader/model can be judged
on real screenshots instead of by eye.

Answer key lives next to the screenshots, in print/ (gitignored — the
screenshots show real player/clan names):
    print/truth.json  {"print/mod/x.jpg": {"<resource_def_key>": <quantity>, ...}, ...}
    print/boxes.json  {"print/mod/x.jpg": [x0, y0, x1, y1], ...}   the STOCKPILE panel
Subfolders name the icon style (print/mod/, print/vanilla/) and are scored
separately. Learned exemplars in data/icon_exemplars/ are used as-is — don't
seed them from the same screenshots you measure, or the score is inflated.

    .venv/Scripts/python.exe scripts/benchmark_capture.py rapidocr
    .venv/Scripts/python.exe scripts/benchmark_capture.py glm-ocr:latest      (any Ollama model)
    .venv/Scripts/python.exe scripts/benchmark_capture.py tesseract

Prints every miss and, per style: values read correctly, values found only as
an "unrecognized item" with the right number (the user picks the item), and
wrong items that were added.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import icon_match_service, number_parser, ocr_service  # noqa: E402
from app.services.capture import readers  # noqa: E402

OLLAMA_URL = "http://127.0.0.1:11434"


def _reader(engine: str):
    if engine == "tesseract":
        return lambda path, box: ocr_service.read_crop(path, box, psm=11)
    if engine == "rapidocr":
        return readers.read_rapidocr
    return lambda path, box: readers.read_ollama(path, box, OLLAMA_URL, engine)


def _value(text: str) -> float | None:
    try:
        return number_parser.parse_quantity(text or "")
    except ValueError:
        return None


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    engine = sys.argv[1]
    truth = json.loads((ROOT / "print" / "truth.json").read_text(encoding="utf-8"))
    boxes = json.loads((ROOT / "print" / "boxes.json").read_text(encoding="utf-8"))
    reader = _reader(engine)

    stats: dict[str, list[int]] = {}  # style -> [correct, total, surfaced_unknown, wrong_extra]
    started = time.time()
    for rel, expected in truth.items():
        style = Path(rel).parent.name
        items = icon_match_service.detect_items(ROOT / rel, tuple(boxes[rel]), read_number=reader)
        got = {i["resource_def_key"]: (i["quantity_raw"] if i["quantity_guess"] else "") for i in items if i["resource_def_key"]}
        unknown = [_value(i["quantity_raw"] if i["quantity_guess"] else "") for i in items if not i["resource_def_key"]]
        s = stats.setdefault(style, [0, 0, 0, 0])
        for key, qty in expected.items():
            s[1] += 1
            value = _value(got.get(key))
            if value is not None and abs(value - qty) < 1e-6:
                s[0] += 1
            elif key not in got and any(u is not None and abs(u - qty) < 1e-6 for u in unknown):
                s[2] += 1
                print(f"  {rel}: {key}={qty} found as an unrecognized item")
            else:
                print(f"  {rel}: {key} expected {qty}, got {got.get(key)!r}")
        extra = {k: v for k, v in got.items() if k not in expected and v}
        s[3] += len(extra)
        if extra:
            print(f"  {rel}: wrong extra items {extra}")

    for style, (correct, total, surfaced, extra) in stats.items():
        print(f"== {engine} [{style}]: {correct}/{total} correct, +{surfaced} as unrecognized item, {extra} wrong extra")
    print(f"   {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
