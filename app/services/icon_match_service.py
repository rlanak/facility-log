"""Finds stockpile items inside a screenshot by matching the game's own icon
grid against the ~100 wiki-sourced icons in data/foxhole/resources.json,
instead of requiring a manual crop per item.

How a slot is found (reworked Nov 2026, measured on 12 real screenshots / 30
user-confirmed values — see CLAUDE.md "Detector de ícones"):

1. Match on *whiteness* (min of B,G,R), not grayscale. The item glyph is
   white; the slot behind it may be a yellow triangle (Sulfur), a blue
   diamond (Assembly Materials)... In grayscale a yellow background looks
   almost as bright as the glyph and Sulfur was never found; in whiteness
   any colored background goes dark and only the glyph remains.
2. Several candidate positions per catalog icon (not just its single best),
   and positions whose quantity corner has no white text are dropped up
   front: greyed-out slots are never stock, and they used to "steal" an icon
   (e.g. a grey row-3 slot took Assembly Materials I from the real one).
3. Greedy assignment by score, one slot per item and one item per slot.
4. Tiered items share one glyph and differ only by a small colored badge the
   game draws (Assembly Materials I-V). The wiki icons' badge art doesn't
   match the game's, so shape can't tell them apart. When near-identical
   icons tie at a spot, real crops of that item the user already confirmed
   ("exemplars", learned on save — see add_exemplar) decide, in color. With
   no exemplar for any rival, the slot is flagged ambiguous ("pode ser X")
   for the user to check.

Results stay a *pre-fill*, never an auto-save.
"""

import uuid
from functools import lru_cache
from pathlib import Path

from app.database import DATA_DIR
from app.paths import APP_DIR
from app.services import foxhole_data, ocr_service

WEB_DIR = APP_DIR / "web"
EXEMPLARS_DIR = DATA_DIR / "icon_exemplars"

# Candidate rendered glyph sizes to search, in px. Real screenshots tested so
# far rendered icons anywhere from ~44px (a hand-made low-res collage) to
# ~64px (native 2560x1080) — kept a bit wider on both ends for headroom.
SCALES = range(26, 74, 2)

SCORE_FLOOR = 0.80
# Icons scoring within this of the best at the same spot count as a tie.
TIE_MARGIN = 0.06
PEAKS_PER_ICON = 4
OVERLAP_PX = 18
# Exemplar color similarity needed, and lead over the runner-up, to settle a
# tie without asking the user.
EXEMPLAR_MIN = 0.6
EXEMPLAR_LEAD = 0.05


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


def _whiteness(bgr):
    return bgr.min(axis=2)


@lru_cache(maxsize=4096)
def _white_template(icon_path_str: str, size: int):
    """The glyph composited on black, as whiteness — what it looks like in
    the whiteness view of a slot, whatever the slot's background color."""
    import cv2
    import numpy as np

    icon = _load_icon(icon_path_str)
    resized = cv2.resize(icon, (size, size), interpolation=cv2.INTER_AREA).astype(np.float32)
    alpha = resized[:, :, 3:4] / 255.0
    return _whiteness((resized[:, :, :3] * alpha).astype(np.uint8))


# Share of near-white pixels in a slot's number box — the quantity is the
# only bright white thing in that corner. Measured over 1100+ candidate boxes
# in 32 real screenshots: real quantities >= 0.0126 (a lone "2"), greyed-out
# slots < 0.004 apart from one 0.0066. 0.02 (the first guess) dropped the "2".
WHITE_LEVEL = 225
MIN_WHITE_FRACTION = 0.01


def _has_white_text(img_bgr, box: tuple[int, int, int, int]) -> bool:
    import cv2

    x0, y0, x1, y1 = box
    crop = img_bgr[max(0, y0):y1, max(0, x0):x1]
    if crop.size == 0:
        return False
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float((gray > WHITE_LEVEL).mean()) >= MIN_WHITE_FRACTION


def _number_box(loc: tuple[int, int], size: int) -> tuple[int, int, int, int]:
    # The quantity sits in the lower portion of the slot, overlapping the
    # icon glyph's own bottom edge by an amount that varies per icon -- there's
    # no single ratio that clears every icon's footprint exactly. Biased
    # toward starting low enough to usually clear the icon, since an empty read
    # (obviously wrong, gets filled in by hand) is a safer failure than a stray
    # icon pixel read as a digit.
    # Left edge at -0.25 (was -0.10): icons a mod draws inside a circle match
    # a bit right of the slot, and "258" came back as "58".
    lx, ly = loc
    return (
        max(0, round(lx - size * 0.25)),
        max(0, round(ly + size * 0.62)),
        round(lx + size * 1.15),
        round(ly + size * 1.25),
    )


# --- Exemplars: real crops of confirmed items ---------------------------------


def add_exemplar(image_path: Path, box: tuple[int, int, int, int], resource_def_key: str) -> None:
    """Saves the icon crop of a slot the user confirmed as `resource_def_key`
    (called when OCR results are saved). Keeps the last few per item."""
    from PIL import Image

    folder = EXEMPLARS_DIR / resource_def_key
    folder.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as img:
        img.convert("RGB").crop(box).save(folder / f"{uuid.uuid4().hex}.png")
    existing = sorted(folder.glob("*.png"), key=lambda p: p.stat().st_mtime)
    for old in existing[:-8]:
        old.unlink()
    _exemplars.cache_clear()


@lru_cache(maxsize=1)
def _exemplars() -> dict[str, list]:
    import cv2

    result: dict[str, list] = {}
    if not EXEMPLARS_DIR.is_dir():
        return result
    for folder in EXEMPLARS_DIR.iterdir():
        crops = [cv2.imread(str(p)) for p in folder.glob("*.png")]
        crops = [c for c in crops if c is not None]
        if crops:
            result[folder.name] = crops
    return result


# Where tiered items differ: the game's tier badge in the icon's top-left
# corner (x0, y0, x1, y1 as fractions of the icon box). The rest of the icon
# is the same glyph on the same colored shape — compared whole, an Assembly
# Materials I slot scored 0.97 against a real AM I crop and 0.94 against AM II,
# too close to call; the corner is what tells them apart.
BADGE_REGION = (0.0, 0.0, 0.5, 0.45)


def _badge(img):
    h, w = img.shape[:2]
    bx0, by0, bx1, by1 = BADGE_REGION
    return img[int(h * by0):int(h * by1), int(w * bx0):int(w * bx1)]


def _exemplar_similarity(patch, crops) -> float:
    """Best color correlation, on the tier-badge corner, between a slot patch
    and any exemplar crop of one item."""
    import cv2
    import numpy as np

    size = patch.shape[1], patch.shape[0]
    a = _badge(patch).astype(np.float32).ravel()
    a -= a.mean()
    best = -1.0
    for crop in crops:
        b = _badge(cv2.resize(crop, size, interpolation=cv2.INTER_AREA)).astype(np.float32).ravel()
        b -= b.mean()
        denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
        if denom:
            best = max(best, float((a * b).sum()) / denom)
    return best


def detect_items(image_path: Path, box: tuple[int, int, int, int], read_number=None) -> list[dict]:
    """box is (x0, y0, x1, y1) in the full screenshot's own pixel space,
    covering the STOCKPILE > ITEMS panel the user selected. `read_number(path,
    box)` reads one quantity (defaults to Tesseract). Returns one dict per
    slot that shows a quantity, sorted top-to-bottom/left-to-right."""
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        return []
    height, width = img.shape[:2]
    x0, y0, x1, y1 = box
    x0, x1 = sorted((max(0, min(x0, width)), max(0, min(x1, width))))
    y0, y1 = sorted((max(0, min(y0, height)), max(0, min(y1, height))))
    panel_bgr = img[y0:y1, x0:x1]
    if panel_bgr.size == 0:
        return []
    panel = _whiteness(panel_bgr)

    # (score, key, name_en, name_pt, size, loc) — several positions per icon.
    candidates = []
    for key, name_en, name_pt, icon_path in _catalog():
        icon = _load_icon(str(icon_path))
        if icon is None or icon.ndim < 3 or icon.shape[2] < 4:
            continue
        best_size, best_res, best_val = None, None, -1.0
        for size in SCALES:
            if size >= panel.shape[0] or size >= panel.shape[1]:
                continue
            res = cv2.matchTemplate(panel, _white_template(str(icon_path), size), cv2.TM_CCOEFF_NORMED)
            val = float(res.max())
            if val > best_val:
                best_size, best_res, best_val = size, res, val
        if best_res is None:
            continue
        res = best_res.copy()
        half = best_size // 2
        for _ in range(PEAKS_PER_ICON):
            _, val, _, loc = cv2.minMaxLoc(res)
            if val < SCORE_FLOOR - TIE_MARGIN:
                break
            cv2.rectangle(res, (loc[0] - half, loc[1] - half), (loc[0] + half, loc[1] + half), -1, -1)
            if _has_white_text(panel_bgr, _number_box(loc, best_size)):
                candidates.append((val, key, name_en, name_pt, best_size, loc))

    # Learned exemplars are templates too: they are the item as *this* user's
    # game draws it — the only way to find icons a mod redraws (Typhon,
    # Lamentum, flame ammo... scored 0.57-0.75 against the wiki art).
    exemplars = _exemplars()
    defs = foxhole_data.get_resource_defs()
    for key, crops in exemplars.items():
        if key not in defs:
            continue
        name_en, name_pt = defs[key]["name"]["en"], defs[key]["name"].get("pt")
        for crop in crops:
            tmpl = _whiteness(crop)
            size = tmpl.shape[1]
            if tmpl.shape[0] >= panel.shape[0] or size >= panel.shape[1] or tmpl.std() < 1:
                continue
            res = cv2.matchTemplate(panel, tmpl, cv2.TM_CCOEFF_NORMED)
            half = size // 2
            for _ in range(PEAKS_PER_ICON):
                _, val, _, loc = cv2.minMaxLoc(res)
                if val < SCORE_FLOOR:
                    break
                cv2.rectangle(res, (loc[0] - half, loc[1] - half), (loc[0] + half, loc[1] + half), -1, -1)
                if _has_white_text(panel_bgr, _number_box(loc, size)):
                    candidates.append((float(val), key, name_en, name_pt, size, loc))

    candidates.sort(key=lambda c: -c[0])

    def overlaps(a, b):
        return abs(a[0] - b[0]) < OVERLAP_PX and abs(a[1] - b[1]) < OVERLAP_PX

    # Group candidates by slot (position), then decide what each slot holds.
    slots: list[list] = []
    for cand in candidates:
        for slot in slots:
            if overlaps(cand[5], slot[0][5]):
                slot.append(cand)
                break
        else:
            slots.append([cand])
    slots = [s for s in slots if s[0][0] >= SCORE_FLOOR]

    # Per slot: an ordered preference of items. Near-identical icons tying
    # with the best are re-ordered by exemplars (real confirmed crops) when
    # there are any; `settled` says whether the order can be trusted.
    plans = []  # (priority, prefs, settled, tied_keys)
    for slot in slots:
        top_score = slot[0][0]
        tied = [c for c in slot if c[0] >= top_score - TIE_MARGIN]
        rest = [c for c in slot if c[0] < top_score - TIE_MARGIN]
        settled, priority = len(tied) == 1, top_score
        if not settled and any(c[1] in exemplars for c in tied):
            lx, ly = slot[0][5]
            size0 = slot[0][4]
            patch = panel_bgr[ly:ly + size0, lx:lx + size0]
            ranked = sorted(
                ((_exemplar_similarity(patch, exemplars[c[1]]) if c[1] in exemplars else -1.0, c) for c in tied),
                key=lambda t: -t[0],
            )
            tied = [c for _, c in ranked]
            runner = ranked[1][0] if len(ranked) > 1 else -1.0
            if ranked[0][0] >= EXEMPLAR_MIN and ranked[0][0] - runner >= EXEMPLAR_LEAD:
                # An exemplar-confirmed slot claims its item before slots
                # that only won on glyph score.
                settled, priority = True, 1.0 + ranked[0][0]
        plans.append((priority, tied + rest, settled, {c[1] for c in tied}))

    def read(loc, size):
        nb = _number_box(loc, size)
        nb = (x0 + nb[0], y0 + nb[1], x0 + nb[2], y0 + nb[3])
        # read_number: the user's chosen engine (services/capture) — icon
        # matching only decides *which* item; reading the digits is pluggable.
        if read_number:
            return read_number(image_path, nb)
        return ocr_service.read_crop(image_path, nb, psm=11)

    used_keys: set[str] = set()
    assigned: list[tuple[tuple[int, int], int]] = []
    detected = []
    for _priority, prefs, settled, tied_keys in sorted(plans, key=lambda p: -p[0]):
        choice = next((c for c in prefs if c[1] not in used_keys), None)
        if choice is None:
            continue
        score, key, name_en, name_pt, size, loc = choice
        # A tie no exemplar settled stays flagged even when the other tied
        # items were already given to other slots — the elimination may have
        # been wrong too, and silently confident is the worst outcome.
        other_tied = [c for c in prefs if c[1] in tied_keys and c[1] != key]
        ambiguous = not settled and bool(other_tied)
        rival = next((c for c in other_tied if c[1] not in used_keys), other_tied[0] if other_tied else None) if ambiguous else None
        used_keys.add(key)
        assigned.append((loc, size))
        ocr = read(loc, size)
        detected.append(
            {
                "resource_def_key": key,
                "name_en": name_en,
                "name_pt": name_pt,
                "confidence": round(float(score), 4),
                "ambiguous": ambiguous,
                "rival_key": rival[1] if rival else None,
                "rival_name_en": rival[2] if rival else None,
                "quantity_raw": ocr.get("raw_text", ""),
                "quantity_guess": ocr.get("guess", ""),
                "box_x": x0 + loc[0],
                "box_y": y0 + loc[1],
                "box_width": size,
                "box_height": size,
            }
        )

    # Grid fallback: a slot that shows a quantity but that no catalog icon or
    # exemplar explained (a mod redrew the icon, or the item isn't in the
    # catalog) is still returned — as "unknown", with its quantity read — so
    # no number is silently dropped. The user picks the item, and on save the
    # slot becomes an exemplar, so the next screenshot recognizes it.
    for loc, size in _grid_slots(assigned, panel.shape):
        if any(overlaps(loc, a) for a, _ in assigned):
            continue
        if not _has_white_text(panel_bgr, _number_box(loc, size)):
            continue
        guess = next(
            (c for c in candidates if overlaps(c[5], loc) and c[1] not in used_keys and c[0] >= SCORE_FLOOR - TIE_MARGIN),
            None,
        )
        assigned.append((loc, size))
        ocr = read(loc, size)
        detected.append(
            {
                "resource_def_key": guess[1] if guess else None,
                "name_en": guess[2] if guess else None,
                "name_pt": guess[3] if guess else None,
                "confidence": round(float(guess[0]), 4) if guess else 0.0,
                "ambiguous": True,
                "rival_key": None,
                "rival_name_en": None,
                "quantity_raw": ocr.get("raw_text", ""),
                "quantity_guess": ocr.get("guess", ""),
                "box_x": x0 + loc[0],
                "box_y": y0 + loc[1],
                "box_width": size,
                "box_height": size,
            }
        )

    detected.sort(key=lambda d: (d["box_y"], d["box_x"]))
    return detected


def _grid_slots(assigned: list[tuple[tuple[int, int], int]], panel_shape) -> list[tuple[tuple[int, int], int]]:
    """Every slot position of the stockpile grid, inferred from the slots
    already recognized (the grid is regular: same icon size, same pitch).
    Needs at least two recognized slots to know the pitch; when only the
    column (or row) pitch is known, the grid is assumed square."""
    import statistics

    if len(assigned) < 2:
        return []
    size = int(statistics.median(s for _, s in assigned))

    def pitch(values):
        values = sorted(values)
        clusters = [values[0]]
        for v in values[1:]:
            if v - clusters[-1] > size * 0.5:
                clusters.append(v)
        diffs = [b - a for a, b in zip(clusters, clusters[1:]) if b - a > size * 0.8]
        return min(diffs) if diffs else None

    dx = pitch([loc[0] for loc, _ in assigned])
    dy = pitch([loc[1] for loc, _ in assigned])
    dx, dy = dx or dy, dy or dx
    if not dx:
        return []
    ox, oy = assigned[0][0]
    height, width = panel_shape[:2]
    xs = [ox + i * dx for i in range(-20, 21) if 0 <= ox + i * dx <= width - size]
    ys = [oy + j * dy for j in range(-20, 21) if 0 <= oy + j * dy <= height - size]
    return [((x, y), size) for y in ys for x in xs]
