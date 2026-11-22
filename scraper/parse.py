"""Turn a product's title + description into structured coffee fields.

Everything here is heuristic: roasters write their pages in very different
ways. Each extractor returns None / [] when it is not reasonably sure.
"""
import re
from bs4 import BeautifulSoup

# ---------- text ----------
def html_text(h):
    if not h:
        return ""
    soup = BeautifulSoup(h, "html.parser")
    for br in soup.find_all(["br", "p", "li", "div", "h1", "h2", "h3", "h4", "tr"]):
        br.insert_before("\n")
    t = soup.get_text(" ")
    t = re.sub(r"[ \t ]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()

# ---------- countries ----------
COUNTRIES = [
    ("Papua New Guinea", ["papua new guinea", "png", "papua"]),
    ("Ethiopia", ["ethiopia", "etiopia", "éthiopie", "ethiopie", "äthiopien", "エチオピア"]),
    ("Kenya", ["kenya", "kenia", "ケニア"]),
    ("Colombia", ["colombia", "colombie", "kolumbien", "コロンビア"]),
    ("Panama", ["panama", "panamá", "パナマ"]),
    ("Costa Rica", ["costa rica", "コスタリカ"]),
    ("Guatemala", ["guatemala", "グアテマラ"]),
    ("Honduras", ["honduras", "ホンジュラス"]),
    ("El Salvador", ["el salvador", "salvador", "エルサルバドル"]),
    ("Nicaragua", ["nicaragua", "ニカラグア"]),
    ("Mexico", ["mexico", "méxico", "mexique", "メキシコ"]),
    ("Peru", ["peru", "perú", "pérou", "ペルー"]),
    ("Bolivia", ["bolivia", "bolivie", "ボリビア"]),
    ("Ecuador", ["ecuador", "équateur", "エクアドル"]),
    ("Brazil", ["brazil", "brasil", "brésil", "brasilien", "ブラジル"]),
    ("Rwanda", ["rwanda", "ruanda", "ルワンダ"]),
    ("Burundi", ["burundi", "ブルンジ"]),
    ("Uganda", ["uganda", "ouganda", "ウガンダ"]),
    ("Tanzania", ["tanzania", "tanzanie", "タンザニア"]),
    ("DR Congo", ["dr congo", "drc", "congo", "コンゴ"]),
    ("Malawi", ["malawi"]),
    ("Zambia", ["zambia"]),
    ("Zimbabwe", ["zimbabwe"]),
    ("Yemen", ["yemen", "yémen", "イエメン"]),
    ("Indonesia", ["indonesia", "indonésie", "sumatra", "java", "インドネシア"]),
    ("China", ["china", "yunnan", "chine", "中国", "云南", "雲南"]),
    ("Taiwan", ["taiwan", "台湾"]),
    ("India", ["india", "inde", "インド"]),
    ("Myanmar", ["myanmar", "burma"]),
    ("Thailand", ["thailand", "タイ"]),
    ("Laos", ["laos"]),
    ("Vietnam", ["vietnam", "viet nam"]),
    ("Philippines", ["philippines"]),
    ("Jamaica", ["jamaica"]),
    ("Hawaii", ["hawaii", "kona"]),
    ("Dominican Republic", ["dominican republic"]),
    ("Haiti", ["haiti"]),
    ("Cuba", ["cuba"]),
]
_cpat = [(n, re.compile(r"(?<![a-z])(" + "|".join(re.escape(a) for a in al) + r")(?![a-z])", re.I)) for n, al in COUNTRIES]

def find_countries(text):
    hits = []
    for n, p in _cpat:
        m = p.search(text)
        if m:
            # 'java' is also a variety; only accept it as Indonesia if Indonesia-like context
            if n == "Indonesia" and m.group(1).lower() == "java" and not re.search(r"indonesi|sumatra", text, re.I):
                continue
            if n == "Papua New Guinea" and m.group(1).lower() == "png" and not re.search(r"\bpng\b", text):
                continue
            hits.append((m.start(), n))
    return [n for _, n in sorted(hits)]

# ---------- process ----------
def find_process(text):
    t = text.lower()
    has = lambda *ws: any(w in t for w in ws)
    anaer = has("anaerobic", "anaerob", "anaérob", "アナエロビック", "厌氧")
    out = None
    if has("carbonic maceration", "carbonic"):
        out = "Carbonic maceration"
    elif has("co-ferment", "coferment", "co ferment", "infused"):
        out = "Co-fermented"
    elif has("thermal shock"):
        out = "Thermal shock"
    elif has("wet hulled", "wet-hulled", "giling basah"):
        out = "Wet hulled"
    elif has("semi-washed", "semi washed", "semi-lavado"):
        out = "Semi-washed"
    elif has("pulped natural"):
        out = "Pulped natural"
    elif has("honey", "miel", "ハニー", "蜜处理", "蜜處理"):
        out = "Honey"
    elif has("natural", "dry process", "dry-process", "naturel", "natural process", "sun-dried", "ナチュラル", "日晒", "日曬"):
        out = "Natural"
    elif has("washed", "lavado", "lavé", "wet process", "ウォッシュト", "ウォッシュド", "水洗"):
        out = "Washed"
    if anaer:
        out = "Anaerobic " + out.lower() if out in ("Natural", "Washed", "Honey") else (out or "Anaerobic")
    if has("decaf", "decaffeinated", "sugarcane process", "swiss water", "デカフェ"):
        out = "Decaf" + (" · " + out if out and out != "Decaf" else "")
    return out

# ---------- varieties ----------
VARIETIES = [
    ("Pink Bourbon", ["pink bourbon", "bourbon rosado", "ピンクブルボン"]),
    ("Red Bourbon", ["red bourbon", "bourbon rouge"]),
    ("Yellow Bourbon", ["yellow bourbon", "bourbon amarillo"]),
    ("Striped Bourbon", ["striped bourbon", "bourbon striped"]),
    ("Bourbon", ["bourbon", "ブルボン"]),
    ("Geisha", ["gesha", "geisha", "ゲイシャ"]),
    ("Sidra", ["sidra"]),
    ("Typica", ["typica", "ティピカ"]),
    ("Caturra", ["caturra", "カトゥーラ"]),
    ("Catuai", ["catuai", "catuaí", "カトゥアイ"]),
    ("Pacamara", ["pacamara", "パカマラ"]),
    ("Pacas", ["pacas"]),
    ("Maragogype", ["maragogype", "maragogipe"]),
    ("Mokka", ["mokka", "mocca"]),
    ("Laurina", ["laurina", "bourbon pointu"]),
    ("Wush Wush", ["wush wush", "wushwush"]),
    ("Java", ["java variety", "java cultivar"]),
    ("Castillo", ["castillo"]),
    ("Colombia (var.)", ["variedad colombia"]),
    ("Villa Sarchi", ["villa sarchi", "villasarchi"]),
    ("Parainema", ["parainema"]),
    ("Catimor", ["catimor"]),
    ("Sarchimor", ["sarchimor"]),
    ("Mundo Novo", ["mundo novo"]),
    ("Chiroso", ["chiroso"]),
    ("Tabi", ["tabi"]),
    ("Sudan Rume", ["sudan rume", "sudanrume"]),
    ("Bernardina", ["bernardina"]),
    ("Eugenioides", ["eugenioides"]),
    ("Kent", ["kent"]),
    ("SL28", ["sl28", "sl 28", "sl-28"]),
    ("SL34", ["sl34", "sl 34", "sl-34"]),
    ("SL9", ["sl9", "sl09", "sl 9"]),
    ("Ruiru 11", ["ruiru 11", "ruiru11", "ruiru"]),
    ("Batian", ["batian"]),
    ("K7", ["k7"]),
    ("74110", ["74110"]),
    ("74112", ["74112"]),
    ("74158", ["74158"]),
    ("74165", ["74165"]),
    ("Heirloom", ["heirloom", "landrace", "land race", "local landraces", "jarc", "原生種", "原生种"]),
]
_vpat = [(n, re.compile(r"(?<![a-z0-9])(" + "|".join(re.escape(a) for a in al) + r")(?![a-z0-9])", re.I)) for n, al in VARIETIES]

def find_varieties(text):
    hits = []
    taken = []
    for n, p in _vpat:
        for m in p.finditer(text):
            span = (m.start(), m.end())
            if any(a <= span[0] < b for a, b in taken):
                continue
            taken.append(span)
            hits.append((m.start(), n))
            break
    seen, out = set(), []
    for _, n in sorted(hits):
        if n not in seen:
            seen.add(n); out.append(n)
    return out[:5]

# ---------- labelled fields ----------
LABELS = r"(?:flavou?rs?|tasting notes?|cup notes?|notes?|taste|we taste|in the cup|producers?|farmers?|grown by|farm|estate|finca|washing station|station|mill|origin|region|area|altitude|elevation|masl|variet(?:y|ies|al)|cultivars?|process(?:ing)?|method|harvest|importer|exporter|roast(?:ed)? for|roast|recommended|weight|size)"
def labelled(text, *names):
    for name in names:
        m = re.search(r"(?:^|\n|\s)(?:" + name + r")\s*[:：\-–]\s*(.+?)(?=(?:\s|\n)" + LABELS + r"\s*[:：]|\n|$)", text, re.I)
        if m:
            v = m.group(1).strip(" .;,|")
            if 1 < len(v) < 160:
                return v
    return None

STOP_NOTES = {"familiar", "lingering sweetness", "sweetness", "balance", "clean", "complex", "juicy", "bright"}
def split_notes(s):
    s = re.sub(r"^(?:a|an|the)\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"\b(and|&|und|et|y)\b", ",", s, flags=re.I)
    parts = [p.strip(" .;:-–—|·•*\"'") for p in re.split(r"[,/;|·•+]|、", s)]
    out = []
    for p in parts:
        p = re.sub(r"^(?:a|an|the|some|hints? of|notes? of)\s+", "", p, flags=re.I)
        if 1 < len(p) <= 32 and p.lower() not in STOP_NOTES and not re.search(r"\d{3,}|http|roast|brew|recipe|whether|espresso|filter", p, re.I):
            out.append(p[:1].upper() + p[1:])
    return out[:6]

PROSE_NOTES = [
    r"\bexpect\s+(.+?)[.\n]",
    r"notas (?:principales |de cata )?(?:son|de)\s+(.+?)[.\n]",
    r"notes (?:de|of) (?:dégustation )?:?\s*(.+?)[.\n]",
    r"with ([a-z ,'-]+?) (?:flavou?rs?|notes)\b",
    r"in the cup,? (?:we|you)(?:'ll| will)? (?:find|get|taste|can expect)\s+(.+?)[.\n]",
    r"(?:we|you)(?:'ll| will)? taste\s+(.+?)[.\n]",
    r"(?:flavou?r|tasting) notes? (?:of|include|are|like)\s+(.+?)[.\n]",
    r"notes of\s+(.+?)[.\n]",
    r"reminiscent of\s+(.+?)[.\n]",
    r"tastes? (?:of|like)\s+(.+?)[.\n]",
]
def find_notes(text, title=""):
    v = labelled(text, r"flavou?r notes?", r"tasting notes?", r"cup notes?", r"notes?", r"flavou?rs?", r"taste", r"in the cup", r"we taste", r"tastes like")
    if v:
        n = split_notes(v)
        if n:
            return n
    for pat in PROSE_NOTES:
        m = re.search(pat, text, re.I)
        if m and len(m.group(1)) < 140:
            n = split_notes(m.group(1))
            if n:
                return n
    if len(text) < 320:
        m = re.search(r"\bwith ([a-z][a-z ,'-]+?(?:,| and) [a-z][a-z '-]+)\.", text, re.I)
        if m:
            n = split_notes(m.group(1))
            if len(n) >= 2:
                return n
    # many roasters put notes in the title after a separator: "Kenya Gondo AA – Blackcurrant, Plum"
    m = re.search(r"[|–—]\s*([A-Za-z ,&/]+)$", title)
    if m and "," in m.group(1):
        return split_notes(m.group(1))
    return []

def find_altitude(text):
    m = re.search(r"(\d[\d.,]{2,5})\s*(?:[-–to]+\s*(\d[\d.,]{2,5}))?\s*(?:m\.?a\.?s\.?l\.?|masl|metres|meters|m\b|mts|m above)", text, re.I)
    if not m:
        return None
    nums = [int(re.sub(r"[.,]", "", g)) for g in m.groups() if g]
    nums = [n for n in nums if 600 <= n <= 3000]
    if not nums:
        return None
    return round(sum(nums) / len(nums))

def find_producer(text):
    return labelled(text, r"producers?", r"farmers?", r"grown by", r"produced by")

def find_farm(text):
    return labelled(text, r"farm", r"estate", r"washing station", r"station", r"mill", r"finca")

def find_region(text):
    return labelled(text, r"region", r"origin", r"area")

# ---------- weights ----------
UNIT = {"kg": 1000, "g": 1, "gr": 1, "gram": 1, "grams": 1, "grammes": 1, "lb": 453.6, "lbs": 453.6, "oz": 28.35}
def grams_in(s):
    if not s:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|grams|grammes|gram|gr|g|lbs|lb|oz)\b", s, re.I)
    if not m:
        return None
    g = float(m.group(1).replace(",", ".")) * UNIT[m.group(2).lower()]
    return int(round(g)) if 30 <= g <= 5000 else None

STD = [60, 100, 125, 150, 200, 225, 227, 250, 300, 340, 350, 400, 454, 500, 1000]
def from_ship_weight(g):
    if not g or g < 60 or g > 1200:
        return None
    cands = [s for s in STD if s <= g]
    return max(cands) if cands else None

# ---------- classification ----------
EXCLUDE = re.compile(r"subscri|abonnement|gift ?card|giftcard|gift box|gavekort|presentkort|voucher|equipment|merch|apparel|t-?shirt|hoodie|tote|\bcap\b|beanie|\bmug\b|\bcup\b(?! of excellence)|tumbler|glass|carafe|filter paper|papers|grinder|kettle|dripper|scale|capsule|nespresso|\bpods?\b|drip ?bag|brew ?bag|coffee ?bag(?:s)? \(|single serve|steep|sample|taster|tasting box|chocolate|\btea\b|matcha|chai|workshop|course|training|cupping|tour|class|book|candle|poster|bundle|\bset\b|\bbox\b|trio|duo|kit|cleaner|cafetto|thermos|wholesale|b2b|office|gift|calendar|advent|instant|concentrate|cold brew|ticket|donation|deposit|shipping|recurring|installment|canister|accessor|machine|baratza|breville|barista express|aeropress|chemex|\bv60\b|kalita|hario|fellow|acaia|difluid|refractometer|camiseta|\btaza\b|plato|vinyl|\brecord\b|\blp\b|album|sticker|towel|\bufo\b|\bdrip\b|tasse|lelit|la marzocco|decent|espresso machine|filter holder|portafilter|tamper|pitcher|jug", re.I)
COFFEE_HINT = re.compile(r"coffee|coffees|kaffe|kaffee|café|cafe|filter|espresso|omni|single origin|roast|豆|コーヒー", re.I)

def is_coffee(title, ptype="", tags=(), extra=""):
    blob = " ".join([title or "", ptype or "", " ".join(tags or [])])
    if EXCLUDE.search(title or "") or EXCLUDE.search(ptype or ""):
        return False
    if re.search(r"archiv", ptype or "", re.I):
        return False
    return bool(COFFEE_HINT.search(blob + " " + (extra or "")))

def roast_kind(*parts):
    s = " ".join(p for p in parts if p).lower()
    out = []
    if re.search(r"filter|pour ?over|hand ?drip|filtre|drip", s): out.append("filter")
    if re.search(r"espresso", s): out.append("espresso")
    if re.search(r"omni", s): out.append("omni")
    return out

def enrich(title, text):
    """Fields derived from the combined title + description."""
    both = title + "\n" + text
    countries = find_countries(title) or find_countries(text)
    blend = bool(re.search(r"\bblend\b|拼配|ブレンド", title, re.I))
    proc = find_process(title) or find_process(text)
    return {
        "country": None if blend and len(countries) != 1 else (countries[0] if countries else None),
        "countries": countries[:4],
        "blend": blend,
        "process": proc,
        "variety": find_varieties(title) + [v for v in find_varieties(text) if v not in find_varieties(title)],
        "notes": find_notes(text, title),
        "producer": find_producer(text),
        "farm": find_farm(text),
        "region": find_region(text),
        "alt": find_altitude(text),
        "decaf": bool(re.search(r"decaf|デカフェ", both, re.I)),
    }
