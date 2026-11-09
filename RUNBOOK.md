# Weekly update runbook

This repo publishes `index.html` (GitHub Pages) — a "what's near me" page built from the owner's
saved Google Maps places. A scheduled session runs this weekly. Work in the repo root.

## 0. Preconditions
- Places API key is a network secret on the cloud environment (host `places.googleapis.com`,
  header `X-Goog-Api-Key`). Test: `python3 -I scripts/update.py recheck` must not print an API error.
  If it fails with 400/403, stop and report "Google 金鑰失效或未設定" — do not continue.
- Google Drive connector: folder **口袋名單匯入** (id `1wPnO1VLW5h8SDjB2Npr2Lap81lruydcK`).

## 1. New export?
- In Drive, list files in that folder (`parentId = '1wPnO1VLW5h8SDjB2Npr2Lap81lruydcK'`, not trashed),
  newest first. Ignore files whose title starts with `已處理_`.
- If there is an unprocessed CSV (or a Google Sheet — download it as `text/csv`), save it locally
  outside the repo and run `python3 -I scripts/update.py merge <file>`.
  The export is the full list: places missing from it are removed on purpose.
  Sanity check: if it would remove more than 30% of places, stop and report instead of committing.
- Then `python3 -I scripts/update.py geocode` and `python3 -I scripts/update.py parking`.
- After a successful push (step 4), rename the Drive file to `已處理_<original title>`.
- Fallback / also check: CSV files the owner uploaded to the repo's `imports/` folder.
  Process them the same way, then `git mv` each to `imports/processed/` in the same commit.
- If the Google Drive tools are not available in this session, say so in the report
  (the owner must add the Google Drive connector to the scheduled task) and still process `imports/`.

## 2. Monthly status recheck
- On the first run of each calendar month (i.e. today's day-of-month ≤ 7), run
  `python3 -I scripts/update.py recheck`. Otherwise skip unless step 1 added places.

## 3. Review (Claude does this by judgment)
Run `python3 -I scripts/update.py report` and fix every listed row in `data/places.json`:
- **type**: one of 餐廳 / 咖啡 (cafés, desserts, ice, tea) / 酒吧 / 景點 / 外帶/伴手禮.
- **Not food/café/bar/sight** (bare address pins, parking lots, gas stations, car washes, gyms, shops unrelated to
  eating out): the owner does not want these. Remove the row from `data/places.json` and append
  `{"url", "name", "reason"}` to `data/excluded.json` so later exports never re-add it. List them in the report.
- **occ**: comma-free list joined by `、` from 約會、一個人、帶朋友.
- **price** per person: `$` ≤150, `$$` 150–400, `$$$` 400–1000, `$$$$` >1000, `—` for non-food.
- **name mismatch / no match**: if Google matched a different shop, set `lat`, `lng`, `pid`, `status`
  to null and `nomatch` to true (better absent than wrong). If it is the same shop under another
  name, keep it.
- Set `reviewed: true` on each row you checked. Then `report` must print nothing.

## 3b. Bib Gourmand (yearly, automatic in August)
`data/bib.json` holds MICHELIN Guide Taiwan Bib Gourmand editions with Google place ids; saved places are
tagged by matching `pid` (or `bib_pid`). The guide publishes each July. **On any run in August** (month == 8),
if no entry in `data/bib.json` has the current year in `years`, add that edition:
1. Find TVBS 食尚玩家 per-city list articles for the current year, e.g. web-search
   `site:supertaste.tvbs.com.tw <year> 必比登 完整名單` for 台北, 新北, 台中, 台南, 高雄, 新竹 (and any new city).
   Each article title states the city's count; also note the national total from an overview article.
   guide.michelin.com blocks automated reads, so use these articles.
2. `python3 -I scripts/bib.py add <year> <url> [<url> ...]` (all city articles in one call).
3. Compare its per-city counts with the counts the articles state. If a city is off, open that article's
   text and fix by hand (add/remove rows in `data/bib.json`). Review every `NAME DIFFERS` / `NO MATCH` line:
   a moved or renamed shop is fine; a wrong match must be fixed or removed (the page must never show a
   wrong place). Shops that appear twice (same place id or obvious move) must be one row with all years.
4. Build and push as usual; in the report list the new edition's total, newly added and dropped shops.
If no current-year articles exist yet, say so and retry next week (the check repeats every August run).

## 4. Publish
- `python3 -I scripts/update.py build`
- Commit only if something changed; message like `Weekly update: +3 places, 1 closed`.
  Push to `main` (`git push -u origin main`). Pages redeploys automatically.

## 5. Report back (final message, Traditional Chinese, short)
Added / removed places, newly closed or reopened places, rows you could not resolve,
and whether anything was pushed. If nothing changed, say so in one line.
