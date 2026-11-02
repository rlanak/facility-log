"""Checks every recipe in data/foxhole/building_types.json against the
building's wiki page (rendered tables via the MediaWiki API): time, input
quantities and output quantities. Prints only what differs. Item names that
are spelled differently on the wiki show up as "not found" — check those by
hand. Run from the project root after a game update.
"""

import html
import json
import re
import time
import urllib.parse
import urllib.request

bts = json.load(open("data/foxhole/building_types.json", encoding="utf-8"))
res = json.load(open("data/foxhole/resources.json", encoding="utf-8"))
name_of = {k: v["name"]["en"] for k, v in res.items()}


def clean(s):
    s = re.sub(r"<[^>]+>", " ", s)
    return html.unescape(re.sub(r"\s+", " ", s)).replace("\xa0", " ").strip()


def to_seconds(t):
    h, m, s = (int(x) for x in t.split(":"))
    return h * 3600 + m * 60 + s


def items(cell):
    # "2 x Construction Materials", "66L of Heavy Oil", "4MW of Power",
    # "10 of 15 x RPG" (10 crates of 15 = 150)
    out = {}
    pattern = r"(?:(\d+)\s+of\s+)?(\d[\d,.]*)\s*(?:x|L of)\s+(.+?)(?=\s+\d[\d,.]*\s*(?:x\s|L of|MW|of\s)|$)"
    for m in re.finditer(pattern, cell):
        crates = int(m.group(1)) if m.group(1) else 1
        out[m.group(3).strip().lower()] = crates * float(m.group(2).replace(",", ""))
    return out


problems = 0
checked = 0
for bt_key, bt in bts.items():
    if not bt["recipes"]:
        continue
    page = bt.get("wiki_url", "").rsplit("/", 1)[-1] or bt["name_en"].replace(" ", "_")
    url = f"https://foxhole.wiki.gg/api.php?action=parse&page={urllib.parse.quote(page)}&prop=text&format=json&formatversion=2"
    req = urllib.request.Request(url, headers={"User-Agent": "facility-log-audit"})
    t = json.loads(urllib.request.urlopen(req, timeout=60).read())["parse"]["text"]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) >= 3 and re.fullmatch(r"\d\d:\d\d:\d\d", cells[-1]):
            rows.append((items(cells[-3]), items(cells[-2]), to_seconds(cells[-1])))
    for r in bt["recipes"]:
        outq = {name_of.get(o.get("resource"), "").lower(): o["qty"] for o in r["outputs"] if o.get("resource")}
        outs = set(outq)
        ins = {name_of.get(i.get("resource"), "").lower(): i["qty"] for i in r["inputs"] if i.get("resource")}
        # Same outputs and same inputs: one building can have two recipes
        # with the same inputs (Coal Refinery base / Coke Furnace).
        cands = [row for row in rows if outs and outs == set(row[1])] or [
            row for row in rows if outs and outs <= set(row[1])
        ]
        exact = [row for row in cands if all(row[0].get(k) == v for k, v in ins.items())]
        for row in exact:
            if any(row[1].get(k) != v for k, v in outq.items()):
                print(f"≠ out {bt_key}/{r['key']}: catalog {outq} vs wiki {row[1]}")
        match = exact or cands
        checked += 1
        if not match:
            print(f"? {bt_key}/{r['key']}: not found on wiki ({sorted(outs)})")
            problems += 1
        elif not exact:
            print(f"≠ {bt_key}/{r['key']}: inputs catalog {ins} vs wiki {[c[0] for c in cands]}")
            problems += 1
        elif all(m[2] != r["time_seconds"] for m in match):
            print(f"✗ {bt_key}/{r['key']}: catalog {r['time_seconds']}s, wiki {[m[2] for m in match]}")
            problems += 1
    time.sleep(1)
print(f"{checked} recipes checked, {problems} to look at")
