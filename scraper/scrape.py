"""Fetch the current coffee menus of the roasters in roasters.json.

Writes docs/data/menu.json. Run: python scraper/scrape.py
Polite by design: one roaster at a time, a pause between requests,
an honest User-Agent, and only public catalogue endpoints/pages.
"""
import json, re, sys, time, datetime, traceback, xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
import requests

sys.path.insert(0, str(Path(__file__).parent))
from parse import html_text, enrich, is_coffee, grams_in, from_ship_weight, roast_kind, EXCLUDE, find_countries, find_process

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "menu.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 bean-menu/1.0 (personal, non-commercial)"
PAUSE = 0.8
RECENT = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()

def session(country="FR", currency="EUR"):
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "en;q=0.9,fr;q=0.8"})
    s.cookies.set("localization", country)
    s.cookies.set("cart_currency", currency)
    return s

def get(s, url, **kw):
    time.sleep(PAUSE)
    r = s.get(url, timeout=25, **kw)
    r.raise_for_status()
    return r

# ---------- exchange rates (ECB, EUR base) ----------
def rates():
    r = requests.get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml", timeout=20, headers={"User-Agent": UA})
    root = ET.fromstring(r.content)
    out = {"EUR": 1.0}
    for el in root.iter():
        if el.get("currency") and el.get("rate"):
            out[el.get("currency")] = float(el.get("rate"))
    if "USD" in out:
        out["AED"] = out["USD"] * 3.6725  # AED is pegged to USD
    return out

# ---------- item assembly ----------
def make_item(r, title, url, text, sizes, cur, extra_kind=""):
    """sizes: list of (grams|None, price, available, label)"""
    f = enrich(title, text)
    good = [s for s in sizes if s[0] and 60 <= s[0] <= 1100]
    pick = None
    if good:
        avail = [s for s in good if s[2]]
        pool = avail or good
        pick = min(pool, key=lambda s: (s[0], s[1]))
    elif sizes:
        pick = min(sizes, key=lambda s: s[1])
    return {
        "roaster": r["id"],
        "title": re.sub(r"\s+", " ", title).strip(),
        "url": url,
        "cur": cur,
        "price": pick[1] if pick else None,
        "grams": pick[0] if pick else None,
        "sizes": sorted({(s[0], s[1], bool(s[2])) for s in sizes if s[0]}, key=lambda s: s[0])[:6],
        "avail": any(s[2] for s in sizes) if sizes else True,
        "kind": roast_kind(title, extra_kind, " ".join(s[3] or "" for s in sizes)),
        **f,
        "desc": text[:600],
    }

# ---------- Shopify ----------
def scrape_shopify(r):
    s = session()
    base = r["base"].rstrip("/")
    link = (r.get("link_base") or base).rstrip("/")
    items, page = [], 1
    while page <= 6:
        j = get(s, f"{base}/products.json", params={"limit": 250, "page": page}).json()
        prods = j.get("products", [])
        if not prods:
            break
        for p in prods:
            text = html_text(p.get("body_html"))
            if not is_coffee(p["title"], p.get("product_type", ""), p.get("tags", []), text[:200]):
                continue
            avail_any = any(v.get("available", True) for v in p.get("variants", []))
            fresh = (p.get("updated_at") or "")[:10] >= RECENT
            if not avail_any and not fresh:
                continue  # long-gone archive entries
            strong = bool(re.search(r"coffee|kaffe|café|filter|espresso", p.get("product_type", ""), re.I)) or bool(find_countries(p["title"] + " " + text[:400])) or bool(find_process(p["title"]))
            opts = " ".join(o["name"] + " " + " ".join(o.get("values", [])) for o in p.get("options", []))
            sizes = []
            for v in p.get("variants", []):
                g = grams_in(v.get("title")) or grams_in(" ".join(filter(None, [v.get("option1"), v.get("option2"), v.get("option3")]))) \
                    or grams_in(p["title"]) or grams_in(text[:300]) or (from_ship_weight(v.get("grams")) if strong else None)
                try:
                    price = float(v["price"])
                except Exception:
                    continue
                sizes.append((g, price, v.get("available", True), v.get("title")))
            if sizes and not any(sz[0] for sz in sizes):
                continue  # no recognisable bag size → probably not a bag of beans
            items.append(make_item(r, p["title"], f"{link}/products/{p['handle']}", text, sizes, None, opts + " " + " ".join(p.get("tags", []))))
        if len(prods) < 250:
            break
        page += 1
    cur = r.get("cur")
    try:
        cj = get(s, f"{base}/cart.js").json()
        cur = cj.get("currency") or cur
    except Exception:
        pass
    for it in items:
        it["cur"] = cur
    return items

# ---------- WooCommerce Store API ----------
def scrape_woo(r):
    s = session()
    base = r["base"].rstrip("/")
    items, page = [], 1
    while page <= 10:
        res = s.get(f"{base}/wp-json/wc/store/v1/products", params={"per_page": 100, "page": page}, timeout=25, headers={"Accept": "application/json"})
        time.sleep(PAUSE)
        if res.status_code == 400:
            break
        res.raise_for_status()
        try:
            prods = res.json()
        except Exception:
            raise RuntimeError(f"not JSON (HTTP {res.status_code}, {res.headers.get('content-type')}): {res.text[:120]!r}")
        if not prods:
            break
        for p in prods:
            title = html_text(p.get("name"))
            cats = " ".join(c.get("slug", "") + " " + c.get("name", "") for c in p.get("categories", []))
            text = html_text((p.get("short_description") or "") + "\n" + (p.get("description") or ""))
            if not is_coffee(title, cats, [], text[:200]) or EXCLUDE.search(cats):
                continue
            pr = p.get("prices", {})
            mu = int(pr.get("currency_minor_unit", 2))
            try:
                price = int(pr.get("price")) / (10 ** mu)
            except Exception:
                continue
            attrs = " ".join(a.get("name", "") + " " + " ".join(t.get("name", "") for t in a.get("terms", [])) for a in p.get("attributes", []))
            sizes = []
            terms = [t.get("name", "") for a in p.get("attributes", []) for t in a.get("terms", [])]
            gs = [grams_in(t) for t in terms if grams_in(t)]
            g0 = min(gs) if gs else (grams_in(title) or grams_in(text[:400]))
            sizes.append((g0, price, p.get("is_in_stock", True), attrs))
            it = make_item(r, title, p.get("permalink"), text, sizes, pr.get("currency_code") or r.get("cur"), cats + " " + attrs)
            items.append(it)
        if len(prods) < 100:
            break
        page += 1
    return items

# ---------- generic HTML (JSON-LD first) ----------
def jsonld_products(html):
    out = []
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, list):
                stack.extend(d); continue
            if not isinstance(d, dict):
                continue
            if "@graph" in d:
                stack.extend(d["@graph"])
            t = d.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                out.append(d)
            if "hasVariant" in d:
                stack.extend(d["hasVariant"] if isinstance(d["hasVariant"], list) else [d["hasVariant"]])
    return out

def meta(html, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\'][^>]+content=["\']([^"\']+)', html, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']' + re.escape(prop) + r'["\']', html, re.I)
    return m.group(1) if m else None

def scrape_html(r):
    s = session()
    urls = []
    for lu in r["list"]:
        try:
            h = get(s, lu).text
        except Exception:
            continue
        for m in re.finditer(r'href=["\']([^"\']+)["\']', h):
            u = urljoin(lu, m.group(1)).split("#")[0].split("?")[0]
            if re.search(r["product_re"], u) and u not in urls:
                urls.append(u)
    items = []
    for u in urls[:90]:
        try:
            h = get(s, u).text
        except Exception:
            continue
        prods = jsonld_products(h)
        title = None; text = ""; sizes = []; cur = r.get("cur")
        if prods:
            p = prods[0]
            title = p.get("name")
            text = html_text(p.get("description") or "")
            offers = []
            for pp in prods:
                o = pp.get("offers") or []
                o = o if isinstance(o, list) else [o]
                for of in o:
                    if of.get("@type") == "AggregateOffer" and of.get("offers"):
                        offers.extend(of["offers"] if isinstance(of["offers"], list) else [of["offers"]])
                    else:
                        offers.append({**of, "_name": pp.get("name")})
            for of in offers:
                try:
                    price = float(str(of.get("price") or of.get("lowPrice")).replace(",", "."))
                except Exception:
                    continue
                cur = of.get("priceCurrency") or cur
                lab = " ".join(filter(None, [of.get("name"), of.get("_name"), of.get("sku")]))
                g = grams_in(lab) or grams_in(title) or grams_in(text[:400])
                sizes.append((g, price, "InStock" in str(of.get("availability", "InStock")), lab))
        if not title:
            title = meta(h, "og:title") or (re.search(r"<title>(.*?)</title>", h, re.S | re.I) or [None, ""])[1]
            title = html_text(title).split("|")[0].strip()
        body = html_text(re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", h))
        if len(text) < 80:
            text = body[:4000]
        if not sizes:
            pa = meta(h, "product:price:amount") or meta(h, "og:price:amount")
            pc = meta(h, "product:price:currency") or meta(h, "og:price:currency")
            if pa:
                try:
                    sizes.append((grams_in(title) or grams_in(body[:3000]), float(pa.replace(",", ".")), True, ""))
                    cur = pc or cur
                except Exception:
                    pass
        if not sizes and r.get("cur") == "JPY":
            m = re.search(r"(?:¥|￥)\s?([\d,]{3,6})|([\d,]{3,6})\s?円", body)
            if m:
                sizes.append((grams_in(body[:3000]), float((m.group(1) or m.group(2)).replace(",", "")), not re.search(r"sold ?out|売り切れ|在庫切れ", body, re.I), ""))
                cur = "JPY"
        if not title or not is_coffee(title, "coffee", [], ""):
            continue
        if sizes and not any(sz[0] for sz in sizes):
            continue
        items.append(make_item(r, title, u, text, sizes, cur))
    return items

SIZE_RE = re.compile(r"[,\-–—|/(]*\s*\d+(?:[.,]\d+)?\s*(?:kg|g|gr|grams?|lbs?|oz)\b\)?", re.I)
KIND_RE = re.compile(r"[\s,\-–—|/(]+(?:espresso|filter|omni|filtre|roast)(?:\s+roast)?\)?\s*$", re.I)
def merge(items):
    out, idx = [], {}
    for it in items:
        k = KIND_RE.sub("", SIZE_RE.sub("", it["title"])).strip(" ,-–—|").lower()
        k = re.sub(r"\s+", " ", k)
        if k in idx:
            m = idx[k]
            m["sizes"] = sorted({tuple(x) for x in m["sizes"] + it["sizes"]}, key=lambda s: s[0])[:6]
            m["kind"] = sorted(set(m["kind"]) | set(it["kind"]))
            m["avail"] = m["avail"] or it["avail"]
            for f in ("notes", "variety", "country", "process", "producer", "farm", "region", "alt"):
                if not m.get(f) and it.get(f):
                    m[f] = it[f]
            av = [s for s in m["sizes"] if s[2] and 60 <= s[0] <= 1100] or [s for s in m["sizes"] if 60 <= s[0] <= 1100]
            if av:
                g, pr, _ = min(av, key=lambda s: (s[0], s[1]))
                if not m.get("grams") or g < m["grams"] or m["grams"] > 1100:
                    m["grams"], m["price"] = g, pr
                    m["url"] = it["url"] if it.get("grams") == g else m["url"]
            continue
        it = dict(it)
        it["title"] = KIND_RE.sub("", SIZE_RE.sub("", it["title"])).strip(" ,-–—|") or it["title"]
        if it.get("grams") and it["grams"] > 1100:
            it["grams"] = None
        idx[k] = it
        out.append(it)
    return [i for i in out if i.get("grams")]

ADAPTERS = {"shopify": scrape_shopify, "woo": scrape_woo, "html": scrape_html}

def main(only=None):
    roasters = json.loads((ROOT / "roasters.json").read_text())
    prev = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text())
            prev = {i["url"]: i.get("first_seen") for i in old.get("items", [])}
            prev_status = {x["id"]: x for x in old.get("roasters", [])}
        except Exception:
            old, prev_status = {}, {}
    else:
        old, prev_status = {}, {}
    try:
        fx = rates()
    except Exception:
        fx = old.get("rates") or {"EUR": 1.0}
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    today = now[:10]
    all_items, status = [], []
    for r in roasters:
        if only and r["id"] not in only:
            continue
        t0 = time.time()
        try:
            items = merge(ADAPTERS[r["platform"]](r))
            err = None
        except Exception as e:
            items, err = [], f"{type(e).__name__}: {e}"[:200]
            traceback.print_exc()
        if err and old:  # keep yesterday's list for a roaster whose site failed this run
            items = [i for i in old.get("items", []) if i["roaster"] == r["id"]]
        for it in items:
            it["first_seen"] = prev.get(it["url"]) or it.get("first_seen") or today
            if it.get("price") is not None and it.get("cur") in fx and "CNY" in fx:
                eur = it["price"] / fx[it["cur"]]
                it["cny"] = round(eur * fx["CNY"], 2)
                it["p100"] = round(it["cny"] / it["grams"] * 100, 2) if it.get("grams") else None
            else:
                it["cny"] = it.get("cny"); it["p100"] = it.get("p100")
        all_items += items
        status.append({**{k: r.get(k) for k in ("id", "name", "rank", "city", "country", "country_en", "region", "note", "note_en", "base")},
                       "count": len(items), "error": err, "secs": round(time.time() - t0, 1)})
        print(f"{r['id']:<18} {len(items):>3} items  {('ERR ' + err) if err else ''}", flush=True)
    if only and old:
        keep = [i for i in old.get("items", []) if i["roaster"] not in only]
        all_items = keep + all_items
        status = [x for x in old.get("roasters", []) if x["id"] not in only] + status
    data = {"updated": now, "rates": fx, "roasters": status, "items": all_items}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    print(f"total {len(all_items)} items from {sum(1 for x in status if x['count'])}/{len(status)} roasters")

if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
