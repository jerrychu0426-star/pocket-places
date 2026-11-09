#!/usr/bin/env python3
"""Add a MICHELIN Guide Taiwan Bib Gourmand edition to data/bib.json.

  python3 -I scripts/bib.py add <year> <supertaste article url> [<url> ...]

Source: TVBS 食尚玩家 (supertaste.tvbs.com.tw) per-city "必比登完整名單" articles, whose tables give
店名 / 地址 (/ 電話). Each restaurant is located with Places API Text Search (key injected by the
network proxy) and merged into data/bib.json by Google place id, so a shop that appears in several
editions gets several years. Prints per-city counts and suspicious matches for review.
"""
import html, json, os, re, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIB = os.path.join(ROOT, "data", "bib.json")
ADDR = re.compile(r'^(台北|臺北|新北|台中|臺中|台南|臺南|高雄|新竹|桃園|基隆|宜蘭|嘉義|彰化|屏東|花蓮)[市縣]')
PHONE = re.compile(r'^[\(（]?0\d|^無$|^\d{2,4}-')
DIST = re.compile(r'^\S{1,3}區$')


def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(r, timeout=30).read().decode("utf-8", "ignore")


def lines(t):
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', t, flags=re.S)
    t = html.unescape(re.sub(r'<[^>]+>', '\n', t))
    return [l.strip() for l in t.split('\n') if l.strip()]


def parse(url):
    """Rows are either [name, addr, phone] or [district|MRT line, name, landmark|station, addr, phone]."""
    L = lines(get(url))
    out, seen = [], set()
    for i in range(3, len(L)):
        a = L[i]
        if not ADDR.match(a) or not re.search(r'[號弄巷攤]|夜市|市場', a):
            continue
        if (L[i-3].endswith('線') or DIST.match(L[i-3]) or L[i-3] == '地址＋電話'
                or L[i-1] in ('無鄰近捷運站',) or L[i-1].endswith('：')
                or re.fullmatch(r'[【\[（(]?\s*(NEW|新入選)\s*[】\]）)]?', L[i-1])):
            n = L[i-2]
        else:
            n = L[i-1]
        n = re.sub(r'[（(]\s*NEW\s*[）)]|【NEW】|（新入選）', '', n).strip()
        if (not n or ADDR.match(n) or len(n) > 30 or n in ('店名', '地址', '電話') or PHONE.match(n)
                or n.endswith('：') or '、' in n or re.fullmatch(r'[\d.]+', n)):
            continue
        ka = re.sub(r'[（(].*?[）)]|[\s（）()]', '', a).replace('臺', '台').replace('之', '-')
        kn = re.sub(r'[\s（）()]', '', n)
        if ka in seen or kn in seen:
            continue
        seen.update((ka, kn))
        out.append((n, a))
    return out


def city(a):
    m = ADDR.match(a)
    return m.group(1).replace('臺', '台') if m else ''


def geocode(name, addr):
    body = {"textQuery": f"{name} {addr}", "languageCode": "zh-TW", "regionCode": "TW", "pageSize": 1}
    req = urllib.request.Request("https://places.googleapis.com/v1/places:searchText", data=json.dumps(body).encode(),
                                 method="POST", headers={"Content-Type": "application/json", "X-Goog-Api-Key": "injected-by-proxy",
                                                         "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.businessStatus,places.googleMapsUri"})
    g = (json.load(urllib.request.urlopen(req, timeout=20)).get("places") or [None])[0]
    if not g:
        return None
    return dict(pid=g["id"], gname=g["displayName"]["text"], gaddr=g.get("formattedAddress"), lat=round(g["location"]["latitude"], 6),
                lng=round(g["location"]["longitude"], 6), status=g.get("businessStatus"), gurl=g.get("googleMapsUri"))


def add(year, urls):
    data = json.load(open(BIB, encoding="utf-8")) if os.path.exists(BIB) else []
    by_pid = {b["pid"]: b for b in data}
    rows = []
    for u in urls:
        r = parse(u)
        print(f"{u}: {len(r)} rows")
        rows += r
    counts, suspicious, added = {}, [], 0
    norm = lambda s: re.sub(r'[\s（）()\-_|｜·．.、,，/&]', '', s or '')
    for n, a in rows:
        counts[city(a)] = counts.get(city(a), 0) + 1
        g = geocode(n, a)
        time.sleep(0.05)
        if not g:
            suspicious.append(f"NO MATCH: {n} | {a}")
            continue
        if norm(n)[:2] not in norm(g["gname"]) and norm(g["gname"])[:2] not in norm(n):
            suspicious.append(f"NAME DIFFERS: {n} | {a} -> Google: {g['gname']} | {g['gaddr']}")
        if g["pid"] in by_pid:
            b = by_pid[g["pid"]]
            b["years"] = sorted(set(b["years"]) | {year})
            b.update(name=n, addr=a, status=g["status"])          # newest edition wins name/address
        else:
            b = dict(name=n, gname=g["gname"], addr=a, city=city(a), years=[year], pid=g["pid"], lat=g["lat"], lng=g["lng"],
                     status=g["status"], gurl=g["gurl"])
            data.append(b); by_pid[g["pid"]] = b; added += 1
    json.dump(data, open(BIB, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{year}: {sum(counts.values())} rows {counts} | new restaurants {added} | total in file {len(data)}")
    for s in suspicious:
        print("  " + s)


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "add":
        add(int(sys.argv[2]), sys.argv[3:])
    else:
        sys.exit(__doc__)
