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
- Then `python3 -I scripts/update.py geocode`.
- After a successful push (step 4), rename the Drive file to `已處理_<original title>`.

## 2. Monthly status recheck
- On the first run of each calendar month (i.e. today's day-of-month ≤ 7), run
  `python3 -I scripts/update.py recheck`. Otherwise skip unless step 1 added places.

## 3. Review (Claude does this by judgment)
Run `python3 -I scripts/update.py report` and fix every listed row in `data/places.json`:
- **type**: one of 餐廳 / 咖啡 (cafés, desserts, ice, tea) / 酒吧 / 景點 / 外帶/伴手禮 / 其他 (parking, gas, gym…).
- **occ**: comma-free list joined by `、` from 約會、一個人、帶朋友.
- **price** per person: `$` ≤150, `$$` 150–400, `$$$` 400–1000, `$$$$` >1000, `—` for non-food.
- **name mismatch / no match**: if Google matched a different shop, set `lat`, `lng`, `pid`, `status`
  to null and `nomatch` to true (better absent than wrong). If it is the same shop under another
  name, keep it.
- Set `reviewed: true` on each row you checked. Then `report` must print nothing.

## 4. Publish
- `python3 -I scripts/update.py build`
- Commit only if something changed; message like `Weekly update: +3 places, 1 closed`.
  Push to `main` (`git push -u origin main`). Pages redeploys automatically.

## 5. Report back (final message, Traditional Chinese, short)
Added / removed places, newly closed or reopened places, rows you could not resolve,
and whether anything was pushed. If nothing changed, say so in one line.
