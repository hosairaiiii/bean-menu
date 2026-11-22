# Bean menu · 豆单

Current coffee menus of the roasters in `roasters.json`, collected every six hours
and published as a static page with GitHub Pages.

- `scraper/scrape.py` — fetches each roaster's public catalogue (Shopify product feed,
  WooCommerce Store API, or product pages) and writes `docs/data/menu.json`.
- `scraper/parse.py` — pulls origin, process, variety, tasting notes, altitude out of
  product titles and descriptions. Heuristic; some fields stay empty.
- `docs/index.html` — the page. Filters, price per 100 g in CNY (ECB rates),
  marks coffees whose farm/producer already appears in my archive (`docs/data/consumed.json`),
  and a "to buy" list kept in the browser.
- `.github/workflows/scrape.yml` — runs the scraper every 6 hours and commits the result.

Run locally: `pip install -r requirements.txt && python scraper/scrape.py`
(or `python scraper/scrape.py koppi rose` for a few roasters).

Personal, non-commercial. Requests are spaced out and use only public catalogue pages.
