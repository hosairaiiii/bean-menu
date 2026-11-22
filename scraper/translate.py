"""Bilingual (zh / en) short intros + Chinese flavour names for every bean in menu.json.

Optional. Works with any OpenAI-compatible chat API whose key is stored as the repository
secret TR_API_KEY (default endpoint: DeepSeek; set TR_API_URL / TR_MODEL to use another).
Without a key it does nothing and the page falls back to the browser's own on-device translator.
Results are cached in docs/data/tr.json by a hash of the source text, so each description is
only ever sent once.

Run: TR_API_KEY=... python scraper/translate.py [max_requests]
"""
import hashlib, json, os, re, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
MENU = ROOT / "docs" / "data" / "menu.json"
TR = ROOT / "docs" / "data" / "tr.json"
URL = os.environ.get("TR_API_URL") or "https://api.deepseek.com/chat/completions"
MODEL = os.environ.get("TR_MODEL") or "deepseek-chat"
MAX_REQ = int(sys.argv[1]) if len(sys.argv) > 1 else 120
BATCH_CHARS = 5200
BATCH_MAX = 10

SYSTEM = """You write short bilingual intros for specialty-coffee bags listed in a personal buying guide.
For each item you get the product title, the shop's description (any language, may contain shop boilerplate) and English flavour notes.
Return JSON only: {"<id>": {"zh": "...", "en": "...", "notes_zh": ["..."]}, ...}
Rules:
- "en": 1–3 plain sentences in English describing this coffee only (origin, producer/farm, variety, process, altitude, what it tastes like, anything notable). Drop shipping, grind, brewing-equipment, subscription or shop boilerplate. No marketing fluff, no invented facts.
- "zh": the same content in natural, concise simplified Chinese as a specialty-coffee person would write it (e.g. 水洗, 日晒, 厌氧, 瑰夏, 海拔 2000 米). Keep producer/farm names in Latin letters.
- "notes_zh": the given flavour notes translated to short Chinese flavour words, same order; [] if none.
- If the description is empty or useless, write one sentence from the title and notes.
"""

def key(it):
    src = (it.get("title") or "") + "\n" + (it.get("desc") or "") + "\n" + "|".join(it.get("notes") or [])
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:14]

def call(batch, token):
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 4000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(batch, ensure_ascii=False)},
        ],
    }
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = URL
    for _ in range(3):   # follow redirects but keep it a POST (requests would turn it into a GET)
        r = requests.post(url, json=payload, timeout=120, headers=hdr, allow_redirects=False)
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
            url = requests.compat.urljoin(url, r.headers["Location"])
            print("redirect →", url, flush=True)
            continue
        break
    if r.status_code == 429:
        raise RuntimeError("quota: " + r.text[:200])
    if r.status_code >= 400:
        raise ValueError(f"HTTP {r.status_code}: {r.text[:300]}")
    try:
        txt = r.json()["choices"][0]["message"]["content"] or ""
    except Exception:
        raise ValueError(f"bad response ({r.status_code}, {r.headers.get('content-type')}): {r.text[:300]!r}")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        raise ValueError("no JSON in reply: " + txt[:200])
    return json.loads(m.group(0))

def main():
    token = os.environ.get("TR_API_KEY")
    if not token:
        print("no TR_API_KEY secret – skipping (the page uses the browser's translator instead)"); return
    menu = json.loads(MENU.read_text())
    tr = json.loads(TR.read_text()) if TR.exists() else {}
    live = set()
    todo = []
    for it in menu["items"]:
        k = key(it)
        live.add(k)
        if k not in tr:
            todo.append((k, it))
    # in-stock first, then newest
    todo.sort(key=lambda kv: (not kv[1].get("avail"), kv[1].get("first_seen") or ""), reverse=False)
    print(f"{len(todo)} to translate, {len(tr)} cached", flush=True)
    req, done, i = 0, 0, 0
    while i < len(todo) and req < MAX_REQ:
        batch, size = {}, 0
        while i < len(todo) and len(batch) < BATCH_MAX:
            k, it = todo[i]
            entry = {"title": it.get("title"), "desc": (it.get("desc") or "")[:900], "notes": it.get("notes") or []}
            n = len(json.dumps(entry, ensure_ascii=False))
            if batch and size + n > BATCH_CHARS:
                break
            batch[k] = entry; size += n; i += 1
        try:
            out = call(batch, token)
            fails = 0
        except RuntimeError as e:
            print("quota reached:", e, flush=True); break
        except Exception as e:
            fails = locals().get("fails", 0) + 1
            print("batch failed:", str(e)[:400], flush=True); req += 1
            if fails >= 3:
                print("giving up for this run", flush=True); break
            time.sleep(5); continue
        req += 1
        for k in batch:
            v = out.get(k)
            if isinstance(v, dict) and v.get("zh") and v.get("en"):
                tr[k] = {"zh": v["zh"].strip(), "en": v["en"].strip(),
                         "notes_zh": [str(x) for x in (v.get("notes_zh") or [])][:6]}
                done += 1
        time.sleep(1)
    # drop entries for beans no longer listed (keeps the file small)
    tr = {k: v for k, v in tr.items() if k in live}
    TR.write_text(json.dumps(tr, ensure_ascii=False, separators=(",", ":")))
    print(f"translated {done} in {req} requests; cache {len(tr)}")

if __name__ == "__main__":
    main()
