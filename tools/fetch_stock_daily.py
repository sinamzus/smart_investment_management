#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دریافت تاریخچهٔ روزانهٔ نمادهای بورس/فرابورس از TSETMC (اسکریپت مستقل)
=====================================================================
باید روی سیستم خودتان اجرا شود (TSETMC از IP دیتاسنتر ۴۰۳ می‌دهد).

مسیرهای API و نام فیلدها از کد جمع‌آوری مخزن RiskFree_Arbitrage
(data_fetcher.py: get_market_watch / get_historical_daily) گرفته شده‌اند —
یعنی روی سیستم شما قبلاً استفاده شده‌اند، ولی برای این اسکریپت تست نشده‌اند.

اجرا
----
    pip install requests
    python tools/fetch_stock_daily.py --discover               # فهرست نمادها → data/instruments.csv
    python tools/fetch_stock_daily.py --probe فولاد            # آزمون یک نماد (۵ ردیف آخر + تعداد)
    python tools/fetch_stock_daily.py --collect                # همهٔ سهام، قابل‌ازسرگیری
    python tools/fetch_stock_daily.py --collect --types stock,fund
    python tools/fetch_stock_daily.py --collect --limit 20     # فقط ۲۰ نماد (آزمایش)
    python tools/fetch_stock_daily.py --summary                # گزارش آنچه جمع شده
    python tools/fetch_stock_daily.py --search پالایش          # سهام خارج از MarketWatch → data/instruments_extra.csv

خروجی
-----
    data/instruments.csv          فهرست ابزارها (ins_code, symbol, name, market, type, base_volume)
    data/prices/<ins_code>.csv.gz تاریخچهٔ روزانه، ستون‌های خام TSETMC بدون تعدیل

هشدارهای مهم
------------
* **سوگیری بقا:** MarketWatch فقط نمادهای فعلی را می‌دهد؛ نمادهای حذف‌شده نیستند.
  اگر کد (ins_code) نمادهای حذف‌شده را دارید در فایل متنی بنویسید (هر خط یک کد) و
  با --codes-file بدهید تا همراه بقیه گرفته شوند.
* قیمت‌ها **تعدیل‌نشده**‌اند. ستون priceYesterday قیمت مبنای روز است (فصل ۲ سند).
* قابل‌ازسرگیری: فایل موجود رد می‌شود؛ برای دریافت مجدد --force.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRICES = DATA / "prices"
INSTR = DATA / "instruments.csv"
EXTRA = DATA / "instruments_extra.csv"   # نمادهایی که با --search اضافه می‌شوند (مثلاً نمادهای حذف‌شده از MarketWatch)

CDN = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Referer": "https://main.tsetmc.com/",
}
TIMEOUT = 40
MIN_INTERVAL = 0.8       # ثانیه بین شروع دو درخواست (در کل فرایند)

# ستون‌های ثابت خروجی (نام خام TSETMC) — بقیهٔ ستون‌ها هم اگر بود ذخیره می‌شود.
CORE = ["dEven", "priceFirst", "priceMax", "priceMin", "pClosing", "pDrCotVal",
        "priceYesterday", "qTotTran5J", "qTotCap", "zTotTran", "priceChange"]

_FLOW_MARKET = {1: "bourse", 2: "farabourse", 3: "other", 4: "other", 5: "other", 6: "other", 7: "paye"}


class RateLimiter:
    def __init__(self, interval):
        self.interval, self.lock, self.next = interval, threading.Lock(), 0.0

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            if self.next > now:
                time.sleep(self.next - now)
                now = time.monotonic()
            self.next = now + self.interval


LIMITER = RateLimiter(MIN_INTERVAL)


def get_json(url: str, retries: int = 3):
    err = None
    for k in range(retries):
        LIMITER.acquire()
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code}"
            if r.status_code == 404:
                break
        except Exception as e:  # noqa: BLE001
            err = repr(e)
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"{url} -> {err}")


def normalize(text: str) -> str:
    fa = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return (text or "").replace("ي", "ی").replace("ك", "ک").translate(fa).strip()


def classify(symbol: str, name: str) -> str:
    """طبقه‌بندی ابزار از نماد و نام (همان قواعد data_fetcher.py)."""
    s, n = normalize(symbol), normalize(name)
    if n.startswith("آتی"):
        return "future"
    if "اختیار" in n or s[:1] in ("ض", "ط"):
        return "option"
    if any(k in n for k in ("خزانه", "صکوک", "مشارکت", "اجاره", "مرابحه", "سلف", "اوراق", "گام", "رهنی", "منفعت")):
        return "bond"
    if "صندوق" in n:
        return "fund"
    if "حق تقدم" in n or (s.endswith("ح") and len(s) > 1):
        return "right"
    return "stock"


# ── کشف ابزارها ──────────────────────────────────────────────────────────
def discover() -> list[dict]:
    variants = [
        f"{CDN}/ClosingPrice/GetMarketWatch?market=0&industrialGroup="
        "&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4"
        "&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8"
        "&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false&hEven=0&refID=0",
        f"{CDN}/ClosingPrice/GetMarketWatch?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3"
        "&paperTypes[3]=4&showTraded=false&withBestLimits=false&hEven=0&refID=0",
    ]
    rows = []
    for u in variants:
        try:
            d = get_json(u, retries=2)
        except Exception as e:  # noqa: BLE001
            print("  تلاش ناموفق:", e, file=sys.stderr)
            continue
        rows = d.get("marketwatch") or d.get("marketWatch") or d.get("MarketWatch") or []
        if rows:
            break
    if not rows:
        raise SystemExit("MarketWatch جواب نداد یا ساختار عوض شده است.")
    out = []
    for r in rows:
        code = str(r.get("insCode") or r.get("InsCode") or "").strip()
        sym = normalize(r.get("lva") or r.get("lVal18AFC") or r.get("symbol") or "")
        name = normalize(r.get("lvc") or r.get("lVal30") or r.get("name") or "")
        if not code or not sym:
            continue
        try:
            flow = int(r.get("flow", 0))
        except (TypeError, ValueError):
            flow = 0
        try:
            bv = int(r.get("bv") or r.get("baseVol") or 0)
        except (TypeError, ValueError):
            bv = 0
        out.append({"ins_code": code, "symbol": sym, "name": name,
                    "market": _FLOW_MARKET.get(flow, "other"), "type": classify(sym, name), "base_volume": bv})
    return out


def save_instruments(rows: list[dict]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with INSTR.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ins_code", "symbol", "name", "market", "type", "base_volume"])
        w.writeheader()
        w.writerows(rows)
    by = {}
    for r in rows:
        by[(r["market"], r["type"])] = by.get((r["market"], r["type"]), 0) + 1
    print(f"{len(rows)} ابزار -> {INSTR}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:10s} {k[1]:8s} {v}")


def load_extra() -> list[dict]:
    if not EXTRA.exists():
        return []
    return [{"ins_code": r["ins_code"], "symbol": r["symbol"], "name": r["name"], "market": "bourse",
             "type": "stock", "base_volume": 0, "extra": 1} for r in csv.DictReader(EXTRA.open(encoding="utf-8"))]


def load_instruments() -> list[dict]:
    if not INSTR.exists():
        raise SystemExit("ابتدا --discover را اجرا کنید.")
    rows = list(csv.DictReader(INSTR.open(encoding="utf-8")))
    known = {r["ins_code"] for r in rows}
    return rows + [r for r in load_extra() if r["ins_code"] not in known]


def search(term: str) -> None:
    """GetInstrumentSearch: نماد/نام را در همهٔ ابزارها (حتی خارج از MarketWatch) جست‌وجو و در instruments_extra.csv ذخیره می‌کند."""
    d = get_json(f"{CDN}/Instrument/GetInstrumentSearch/{quote(term)}")
    items = d.get("instrumentSearch") or []
    print(f"«{term}»: {len(items)} نتیجه")
    known = {r["ins_code"] for r in csv.DictReader(INSTR.open(encoding="utf-8"))} if INSTR.exists() else set()
    old = list(csv.DictReader(EXTRA.open(encoding="utf-8"))) if EXTRA.exists() else []
    seen = {r["ins_code"] for r in old}
    new = []
    for i in items:
        code, sym, name = str(i.get("insCode", "")), normalize(i.get("lVal18AFC", "")), normalize(i.get("lVal30", ""))
        flag = "در MarketWatch" if code in known else "خارج از MarketWatch"
        print(f"  {code}  {sym:12s} {name}  [{flag}; نوع={classify(sym, name)}]")
        if code and code not in known and code not in seen and classify(sym, name) == "stock":
            new.append({"ins_code": code, "symbol": sym, "name": name})
    if new:
        DATA.mkdir(parents=True, exist_ok=True)
        with EXTRA.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ins_code", "symbol", "name"])
            w.writeheader()
            w.writerows(old + new)
        print(f"  {len(new)} سهم جدید به {EXTRA.name} اضافه شد (جمعاً {len(old)+len(new)})")


# ── تاریخچهٔ روزانه ──────────────────────────────────────────────────────
def fetch_daily(ins_code: str, days: int) -> list[dict]:
    d = get_json(f"{CDN}/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{days}")
    items = d.get("closingPriceDaily") or []
    items = [e for e in items if e.get("dEven")]
    items.sort(key=lambda e: e["dEven"])
    return items


def write_prices(ins_code: str, items: list[dict]) -> int:
    if not items:
        return 0
    cols = list(CORE) + [k for k in items[0].keys() if k not in CORE and not isinstance(items[0][k], (dict, list))]
    PRICES.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(items)
    tmp = PRICES / f"{ins_code}.csv.gz.tmp"
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    tmp.replace(PRICES / f"{ins_code}.csv.gz")
    return len(items)


def collect(types: set[str], days: int, limit: int | None, force: bool, workers: int,
            codes_file: str | None) -> None:
    inst = [r for r in load_instruments() if r["type"] in types and r["market"] in ("bourse", "farabourse")]
    extra = []
    if codes_file:
        known = {r["ins_code"] for r in inst}
        extra = [{"ins_code": c.strip(), "symbol": "?", "name": "extra"}
                 for c in Path(codes_file).read_text(encoding="utf-8").split() if c.strip() and c.strip() not in known]
    todo = inst + extra
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} نماد برای دریافت ({len(extra)} کد اضافه از فایل)؛ workers={workers}")
    done = fail = skipped = rows_total = 0
    lock = threading.Lock()
    t0 = time.time()

    def one(r):
        nonlocal done, fail, skipped, rows_total
        code = r["ins_code"]
        if (PRICES / f"{code}.csv.gz").exists() and not force:
            with lock:
                skipped += 1
            return
        try:
            n = write_prices(code, fetch_daily(code, days))
            with lock:
                done += 1
                rows_total += n
                tot = done + fail + skipped
                if tot % 20 == 0 or tot == len(todo):
                    print(f"  [{tot}/{len(todo)}] دریافت={done} خطا={fail} ردشده={skipped} "
                          f"ردیف={rows_total} ({time.time()-t0:.0f}s)")
            if n == 0:
                print(f"  هشدار: {r.get('symbol')} ({code}) ردیفی نداشت")
        except Exception as e:  # noqa: BLE001
            with lock:
                fail += 1
            print(f"  خطا {r.get('symbol')} ({code}): {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    print(f"پایان: دریافت={done} خطا={fail} ردشده={skipped}. اگر خطا بود همان دستور را دوباره بزنید.")


def summary() -> None:
    files = sorted(PRICES.glob("*.csv.gz"))
    if not files:
        print("هنوز چیزی جمع نشده.")
        return
    n = 0
    first, last = "99999999", "0"
    for p in files:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            ds = [r["dEven"] for r in rd]
        if ds:
            n += len(ds)
            first, last = min(first, ds[0]), max(last, ds[-1])
    mb = sum(p.stat().st_size for p in files) / 1e6
    print(f"{len(files)} فایل، {n} ردیف، {first} تا {last}، حدود {mb:.1f} مگابایت")


def probe(symbol: str, days: int) -> None:
    s = normalize(symbol)
    hit = [r for r in load_instruments() if r["symbol"] == s]
    if not hit:
        raise SystemExit(f"نماد «{s}» در instruments.csv نیست.")
    r = hit[0]
    items = fetch_daily(r["ins_code"], days)
    print(f"{r['symbol']} ({r['ins_code']}, {r['market']}, {r['type']}): {len(items)} ردیف")
    if items:
        print("کلیدها:", list(items[0].keys()))
        for e in items[-5:]:
            print(json.dumps({k: e.get(k) for k in CORE}, ensure_ascii=False))
        print("اولین تاریخ:", items[0]["dEven"], " آخرین:", items[-1]["dEven"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--discover", action="store_true")
    ap.add_argument("--probe", metavar="SYMBOL")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--search", action="append", metavar="TERM", help="جست‌وجوی نماد/نام و افزودن سهام خارج از MarketWatch (قابل تکرار)")
    ap.add_argument("--types", default="stock", help="مثلاً stock,fund,right (پیش‌فرض stock)")
    ap.add_argument("--days", type=int, default=9999, help="حداکثر تعداد روز برای هر نماد")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--codes-file", help="فایل متنی ins_code اضافه (مثلاً نمادهای حذف‌شده)")
    a = ap.parse_args()
    if not (a.discover or a.probe or a.collect or a.summary or a.search):
        ap.print_help()
        return 1
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    if a.discover:
        save_instruments(discover())
    for t in a.search or []:
        search(t)
    if a.probe:
        probe(a.probe, a.days)
    if a.collect:
        collect(set(a.types.split(",")), a.days, a.limit, a.force, a.workers, a.codes_file)
    if a.summary:
        summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
