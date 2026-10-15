#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دریافت رویدادهای سرمایه‌ای نمادها از TSETMC: تعدیل قیمت، سود نقدی (DPS)، تعداد سهام
=================================================================================
اسکریپت مستقل (فقط requests). روی سیستم خودتان اجرا شود.

مسیرها از سورس کتابخانهٔ منبع‌باز `tsetmc` (5j9/tsetmc، نسخهٔ 0.68) استخراج شده‌اند.
وضعیت پس از اجرای کاربر (۲۰۲۶-۱۰-۱۵):
  ✔ GetPriceAdjustList  — کار می‌کند: dEven, pClosing (تعدیل‌شده), pClosingNotAdjusted
  ✔ GetInstrumentShareChange — کار می‌کند: dEven, numberOfShareNew, numberOfShareOld
  ✔ GetInstrumentInfo — کار می‌کند (zTitad = تعداد سهام فعلی)
  ✘ DPSData.aspx — برای ~۸۴٪ نمادها پاسخ خالی؛ رکوردها با «;» جدا می‌شوند نه خط جدید. نامطمئن.

  ۱) تعدیل قیمت هر نماد (API جدید):   cdn.tsetmc.com/api/ClosingPrice/GetPriceAdjustList/{insCode}
  ۲) تعدیل قیمت کل یک بازار (یک درخواست): old.tsetmc.com/Loader.aspx?ParTree=151319&Flow={1|2}
  ۳) سابقهٔ DPS (سود نقدی هر سهم):       old.tsetmc.com/tsev2/data/DPSData.aspx?s={نماد با حروف عربی}
  ۴) تعداد سهام فعلی:                  cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/{insCode}  (zTitad)
  ۵) تاریخچهٔ تعداد سهام (تغییر سرمایه):  cdn.tsetmc.com/api/Instrument/GetInstrumentShareChange/{insCode}

اجرا
----
    python tools/fetch_corporate_actions.py --probe فولاد
    python tools/fetch_corporate_actions.py --flow 1                  # همهٔ تعدیل‌های بورس در یک درخواست
    python tools/fetch_corporate_actions.py --collect-adjust --limit 20
    python tools/fetch_corporate_actions.py --collect-dps --limit 20
    python tools/fetch_corporate_actions.py --collect-adjust --collect-dps   # همهٔ سهام (قابل‌ازسرگیری)

خروجی
-----
    data/raw/ca/...                   پاسخ‌های خام (برای بازبینی ساختار)
    data/corporate_actions/price_adjust.csv   ردیف‌های تعدیل قیمت هر نماد
    data/corporate_actions/dps.csv            ردیف‌های DPS (تاریخ‌ها میلادی + متن شمسی اصلی)
    data/corporate_actions/share_change.csv   تاریخچهٔ تعداد سهام هر نماد
    data/corporate_actions/flow_adjust_<n>.csv  فهرست یک‌جای تعدیل‌های بازار
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw" / "ca"
OUT = DATA / "corporate_actions"
INSTR = DATA / "instruments.csv"

API = "https://cdn.tsetmc.com/api/"
OLD = "http://old.tsetmc.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
}
TIMEOUT = 40
MIN_INTERVAL = 0.8


class RateLimiter:
    def __init__(self, i):
        self.i, self.lock, self.next = i, threading.Lock(), 0.0

    def acquire(self):
        with self.lock:
            now = time.monotonic()
            if self.next > now:
                time.sleep(self.next - now)
                now = time.monotonic()
            self.next = now + self.i


LIM = RateLimiter(MIN_INTERVAL)


def get(url: str, retries: int = 3) -> bytes:
    err = None
    for k in range(retries):
        LIM.acquire()
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.content
            err = f"HTTP {r.status_code}"
            if r.status_code == 404:
                break
        except Exception as e:  # noqa: BLE001
            err = repr(e)
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"{url} -> {err}")


def get_json(path: str):
    return json.loads(get(API + path).decode("utf-8"))


# ── تاریخ شمسی → میلادی (الگوریتم استاندارد، بدون وابستگی) ──────────────────
def j2g(jy: int, jm: int, jd: int) -> str:
    jy -= 979
    jm -= 1
    jd -= 1
    j_dm = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    g_dm = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_day = 365 * jy + (jy // 33) * 8 + ((jy % 33) + 3) // 4
    j_day += sum(j_dm[:jm]) + jd
    g_day = j_day + 79
    gy = 1600 + 400 * (g_day // 146097)
    g_day %= 146097
    leap = True
    if g_day >= 36525:
        g_day -= 1
        gy += 100 * (g_day // 36524)
        g_day %= 36524
        if g_day >= 365:
            g_day += 1
        else:
            leap = False
    gy += 4 * (g_day // 1461)
    g_day %= 1461
    if g_day >= 366:
        leap = False
        g_day -= 1
        gy += g_day // 365
        g_day %= 365
    i = 0
    while g_day >= g_dm[i] + (1 if i == 1 and leap else 0):
        g_day -= g_dm[i] + (1 if i == 1 and leap else 0)
        i += 1
    return f"{gy:04d}-{i + 1:02d}-{g_day + 1:02d}"


_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def jalali_text_to_iso(t: str) -> str:
    t = (t or "").translate(_FA).strip()
    m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", t)
    return j2g(int(m[1]), int(m[2]), int(m[3])) if m else ""


def arabic_l18(sym: str) -> str:
    return sym.replace("ی", "ي").replace("ک", "ك")


def load_stocks():
    if not INSTR.exists():
        raise SystemExit("ابتدا tools/fetch_stock_daily.py --discover را اجرا کنید.")
    rows = list(csv.DictReader(INSTR.open(encoding="utf-8")))
    known = {r["ins_code"] for r in rows}
    extra_p = DATA / "instruments_extra.csv"
    if extra_p.exists():  # سهام اضافه‌شده با fetch_stock_daily.py --search
        rows += [{"ins_code": r["ins_code"], "symbol": r["symbol"], "name": r["name"], "market": "bourse", "type": "stock"}
                 for r in csv.DictReader(extra_p.open(encoding="utf-8")) if r["ins_code"] not in known]
    # اعضای رسمی «شاخص كل» همیشه سهم‌اند (مثل «وصندوق» و «بورس» که طبقه‌بندی خودکار آن‌ها را صندوق/اوراق می‌دید)
    cons_p = DATA / "index_constituents.csv"
    kmem = set()
    if cons_p.exists():
        kmem = {r["ins_code"] for r in csv.DictReader(cons_p.open(encoding="utf-8")) if r["index_code"] == "32097828799138957"}
    for r in rows:
        if r["ins_code"] in kmem:
            r["type"], r["market"] = "stock", "bourse"
    return [r for r in rows if r["type"] == "stock" and r["market"] in ("bourse", "farabourse")]


def save_raw(name: str, content: bytes | str):
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / name
    p.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    return p


# ── تعدیل قیمت هر نماد ────────────────────────────────────────────────────
def fetch_adjust(ins_code: str) -> list[dict]:
    raw = get(f"{API}ClosingPrice/GetPriceAdjustList/{ins_code}")
    save_raw(f"adjust_{ins_code}.json", raw)
    j = json.loads(raw.decode("utf-8"))
    return j.get("priceAdjust") or []


def collect_adjust(limit, force, workers):
    st = load_stocks()[:limit] if limit else load_stocks()
    OUT.mkdir(parents=True, exist_ok=True)
    rows_all, lock, done, fail = [], threading.Lock(), [0], [0]

    def one(r):
        code = r["ins_code"]
        cache = RAW / f"adjust_{code}.json"
        try:
            if cache.exists() and not force:
                items = json.loads(cache.read_text(encoding="utf-8")).get("priceAdjust") or []
            else:
                items = fetch_adjust(code)
            with lock:
                for it in items:
                    rows_all.append({"ins_code": code, "symbol": r["symbol"], **it})
                done[0] += 1
                if done[0] % 25 == 0:
                    print(f"  adjust [{done[0]}/{len(st)}] ردیف={len(rows_all)}")
        except Exception as e:  # noqa: BLE001
            with lock:
                fail[0] += 1
            print(f"  خطا {r['symbol']}: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, st))
    write_csv(OUT / "price_adjust.csv", rows_all)
    print(f"تعدیل قیمت: {done[0]} نماد، {len(rows_all)} ردیف، خطا={fail[0]} -> {OUT/'price_adjust.csv'}")


# ── تاریخچهٔ تعداد سهام ───────────────────────────────────────────────────
def fetch_shares(ins_code: str) -> list[dict]:
    raw = get(f"{API}Instrument/GetInstrumentShareChange/{ins_code}")
    save_raw(f"shares_{ins_code}.json", raw)
    return json.loads(raw.decode("utf-8")).get("instrumentShareChange") or []


def collect_shares(limit, force, workers):
    st = load_stocks()[:limit] if limit else load_stocks()
    OUT.mkdir(parents=True, exist_ok=True)
    rows_all, lock, done, fail = [], threading.Lock(), [0], [0]

    def one(r):
        code = r["ins_code"]
        cache = RAW / f"shares_{code}.json"
        try:
            if cache.exists() and not force:
                items = json.loads(cache.read_text(encoding="utf-8")).get("instrumentShareChange") or []
            else:
                items = fetch_shares(code)
            with lock:
                for it in items:
                    rows_all.append({"ins_code": code, "symbol": r["symbol"], "dEven": it.get("dEven"),
                                     "shares_new": it.get("numberOfShareNew"), "shares_old": it.get("numberOfShareOld")})
                done[0] += 1
                if done[0] % 25 == 0:
                    print(f"  shares [{done[0]}/{len(st)}] ردیف={len(rows_all)}")
        except Exception as e:  # noqa: BLE001
            with lock:
                fail[0] += 1
            print(f"  خطا {r['symbol']}: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, st))
    write_csv(OUT / "share_change.csv", rows_all)
    print(f"تعداد سهام: {done[0]} نماد، {len(rows_all)} رویداد، خطا={fail[0]} -> {OUT/'share_change.csv'}")


# ── اطلاعات ابزار (تعداد سهام فعلی، گروه صنعت…) ─────────────────────────────
def collect_info(limit, force, workers):
    st = load_stocks()[:limit] if limit else load_stocks()
    OUT.mkdir(parents=True, exist_ok=True)
    rows_all, lock, done, fail = [], threading.Lock(), [0], [0]

    def one(r):
        code = r["ins_code"]
        cache = RAW / f"info_{code}.json"
        try:
            if cache.exists() and not force:
                j = json.loads(cache.read_text(encoding="utf-8"))
            else:
                raw = get(f"{API}Instrument/GetInstrumentInfo/{code}")
                save_raw(f"info_{code}.json", raw)
                j = json.loads(raw.decode("utf-8"))
            i = j.get("instrumentInfo") or {}
            sec = i.get("sector") or {}
            with lock:
                rows_all.append({"ins_code": code, "symbol": r["symbol"], "zTitad": i.get("zTitad"),
                                 "baseVol": i.get("baseVol"), "cIsin": i.get("cIsin"),
                                 "sector_code": (sec.get("cSecVal") or "").strip(), "sector_name": sec.get("lSecVal"),
                                 "flow": i.get("flow"), "board": i.get("cgrValCotTitle"),
                                 "yVal": i.get("yVal"), "faraDesc": i.get("faraDesc")})
                done[0] += 1
                if done[0] % 50 == 0:
                    print(f"  info [{done[0]}/{len(st)}]")
        except Exception as e:  # noqa: BLE001
            with lock:
                fail[0] += 1
            print(f"  خطا {r['symbol']}: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, st))
    write_csv(OUT / "instrument_info.csv", rows_all)
    print(f"اطلاعات ابزار: {done[0]} نماد، خطا={fail[0]} -> {OUT/'instrument_info.csv'}")


# ── DPS ───────────────────────────────────────────────────────────────────
DPS_COLS = ["publish_date", "meeting_date", "fiscal_year", "profit_after_tax",
            "distributable_profit", "accumulated_profit", "cash_eps"]


def parse_dps(text: str) -> list[dict]:
    """رکوردها با «;» (یا خط جدید) جدا و فیلدها با «@». نمونهٔ واقعی (۲۰۲۶-۱۰-۱۵):
    1402/04/28@1402/04/21@1401/12/29@@12839689.00@@500.00  →
    publish, meeting, fiscal_year, ‹خالی›, ‹عدد›, ‹خالی›, ‹آخرین ستون = احتمالاً DPS ریال›
    معنای دقیق ستون‌های ۴ تا ۷ تأیید نشده؛ ردیف‌های تکراری حذف می‌شوند."""
    out, seen = [], set()
    for line in re.split(r"[;\n]", text.replace("\r", "")):
        parts = line.strip().split("@")
        if len(parts) < 7 or not re.match(r"^\d{4}/", parts[0].translate(_FA).strip()):
            continue
        key = tuple(p.strip() for p in parts[:7])
        if key in seen:
            continue
        seen.add(key)
        rec = {k: v.strip() for k, v in zip(DPS_COLS, parts)}
        for c in ("publish_date", "meeting_date", "fiscal_year"):
            rec[c + "_jalali"] = rec[c]
            rec[c] = jalali_text_to_iso(rec[c])
        out.append(rec)
    return out


def fetch_dps(symbol: str, ins_code: str) -> list[dict]:
    raw = get(f"{OLD}tsev2/data/DPSData.aspx?s={quote(arabic_l18(symbol))}")
    save_raw(f"dps_{ins_code}.txt", raw)
    return parse_dps(raw.decode("utf-8", errors="replace"))


def collect_dps(limit, force, workers):
    st = load_stocks()[:limit] if limit else load_stocks()
    OUT.mkdir(parents=True, exist_ok=True)
    rows_all, lock, done, fail, empty = [], threading.Lock(), [0], [0], [0]

    def one(r):
        code = r["ins_code"]
        cache = RAW / f"dps_{code}.txt"
        try:
            if cache.exists() and not force:
                items = parse_dps(cache.read_text(encoding="utf-8", errors="replace"))
            else:
                items = fetch_dps(r["symbol"], code)
            with lock:
                for it in items:
                    rows_all.append({"ins_code": code, "symbol": r["symbol"], **it})
                done[0] += 1
                empty[0] += (not items)
                if done[0] % 25 == 0:
                    print(f"  dps [{done[0]}/{len(st)}] ردیف={len(rows_all)}")
        except Exception as e:  # noqa: BLE001
            with lock:
                fail[0] += 1
            print(f"  خطا {r['symbol']}: {e}", file=sys.stderr)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, st))
    write_csv(OUT / "dps.csv", rows_all)
    print(f"DPS: {done[0]} نماد (بدون سابقه: {empty[0]})، {len(rows_all)} ردیف، خطا={fail[0]} -> {OUT/'dps.csv'}")


# ── تعدیل‌های یک بازار (HTML) ─────────────────────────────────────────────
def parse_html_table(html: str) -> list[list[str]]:
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S | re.I):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S | re.I)]
        if cells:
            rows.append(cells)
    return rows


def collect_flow(flow: int):
    raw = get(f"{OLD}Loader.aspx?ParTree=151319&Flow={flow}")
    save_raw(f"flow_adjust_{flow}.html", raw)
    rows = parse_html_table(raw.decode("utf-8", errors="replace"))
    out = []
    for c in rows:
        if len(c) >= 5 and re.search(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", c[2].translate(_FA)):
            out.append({"l18": c[0], "l30": c[1], "date_jalali": c[2], "date": jalali_text_to_iso(c[2]),
                        "adjusted_price": c[3].replace(",", ""), "price": c[4].replace(",", "")})
    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / f"flow_adjust_{flow}.csv", out)
    print(f"flow={flow}: {len(rows)} سطر جدول، {len(out)} ردیف تعدیل -> {OUT/f'flow_adjust_{flow}.csv'}")


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        print("  هشدار: ردیفی برای", path.name, "نبود")
        return
    cols = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


# ── probe ─────────────────────────────────────────────────────────────────
def probe(symbol: str):
    sym = symbol.replace("ي", "ی").replace("ك", "ک")
    hit = [r for r in csv.DictReader(INSTR.open(encoding="utf-8")) if r["symbol"] == sym]
    if not hit:
        raise SystemExit(f"نماد «{sym}» در instruments.csv نیست.")
    code = hit[0]["ins_code"]
    print(f"{sym} ins_code={code}\n")
    tests = [
        ("تعدیل قیمت (API)", lambda: get(f"{API}ClosingPrice/GetPriceAdjustList/{code}")),
        ("DPS (old)", lambda: get(f"{OLD}tsev2/data/DPSData.aspx?s={quote(arabic_l18(sym))}")),
        ("InstrumentInfo (zTitad = تعداد سهام فعلی)", lambda: get(f"{API}Instrument/GetInstrumentInfo/{code}")),
        ("[حدس] ShareChange", lambda: get(f"{API}Instrument/GetInstrumentShareChange/{code}")),
    ]
    for name, fn in tests:
        print("=" * 70, "\n", name)
        try:
            raw = fn()
            save_raw(f"probe_{code}_{re.sub(r'[^A-Za-z0-9]+', '_', name)}.txt", raw)
            txt = raw.decode("utf-8", errors="replace")
            print(f"  طول پاسخ: {len(raw)} بایت\n  ۸۰۰ کاراکتر اول: {txt[:800]}")
        except Exception as e:  # noqa: BLE001
            print("  ناموفق:", e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", metavar="SYMBOL")
    ap.add_argument("--flow", type=int, help="شمارهٔ بازار برای فهرست تعدیل‌ها (۱ = بورس، ۲ = فرابورس) [راستی‌آزمایی نشده]")
    ap.add_argument("--collect-adjust", action="store_true")
    ap.add_argument("--collect-dps", action="store_true")
    ap.add_argument("--collect-shares", action="store_true")
    ap.add_argument("--collect-info", action="store_true", help="تعداد سهام فعلی (zTitad) و گروه صنعت برای همهٔ نمادها")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    if not (a.probe or a.flow or a.collect_adjust or a.collect_dps or a.collect_shares or a.collect_info):
        ap.print_help()
        return 1
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    if a.probe:
        probe(a.probe)
    if a.flow:
        collect_flow(a.flow)
    if a.collect_adjust:
        collect_adjust(a.limit, a.force, a.workers)
    if a.collect_dps:
        collect_dps(a.limit, a.force, a.workers)
    if a.collect_shares:
        collect_shares(a.limit, a.force, a.workers)
    if a.collect_info:
        collect_info(a.limit, a.force, a.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
