"""Finds stockpile items inside a screenshot by matching the game's own icon
grid against the ~100 wiki-sourced icons in data/foxhole/resources.json,
instead of requiring a manual crop per item.

How a slot is scored: each catalog icon (a plain white glyph on transparent
background) is composited onto a flat gray matching the panel's own
background, resized across a range of candidate sizes, and correlated
against the user-selected region with cv2.matchTemplate. Validated by hand
against several real screenshots (see project memory) — grayscale matching
degrades gracefully (a score far below every rival) when an item genuinely
isn't in the catalog, but two failure modes are real and expected, not bugs:
tiered items that share one colorless glyph (e.g. Assembly Materials I-V)
can tie within a hair of each other, and the smaller the rendered icon, the
more a wrong-but-similarly-shaped icon can win with unwarranted confidence.
The margin check below is the guard for the first; there's no cheap guard
for the second, which is why results stay a *pre-fill*, not an auto-save.
"""

from functools import lru_cache
from pathlib import Path

from app.services import foxhole_data, ocr_service

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"

# Candidate rendered glyph sizes to search, in px. Real screenshots tested so
# far rendered icons anywhere from ~44px (a hand-made low-res collage) to
# ~64px (native 2560x1080) — kept a bit wider on both ends for headroom.
SCALES = range(26, 74, 2)

SCORE_FLOOR = 0.80
AMBIGUOUS_MARGIN = 0.03
OVERLAP_PX = 18


@lru_cache(maxsize=1)
def is_available() -> bool:
    try:
        import cv2  # noqa: F401
        import numpy  # noqa: F401
    except Exception:
        return False
    return True


@lru_cache(maxsize=1)
def _catalog() -> list[tuple[str, str, str | None, Path]]:
    items = []
    for key, entry in foxhole_data.get_resource_defs().items():
        icon_rel = entry.get("icon")
        if not icon_rel:
            continue
        icon_path = WEB_DIR / icon_rel.lstrip("/")
        if not icon_path.is_file():
            continue
        items.append((key, entry["name"]["en"], entry["name"].get("pt"), icon_path))
    return items


@lru_cache(maxsize=256)
def _load_icon(icon_path_str: str):
    import cv2

    return cv2.imread(icon_path_str, cv2.IMREAD_UNCHANGED)


def _sample_bg_value(panel_gray) -> float:
    import numpy as np

    # Median over the whole region, not a small corner patch -- a corner can
    # land on a slot's near-black border and throw the composited background
    # off enough to tank every match score.
    return float(np.median(panel_gray))


def _composite_icon(icon_rgba, size: int, bg_value: float):
    import cv2
    import numpy as np

    resized = cv2.resize(icon_rgba, (size, size), interpolation=cv2.INTER_AREA)
    bgr = resized[:, :, :3].astype(np.float32)
    alpha = resized[:, :, 3:4].astype(np.float32) / 255.0
    bg = np.full_like(bgr, bg_value)
    composite = bgr * alpha + bg * (1 - alpha)
    return cv2.cvtColor(composite.astype(np.uint8), cv2.COLOR_BGR2GRAY)


def detect_items(image_path: Path, box: tuple[int, int, int, int]) -> list[dict]:
    """box is (x0, y0, x1, y1) in the full screenshot's own pixel space,
    covering the STOCKPILE > ITEMS panel the user selected. Returns one dict
    per confidently-identified slot, sorted top-to-bottom/left-to-right."""
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        return []
    height, width = img.shape[:2]
    x0, y0, x1, y1 = box
    x0, x1 = sorted((max(0, min(x0, width)), max(0, min(x1, width))))
    y0, y1 = sorted((max(0, min(y0, height)), max(0, min(y1, height))))
    panel = img[y0:y1, x0:x1]
    if panel.size == 0:
        return []
    panel_gray = cv2.cvtColor(panel, cv2.COLOR_BGR2GRAY)
    bg_value = _sample_bg_value(panel_gray)

    results = []
    for key, name_en, name_pt, icon_path in _catalog():
        icon_rgba = _load_icon(str(icon_path))
        if icon_rgba is None or icon_rgba.shape[2] < 4:
            continue
        best = None
        for size in SCALES:
            if size >= panel_gray.shape[0] or size >= panel_gray.shape[1]:
                continue
            tmpl = _composite_icon(icon_rgba, size, bg_value)
            res = cv2.matchTemplate(panel_gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if best is None or max_val > best[0]:
                best = (max_val, size, max_loc)
        if best is not None:
            results.append((best[0], key, name_en, name_pt, best[1], best[2]))

    results.sort(key=lambda r: -r[0])

    def overlaps(a, b):
        return abs(a[0] - b[0]) < OVERLAP_PX and abs(a[1] - b[1]) < OVERLAP_PX

    used_locs: list[tuple[int, int]] = []
    detected = []
    for score, key, name_en, name_pt, size, loc in results:
        if score < SCORE_FLOOR:
            continue
        if any(overlaps(loc, used) for used in used_locs):
            continue
        used_locs.append(loc)

        rivals = [r for r in results if r[1] != key and overlaps(r[5], loc)]
        margin = (score - rivals[0][0]) if rivals else 1.0
        ambiguous = margin < AMBIGUOUS_MARGIN

        lx, ly = loc
        # The quantity sits in the lower portion of the slot, overlapping the
        # icon glyph's own bottom edge by an amount that varies per icon (a
        # bulkier icon silhouette reaches further down than a slim one) --
        # there's no single ratio that clears every icon's footprint exactly.
        # Biased toward starting low enough to usually clear the icon, since
        # an empty OCR read (obviously wrong, gets manually filled in) is a
        # safer failure than a wrong-looking number from a stray icon pixel
        # getting read as a stray digit.
        number_box = (
            x0 + max(0, round(lx - size * 0.10)),
            y0 + max(0, round(ly + size * 0.62)),
            x0 + round(lx + size * 1.15),
            y0 + round(ly + size * 1.25),
        )
        # psm 11 ("sparse text"), not the manual-crop flow's psm 7 ("single
        # line") -- this box is a heuristic estimate that can still catch a
        # sliver of icon, and psm 7 reads that as garbling the line and
        # returns nothing, where psm 11 just picks the digit cluster out and
        # ignores the rest. Confirmed against a real screenshot: psm 7 came
        # back empty, psm 11 read "5.1K" correctly.
        ocr = ocr_service.read_crop(image_path, number_box, psm=11)

        detected.append(
            {
                "resource_def_key": key,
                "name_en": name_en,
                "name_pt": name_pt,
                "confidence": round(float(score), 4),
                "ambiguous": ambiguous,
                "rival_key": rivals[0][1] if ambiguous and rivals else None,
                "rival_name_en": rivals[0][2] if ambiguous and rivals else None,
                "quantity_raw": ocr.get("raw_text", ""),
                "quantity_guess": ocr.get("guess", ""),
                "box_x": x0 + lx,
                "box_y": y0 + ly,
                "box_width": size,
                "box_height": size,
            }
        )

    detected.sort(key=lambda d: (d["box_y"], d["box_x"]))
    return detected
