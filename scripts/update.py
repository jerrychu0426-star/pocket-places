#!/usr/bin/env python3
"""Pocket-places pipeline.

  python3 -I scripts/update.py merge <takeout.csv>   add new saved places, drop removed ones
  python3 -I scripts/update.py geocode               look up places that have no coordinates yet
  python3 -I scripts/update.py recheck               refresh business status of every known place
  python3 -I scripts/update.py parking               find the nearest parking lot for places missing one
  python3 -I scripts/update.py report                list places needing human/Claude review
  python3 -I scripts/update.py build                 regenerate index.html and places.csv

Data lives in data/places.json. The Places API key is injected by the network proxy
(network secret for places.googleapis.com, header X-Goog-Api-Key); the dummy key below is replaced.
"""
import csv, datetime, json, os, re, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "places.json")
TODAY = datetime.date.today().isoformat()
PENDING = "待分類"
STATUS_ZH = {"OPERATIONAL": "營業中", "CLOSED_PERMANENTLY": "已歇業", "CLOSED_TEMPORARILY": "暫停營業"}


def load():
    return json.load(open(DATA, encoding="utf-8"))


def save(d):
    json.dump(d, open(DATA, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def api(url, body=None, mask=""):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json", "X-Goog-FieldMask": mask,
                                          "X-Goog-Api-Key": "injected-by-proxy"})
    return json.load(urllib.request.urlopen(req, timeout=20))


T = str.maketrans({"臺": "台", "园": "園", "芦": "蘆", "区": "區", "龙": "龍", "县": "縣"})


def region(addr):
    a = (addr or "").translate(T)
    m = re.search(r"(台北|新北|桃園|台中|台南|高雄|基隆|新竹|嘉義|宜蘭|苗栗|彰化|南投|雲林|屏東|花蓮|台東)[市縣](.{1,3}?[區鄉鎮市])", a)
    return m.group(1) + m.group(2) if m else None


def merge(path):
    d = load()
    have = {p["url"]: p for p in d}
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig")) if (r.get("標題") or "").strip()]
    urls = set()
    added = []
    for r in rows:
        u = r["網址"].strip()
        urls.add(u)
        if u in have:
            if (r.get("筆記") or "").strip() and not have[u].get("note"):
                have[u]["note"] = "你的筆記：" + r["筆記"].strip().replace("\n", "；")
            continue
        p = dict(name=r["標題"].strip(), region="", type=PENDING, occ=PENDING, price="?",
                 note=("你的筆記：" + r["筆記"].strip().replace("\n", "；")) if (r.get("筆記") or "").strip() else "",
                 url=u, pid=None, gname=None, addr=None, lat=None, lng=None, status=None, nomatch=False, checked=None, reviewed=False)
        d.append(p)
        added.append(p["name"])
    removed = [p["name"] for p in d if p["url"] not in urls]
    d = [p for p in d if p["url"] in urls]
    save(d)
    print(f"export rows {len(rows)} | added {len(added)} | removed {len(removed)} | total {len(d)}")
    for n in added: print("  + " + n)
    for n in removed: print("  - " + n)


def geocode():
    d = load()
    mask = "places.id,places.displayName,places.formattedAddress,places.location,places.businessStatus"
    n = 0
    for p in d:
        if p.get("lat") is not None or p.get("nomatch"):
            continue
        q = p["name"] + (" " + p["region"] if p.get("region") else "")
        try:
            res = api("https://places.googleapis.com/v1/places:searchText",
                      {"textQuery": q, "languageCode": "zh-TW", "regionCode": "TW", "pageSize": 1}, mask)
        except urllib.error.HTTPError as e:
            sys.exit(f"Places API error {e.code}: {e.read()[:300]!r}")
        g = (res.get("places") or [None])[0]
        if not g:
            p["nomatch"] = True
        else:
            p.update(pid=g["id"], gname=g["displayName"]["text"], addr=g.get("formattedAddress"),
                     lat=g["location"]["latitude"], lng=g["location"]["longitude"], status=g.get("businessStatus"))
            p["region"] = region(p["addr"]) or p.get("region") or ""
        p["checked"] = TODAY
        n += 1
        print(f"  {p['name']} -> {p.get('gname')} | {p.get('addr')} | {p.get('status')}")
        time.sleep(0.1)
    save(d)
    print(f"geocoded {n}")


def recheck():
    d = load()
    changed = []
    for p in d:
        if not p.get("pid"):
            continue
        try:
            g = api(f"https://places.googleapis.com/v1/places/{p['pid']}", mask="businessStatus")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                g = {"businessStatus": "CLOSED_PERMANENTLY"}
            else:
                sys.exit(f"Places API error {e.code}: {e.read()[:300]!r}")
        s = g.get("businessStatus")
        if s and s != p.get("status"):
            changed.append(f"{p['name']}: {STATUS_ZH.get(p.get('status'), p.get('status'))} -> {STATUS_ZH.get(s, s)}")
            p["status"] = s
        p["checked"] = TODAY
        time.sleep(0.05)
    save(d)
    print(f"status changes: {len(changed)}")
    for c in changed: print("  " + c)


def report():
    norm = lambda s: re.sub(r"[\s（）()\-_|｜·．.、,，/&]", "", s or "").lower()
    for p in load():
        if p.get("reviewed"): continue
        why = []
        if PENDING in (p["type"], p["occ"]): why.append("needs type/occasion/price")
        if p.get("nomatch"): why.append("no Google match")
        elif p.get("gname"):
            a, b = norm(p["name"]), norm(p["gname"])
            if a[:3] not in b and b[:3] not in a: why.append(f"name mismatch: Google says {p['gname']!r} at {p.get('addr')}")
        if why: print(f"- {p['name']} [{p['url'][-40:]}]: " + "; ".join(why))


def build():
    d = load()
    view = [dict(name=p["name"], region=p["region"], type=p["type"], occ=p["occ"], price=p["price"], note=p["note"],
                 url=p["url"], pid=p.get("pid"), status=p.get("status"), park=p.get("parking"),
                 lat=None if p.get("nomatch") or p.get("lat") is None else round(p["lat"], 6),
                 lng=None if p.get("nomatch") or p.get("lng") is None else round(p["lng"], 6)) for p in d]
    # last date the data actually changed or was rechecked; stable across no-op weekly runs
    updated = max((p.get("checked") or "" for p in d), default=TODAY) or TODAY
    tpl = open(os.path.join(ROOT, "scripts", "template.html"), encoding="utf-8").read()
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(
        tpl.replace("__DATA__", json.dumps(view, ensure_ascii=False)).replace("__UPDATED__", updated))
    with open(os.path.join(ROOT, "data", "places.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["店名", "區域", "類型", "適合場合", "價位", "狀態", "備註", "地址", "Google Maps"])
        for p in d:
            st = "查不到位置" if p.get("nomatch") else STATUS_ZH.get(p.get("status"), "營業狀態不明")
            w.writerow([p["name"], p["region"], p["type"], p["occ"], p["price"], st, p["note"], p.get("addr") or "", p["url"]])
    print(f"built index.html with {len(d)} places")


def parking():
    """Find the nearest parking lot (within 800 m) for places that have coordinates but no parking info yet."""
    import math
    d = load()
    n = 0
    for p in d:
        if p.get("lat") is None or p.get("nomatch") or "parking" in p or p.get("status") == "CLOSED_PERMANENTLY":
            continue
        body = {"includedTypes": ["parking"], "maxResultCount": 1, "rankPreference": "DISTANCE", "languageCode": "zh-TW",
                "locationRestriction": {"circle": {"center": {"latitude": p["lat"], "longitude": p["lng"]}, "radius": 800}}}
        try:
            res = api("https://places.googleapis.com/v1/places:searchNearby", body, "places.id,places.displayName,places.location")
        except urllib.error.HTTPError as e:
            sys.exit(f"Places API error {e.code}: {e.read()[:300]!r}")
        g = (res.get("places") or [None])[0]
        if g:
            la, ln = g["location"]["latitude"], g["location"]["longitude"]
            k = math.pi / 180
            m = 12742000 * math.asin(math.sqrt(math.sin((la - p["lat"]) * k / 2) ** 2 + math.cos(p["lat"] * k) * math.cos(la * k) * math.sin((ln - p["lng"]) * k / 2) ** 2))
            p["parking"] = {"name": g["displayName"]["text"], "pid": g["id"], "lat": round(la, 6), "lng": round(ln, 6), "m": round(m)}
        else:
            p["parking"] = None
        n += 1
        time.sleep(0.05)
    save(d)
    print(f"parking looked up for {n} places")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"merge": lambda: merge(sys.argv[2]), "geocode": geocode, "recheck": recheck, "report": report, "build": build, "parking": parking}.get(
        cmd, lambda: sys.exit(__doc__))()
