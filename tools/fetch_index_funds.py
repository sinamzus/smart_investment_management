#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دریافت دادهٔ صندوق‌های شاخصی برای سنجش خطای ردیابی (روی سیستم خودتان اجرا شود)
==========================================================================
محیط ابری به TSETMC و فیپیران دسترسی ندارد (۴۰۳). این اسکریپت فقط requests لازم دارد.

صندوق‌های شاخصی خودکار کشف می‌شوند (فهرست ابزارهای مخزن + فیپیران + جست‌وجوی TSETMC؛ صندوق اهرمی کنار می‌رود).
برای هر صندوق:
  ۱. کد ابزار (insCode)
  ۲. قیمت روزانهٔ بازار (ClosingPriceDailyList) → data/funds/price_<نماد>.csv
  ۳. NAV روزانه (ابطال، صدور، آماری) و خالص دارایی از فیپیران؛ اگر نشد، از سایت خود صندوق (سامانهٔ رایان)
     → data/funds/nav_<نماد>.csv
  ۴. شاخص‌های مرجع (كل، هم‌وزن، ۳۰ شرکت بزرگ) به‌روز می‌شوند؛ نام شاخص ۳۰ شرکت چاپ می‌شود تا کد تأیید شود.

همهٔ پاسخ‌های خام در data/raw/funds/ ذخیره می‌شوند؛ اگر قالب پاسخی عوض شده باشد، با همان‌ها اصلاح می‌کنیم.
مسیرهای فیپیران و رایان از حافظه‌اند [راستی‌آزمایی نشده]؛ اسکریپت چند مسیر را امتحان می‌کند و گزارش می‌دهد.

استفاده
-------
    pip install requests
    python tools/fetch_index_funds.py --log funds_log.txt
    git add -A; git commit -m "index funds data"; git push -u origin claude/charming-ptolemy-cyehmc

گزینه‌ها: --only کاردان  (یک صندوق؛ نماد مثل TSETMC: «هم وزن»)، --skip-index (شاخص‌ها را دوباره نگیر)، --site کاردان=https://... (سایت صندوق را دستی بده)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "funds"
RAW = ROOT / "data" / "raw" / "funds"

# شاخص مرجع اعلام‌شده (از مالک پروژه، ۲۰۲۶-۱۰-۱۷). صندوق‌های دیگر خودکار کشف می‌شوند (discover)
# و مرجعشان از نام حدس زده می‌شود (benchmark_src = auto)؛ تحلیل، مرجع با بیشترین همبستگی را هم گزارش می‌کند.
DECLARED = {
    "کاردان": "K", "فیروزه": "I30", "آرام": "K", "وبازار": "K", "هوشمند": "K", "هم وزن": "EW", "هم تراز": "EW",
}
INDEX_CODES = {"K": "32097828799138957", "EW": "67130298613737946", "I30": "10523825119011581",
               "K_PR": "5798407779416661", "EW_PR": "8384385859414435"}

CDN = "https://cdn.tsetmc.com/api"
FIPIRAN = "https://fund.fipiran.ir/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}
MIN_GAP = 1.5
_last = 0.0


class Tee:
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.o = sys.stdout

    def write(self, s):
        self.o.write(s)
        self.f.write(s)

    def flush(self):
        self.o.flush()
        self.f.flush()


def get(url: str, referer: str | None = None, retries: int = 2, as_json: bool = True):
    global _last
    err = None
    for k in range(retries + 1):
        w = MIN_GAP - (time.monotonic() - _last)
        if w > 0:
            time.sleep(w)
        _last = time.monotonic()
        try:
            h = dict(HEADERS)
            if referer:
                h["Referer"] = referer
            r = requests.get(url, headers=h, timeout=40)
            if r.status_code == 200:
                return r.json() if as_json else r.text
            err = f"HTTP {r.status_code}"
            if r.status_code in (404, 400, 403):
                break
        except Exception as e:  # noqa: BLE001
            err = repr(e)[:160]
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"{url} -> {err}")


def save_raw(name: str, obj) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / name
    if isinstance(obj, str):
        p.write_text(obj, encoding="utf-8")
    else:
        p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def norm(t) -> str:
    fa = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return re.sub(r"\s+", " ", str(t or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").translate(fa)).strip()


def find_list(o):
    """بزرگ‌ترین فهرست از دیکشنری‌ها در پاسخ (نام کلید ثابت فرض نمی‌شود)."""
    best = []
    if isinstance(o, list):
        if o and isinstance(o[0], dict) and len(o) > len(best):
            best = o
        for v in o[:5]:
            r = find_list(v)
            if len(r) > len(best):
                best = r
    elif isinstance(o, dict):
        for v in o.values():
            r = find_list(v)
            if len(r) > len(best):
                best = r
    return best


# ── تاریخ ────────────────────────────────────────────────────────────────
def j2g(jy: int, jm: int, jd: int) -> date:
    jy += 1595
    days = -355668 + 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4 + jd + ((jm - 1) * 31 if jm < 7 else (jm - 7) * 30 + 186)
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    ml = [0, 31, 29 if (gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > ml[gm]:
        gd -= ml[gm]
        gm += 1
    return date(gy, gm, gd)


def to_date(v) -> str | None:
    s = norm(v)
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return (j2g(y, mo, d) if y < 1700 else date(y, mo, d)).isoformat()
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if m:
        y, mo, d = map(int, m.groups())
        return (j2g(y, mo, d) if y < 1700 else date(y, mo, d)).isoformat()
    return None


def num(v):
    try:
        x = float(norm(v).replace(",", ""))
        return x if x == x else None
    except (TypeError, ValueError):
        return None


# ── TSETMC ───────────────────────────────────────────────────────────────
def tse_find(symbol: str, name: str) -> dict | None:
    d = get(f"{CDN}/Instrument/GetInstrumentSearch/{quote(symbol)}", "https://main.tsetmc.com/")
    save_raw(f"search_{symbol}.json", d)
    items = d.get("instrumentSearch") or []
    cand = [i for i in items if norm(i.get("lVal18AFC")) == norm(symbol)]
    for i in cand or items:
        print(f"    TSETMC: {i.get('insCode')}  {norm(i.get('lVal18AFC'))}  {norm(i.get('lVal30'))}")
    return (cand or [None])[0]


def tse_prices(ins: str, symbol: str) -> int:
    d = get(f"{CDN}/ClosingPrice/GetClosingPriceDailyList/{ins}/0", "https://main.tsetmc.com/")
    items = sorted([e for e in (d.get("closingPriceDaily") or []) if e.get("dEven")], key=lambda e: e["dEven"])
    if not items:
        save_raw(f"price_{symbol}.json", d)
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / f"price_{symbol}.csv.gz", "wt", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "close", "last", "yesterday", "value", "volume", "count"])
        for e in items:
            w.writerow([datetime.strptime(str(e["dEven"]), "%Y%m%d").date().isoformat(), e.get("pClosing"), e.get("pDrCotVal"),
                        e.get("priceYesterday"), e.get("qTotCap"), e.get("qTotTran5J"), e.get("zTotTran")])
    return len(items)


def tse_etf(ins: str, symbol: str) -> dict:
    """NAV لحظه‌ای و مشخصات صندوق از TSETMC (برای سایت صندوق و تطبیق)."""
    out = {}
    for ep in ("Fund/GetETFByInsCode/{ins}", "Instrument/GetInstrumentInfo/{ins}"):
        try:
            d = get(f"{CDN}/{ep.format(ins=ins)}", "https://main.tsetmc.com/")
            save_raw(f"tse_{ep.split('/')[1]}_{symbol}.json", d)
            out[ep] = d
        except Exception as e:  # noqa: BLE001
            print(f"    {ep}: {e}")
    return out


# ── فیپیران ──────────────────────────────────────────────────────────────
_FIP_LIST = None


def fipiran_list():
    global _FIP_LIST
    if _FIP_LIST is None:
        _FIP_LIST = []
        for ep in ("fund/fundcompare", "fund/getfundlist"):
            try:
                d = get(f"{FIPIRAN}/{ep}", "https://fund.fipiran.ir/")
                save_raw(f"fipiran_{ep.replace('/', '_')}.json", d)
                rows = find_list(d)
                if rows:
                    print(f"  فیپیران {ep}: {len(rows)} صندوق؛ کلیدها: {list(rows[0].keys())[:25]}")
                    _FIP_LIST = rows
                    break
            except Exception as e:  # noqa: BLE001
                print(f"  فیپیران {ep}: {e}")
    return _FIP_LIST


def _tokens(s: str) -> set:
    stop = {"صندوق", "سرمایه", "گذاری", "سرمایه‌گذاری", "شاخصی", "شاخص", "قابل", "معامله", "در", "سهام", "بورسی", "ی"}
    return {t for t in re.split(r"[\s.\-()«»]+", norm(s)) if t and t not in stop}


def fipiran_match(f: dict) -> dict | None:
    rows = fipiran_list()
    if not rows:
        return None
    want = _tokens(f["name"]) | {norm(f["symbol"])}
    best, score = None, 0
    for r in rows:
        text = " ".join(str(v) for v in r.values() if isinstance(v, str))
        sc = len(want & _tokens(text))
        if norm(f["symbol"]) in norm(text).split():
            sc += 3
        if sc > score:
            best, score = r, sc
    if best and score >= 2:
        nm = next((v for k, v in best.items() if isinstance(v, str) and "name" in k.lower()), "")
        print(f"    فیپیران: «{norm(nm)}» (امتیاز تطبیق {score})")
        return best
    print("    فیپیران: تطبیق مطمئن پیدا نشد")
    return None


def _pick(r: dict, *keys):
    low = {k.lower(): v for k, v in r.items()}
    for k in keys:
        if k.lower() in low and low[k.lower()] not in (None, ""):
            return low[k.lower()]
    return None


def parse_nav_rows(rows: list[dict]) -> list[dict]:
    """ردیف‌های NAV با نام فیلدهای ناشناخته → date, nav_cancel, nav_issue, nav_stat, aum."""
    out = []
    for r in rows:
        dkey = next((k for k in r if "date" in k.lower() or k.lower() in ("x", "day", "tarikh")), None)
        d = to_date(r.get(dkey)) if dkey else None
        if not d:
            continue
        lk = {k.lower(): k for k in r}

        def f(*names):
            for n in names:
                for k, orig in lk.items():
                    if n in k:
                        v = num(r[orig])
                        if v:
                            return v
            return None
        out.append({"date": d, "nav_cancel": f("cancel", "ebtal", "redemp"), "nav_issue": f("issue", "sodor", "purchase"),
                    "nav_stat": f("statistic", "amari"), "aum": f("netasset", "net_asset", "totalasset", "nav_total", "asset"),
                    "y": f("y", "value", "nav")})
    for o in out:  # پاسخ تک‌سری (x,y): y را NAV ابطال فرض کن
        if not o["nav_cancel"] and o["y"]:
            o["nav_cancel"] = o["y"]
        o.pop("y", None)
    out = [o for o in out if o["nav_cancel"] or o["nav_stat"] or o["nav_issue"]]
    out.sort(key=lambda o: o["date"])
    dedup = {}
    for o in out:
        dedup[o["date"]] = o
    return list(dedup.values())


def fipiran_nav(f: dict, row: dict) -> list[dict]:
    reg = _pick(row, "regNo", "regno", "fundRegNo", "regNumber")
    if not reg:
        print("    فیپیران: شمارهٔ ثبت (regNo) در ردیف نیست")
        return []
    navs = []
    for ep in (f"chart/getfundchart?regno={reg}", f"chart/getfundnetassetchart?regno={reg}", f"fund/getfundnav?regno={reg}&page=1&pageSize=5000"):
        try:
            d = get(f"{FIPIRAN}/{ep}", "https://fund.fipiran.ir/")
        except Exception as e:  # noqa: BLE001
            print(f"    فیپیران {ep.split('?')[0]}: {e}")
            continue
        save_raw(f"fipiran_{ep.split('?')[0].replace('/', '_')}_{f['symbol']}.json", d)
        rows = parse_nav_rows(find_list(d))
        print(f"    فیپیران {ep.split('?')[0]}: {len(rows)} ردیف NAV")
        if len(rows) > len(navs):
            navs = rows
        elif rows and navs:   # سری خالص دارایی را به ردیف‌های NAV بچسبان
            aum = {r["date"]: r["aum"] or r["nav_cancel"] for r in rows}
            for n in navs:
                n["aum"] = n["aum"] or aum.get(n["date"])
    return navs


# ── سایت صندوق (سامانهٔ رایان هم‌افزا) ─────────────────────────────────
def site_nav(f: dict, site: str) -> list[dict]:
    site = site.rstrip("/")
    if not site.startswith("http"):
        site = "https://" + site
    for ep in ("/Chart/TotalNAV?type=getnavtotal", "/Chart/TotalNAV?type=getnav", "/Reports/FundNAVList?page=1&pageSize=5000"):
        try:
            txt = get(site + ep, site + "/", as_json=False)
        except Exception as e:  # noqa: BLE001
            print(f"    سایت {ep}: {e}")
            continue
        save_raw(f"site_{ep.split('?')[0].strip('/').replace('/', '_')}_{f['symbol']}.txt", txt)
        try:
            d = json.loads(txt)
        except ValueError:
            continue
        # قالب رایان: [{"name": "ابطال", "List": [{"x": "1402/01/05", "y": 1234}, …]}, …]  [راستی‌آزمایی نشده]
        series = {}
        if isinstance(d, list) and d and isinstance(d[0], dict) and any(isinstance(v, list) for v in d[0].values()):
            for s in d:
                nm = norm(next((v for v in s.values() if isinstance(v, str)), ""))
                lst = next((v for v in s.values() if isinstance(v, list)), [])
                key = "nav_cancel" if "ابطال" in nm else "nav_issue" if "صدور" in nm else "nav_stat" if "آماری" in nm else None
                if key:
                    for p in lst:
                        dd = to_date(p.get("x") or p.get("X") or p.get("date"))
                        v = num(p.get("y") or p.get("Y") or p.get("value"))
                        if dd and v:
                            series.setdefault(dd, {"date": dd, "nav_cancel": None, "nav_issue": None, "nav_stat": None, "aum": None})[key] = v
            rows = sorted(series.values(), key=lambda o: o["date"])
        else:
            rows = parse_nav_rows(find_list(d))
        print(f"    سایت {ep.split('?')[0]}: {len(rows)} ردیف NAV")
        if rows:
            return rows
    return []


def write_nav(symbol: str, rows: list[dict], source: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / f"nav_{symbol}.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "nav_cancel", "nav_issue", "nav_stat", "aum", "source"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "source": source})


def refresh_indices() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fetch_official_indices as foi  # noqa: E402  (همین مخزن)
    try:
        names = dict(foi.all_index_codes())
        print(f"  نام شاخص ۳۰ شرکت ({INDEX_CODES['I30']}): «{norm(names.get(INDEX_CODES['I30'], 'پیدا نشد'))}»")
        for c, n in names.items():
            if "30" in norm(n) or "50" in norm(n):
                print(f"    {c}  {norm(n)}")
        save_raw("index_names.json", names)
    except Exception as e:  # noqa: BLE001
        print(f"  فهرست شاخص‌ها: {e}")
    for k, c in INDEX_CODES.items():
        try:
            foi.fetch_index(c)
        except Exception as e:  # noqa: BLE001
            print(f"  شاخص {k}: {e}")


def guess_benchmark(name: str) -> str:
    n = norm(name).replace(" ", "")
    if "هموزن" in n or "هم‌وزن" in n:
        return "EW"
    if "30" in n or "سی" in norm(name).split():
        return "I30"
    return "K"


def _local(add) -> None:
    p = ROOT / "data" / "instruments.csv"
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("type") == "fund":
                add(r["symbol"], r["name"], r["ins_code"], "instruments")


def discover_local() -> list[dict]:
    """فقط از فهرست ابزارهای مخزن (بدون شبکه)."""
    found = {}

    def add(sym, name, ins="", how=""):
        sym, name = norm(sym), norm(name)
        if sym and not re.search(r"\d$", sym) and "اهرمی" not in name and "شاخص" in name:
            found.setdefault(sym, {"symbol": sym, "name": name, "ins_code": ins})
    _local(add)
    out = []
    for sym, r in sorted(found.items()):
        decl = DECLARED.get(sym)
        out.append({**r, "benchmark": decl or guess_benchmark(r["name"]), "benchmark_src": "declared" if decl else "auto"})
    return out


def discover() -> list[dict]:
    """صندوق‌های شاخصی (غیراهرمی) از سه منبع: data/instruments.csv، فهرست فیپیران، جست‌وجوی TSETMC."""
    found = {}

    def add(sym, name, ins="", how=""):
        sym, name = norm(sym), norm(name)
        if not sym or re.search(r"\d$", sym) or "اهرمی" in name or "شاخص" not in name:
            return                                     # نماد فنی تکراری / صندوق اهرمی / غیرشاخصی
        r = found.setdefault(sym, {"symbol": sym, "name": name, "ins_code": ins, "found_by": how})
        r["ins_code"] = r["ins_code"] or ins
        if how not in r["found_by"]:
            r["found_by"] += "," + how
    _local(add)
    for term in ("شاخصی", "شاخص هم وزن", "صندوق شاخص"):
        try:
            d = get(f"{CDN}/Instrument/GetInstrumentSearch/{quote(term)}", "https://main.tsetmc.com/")
            save_raw(f"search_{term.replace(' ', '_')}.json", d)
            for i in d.get("instrumentSearch") or []:
                add(i.get("lVal18AFC"), i.get("lVal30"), str(i.get("insCode") or ""), "tsetmc")
        except Exception as e:  # noqa: BLE001
            print(f"  جست‌وجوی TSETMC «{term}»: {e}")
    for r in fipiran_list():
        nm = next((v for k, v in r.items() if isinstance(v, str) and "name" in k.lower()), "")
        sym = _pick(r, "symbol", "smallSymbolName", "fundSymbol", "insSymbol")
        if "شاخص" in norm(nm) and "اهرمی" not in norm(nm):
            if sym:
                add(sym, nm, "", "fipiran")
            else:
                print(f"  فیپیران بدون نماد: «{norm(nm)}»")
    out = []
    for sym, r in sorted(found.items()):
        decl = DECLARED.get(sym) or DECLARED.get(sym.replace(" ", ""))
        out.append({**r, "benchmark": decl or guess_benchmark(r["name"]), "benchmark_src": "declared" if decl else "auto"})
    print(f"  {len(out)} صندوق شاخصی: " + "، ".join(f"{r['symbol']}({r['benchmark']}{'' if r['benchmark_src'] == 'declared' else '؟'})" for r in out))
    return out


def diag() -> None:
    """کدام میزبان‌ها در دسترس‌اند و آیا TSETMC تاریخچهٔ NAV دارد؟ (یک اجرا، نتیجه را push کنید)"""
    ins = next((f["ins_code"] for f in discover_local() if f["symbol"] == "کاردان"), "65023851436340574")
    print("── میزبان‌ها")
    for u in ("https://fund.fipiran.ir/", "https://fund.fipiran.ir/api/v1/fund/fundcompare", "https://fipiran.ir/", "https://www.fipiran.ir/",
              "https://cdn.tsetmc.com/api/Fund/GetETFByInsCode/" + ins):
        try:
            r = requests.get(u, headers=HEADERS, timeout=25)
            print(f"  {r.status_code}  {u}  [{len(r.content)} بایت]  {r.text[:90]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  خطا  {u}  {type(e).__name__}: {str(e)[:140]}")
    print("── مسیرهای محتمل تاریخچهٔ NAV در TSETMC [راستی‌آزمایی نشده]")
    for ep in (f"{CDN}/Fund/GetETFHistory/{ins}", f"{CDN}/Fund/GetETFNavHistory/{ins}", f"{CDN}/Fund/GetFundHistory/{ins}",
               f"{CDN}/Fund/GetETFByInsCode/{ins}/0", f"{CDN}/ClosingPrice/GetClosingPriceHistory/{ins}/20260101",
               f"https://old.tsetmc.com/tsev2/data/ETFHistory.aspx?i={ins}", f"https://old.tsetmc.com/Loader.aspx?ParTree=15131M&i={ins}"):
        try:
            r = requests.get(ep, headers=HEADERS, timeout=25)
            print(f"  {r.status_code}  {ep}  [{len(r.content)} بایت]  {r.text[:140]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"  خطا  {ep}  {type(e).__name__}: {str(e)[:120]}")


def diag2() -> None:
    """مسیر واقعی API فیپیران را از خود سایت پیدا می‌کند و بدنهٔ پاسخ‌های TSETMC قدیمی را ذخیره می‌کند."""
    ins = "65023851436340574"
    RAW.mkdir(parents=True, exist_ok=True)
    print("── TSETMC قدیمی: بدنهٔ کامل")
    for name, u in (("etfhistory", f"https://old.tsetmc.com/tsev2/data/ETFHistory.aspx?i={ins}"),
                    ("loader", f"https://old.tsetmc.com/Loader.aspx?ParTree=15131M&i={ins}")):
        try:
            r = requests.get(u, headers=HEADERS, timeout=30)
            (RAW / f"diag2_{name}.html").write_text(r.text, encoding="utf-8")
            print(f"  {r.status_code} {u} → data/raw/funds/diag2_{name}.html ({len(r.text)} نویسه)")
        except Exception as e:  # noqa: BLE001
            print(f"  خطا {u}: {e}")
    print("── سایت فیپیران: یافتن آدرس‌های API در بستهٔ جاوااسکریپت")
    base = "https://fipiran.ir"
    try:
        html = requests.get(base + "/", headers=HEADERS, timeout=30).text
        (RAW / "diag2_fipiran_index.html").write_text(html, encoding="utf-8")
        srcs = re.findall(r'(?:src|href)="([^"]+\.js[^"]*)"', html)
        print(f"  {len(srcs)} فایل js: {srcs[:6]}")
        found = set()
        for sr in srcs[:8]:
            u = sr if sr.startswith("http") else base + (sr if sr.startswith("/") else "/" + sr)
            try:
                js = requests.get(u, headers=HEADERS, timeout=60).text
            except Exception as e:  # noqa: BLE001
                print(f"  {u}: {e}")
                continue
            print(f"  js {len(js)//1024} KB: {sr}")
            for m in re.findall(r'https?://[A-Za-z0-9._\-/]*fipiran[A-Za-z0-9._\-/?=&]*', js):
                found.add(m)
            for m in re.findall(r'["\'`](/?(?:api|Api)/[A-Za-z0-9_/\-.?=&{}$]*(?:fund|Fund|nav|NAV|chart)[A-Za-z0-9_/\-.?=&{}$]*)["\'`]', js):
                found.add(m)
        for m in sorted(found)[:80]:
            print("   ", m)
    except Exception as e:  # noqa: BLE001
        print(f"  خطا: {e}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", action="append", help="فقط این نماد(ها)")
    ap.add_argument("--skip-index", action="store_true")
    ap.add_argument("--site", action="append", default=[], help="نماد=آدرس سایت صندوق (اگر خودکار پیدا نشد)")
    ap.add_argument("--diag", action="store_true", help="فقط آزمون دسترسی میزبان‌ها و مسیرهای NAV (سریع)")
    ap.add_argument("--diag2", action="store_true", help="یافتن آدرس API فیپیران از سایت و ذخیرهٔ صفحات TSETMC قدیمی")
    ap.add_argument("--log", help="کپی خروجی در این فایل (UTF-8)")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    if a.log:
        sys.stdout = Tee(a.log)
    if a.diag or a.diag2:
        (diag if a.diag else diag2)()
        return 0
    sites = dict(x.split("=", 1) for x in a.site)
    if not a.skip_index:
        print("── شاخص‌های مرجع")
        refresh_indices()
    print("\n── کشف صندوق‌های شاخصی")
    funds = discover()
    meta = []
    for f in funds:
        if a.only and f["symbol"] not in a.only:
            continue
        print(f"\n── {f['symbol']} · {f['name']} (مرجع: {f['benchmark']})")
        m = {**f, "n_price": 0, "n_nav": 0, "nav_source": "", "site": sites.get(f["symbol"], ""), "fipiran_regno": ""}
        try:
            if not m["ins_code"]:
                hit = tse_find(f["symbol"], f["name"])
                m["ins_code"] = str(hit["insCode"]) if hit else ""
            if m["ins_code"]:
                m["n_price"] = tse_prices(m["ins_code"], f["symbol"])
                print(f"    قیمت بازار: {m['n_price']} روز")
                tse_etf(m["ins_code"], f["symbol"])
        except Exception as e:  # noqa: BLE001
            print(f"    TSETMC: {e}")
        navs, src = [], ""
        row = fipiran_match(f)
        if row:
            m["fipiran_regno"] = str(_pick(row, "regNo", "regno") or "")
            m["site"] = m["site"] or str(_pick(row, "websiteAddress", "website", "url", "siteUrl") or "")
            navs = fipiran_nav(f, row)
            src = "fipiran" if navs else ""
        if not navs and m["site"]:
            navs = site_nav(f, m["site"])
            src = "site" if navs else ""
        if navs:
            write_nav(f["symbol"], navs, src)
            m["n_nav"], m["nav_source"] = len(navs), src
            print(f"    NAV: {len(navs)} روز ({navs[0]['date']} تا {navs[-1]['date']}) از {src}")
        else:
            print("    NAV: دریافت نشد؛ پاسخ‌های خام در data/raw/funds/ ذخیره شد. اگر سایت صندوق را می‌دانید: --site نماد=آدرس")
        meta.append(m)
    if meta:
        OUT.mkdir(parents=True, exist_ok=True)
        p = OUT / "funds.csv"
        old = {r["symbol"]: r for r in csv.DictReader(p.open(encoding="utf-8"))} if p.exists() else {}
        old.update({m["symbol"]: m for m in meta})
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(meta[0].keys()))
            w.writeheader()
            w.writerows(old.values())
        print(f"\nخلاصه: {sum(1 for m in old.values() if int(m['n_nav'] or 0) > 0)}/{len(old)} صندوق با NAV → {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
