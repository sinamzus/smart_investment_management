#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت اسناد خزانهٔ اسلامی (اخزا) برای نرخ بدون ریسک (فصل ۷ §۷٫۱۰) — روی سیستم خودتان، بدون پروکسی.

    python tools/fetch_treasury_bills.py              # فهرست فرابورس + جست‌وجوی TSETMC + قیمت روزانهٔ همهٔ اخزاها (سررسیدشده هم)
    python tools/fetch_treasury_bills.py --list-only  # فقط فهرست و YTM لحظه‌ای فرابورس

دو منبع:
  ۱. فرابورس (www.ifb.ir/ytm.aspx، جدول «اسناد خزانه اسلامی»): نماد، قیمت آخرین معامله، تاریخ آخرین معامله، تاریخ سررسید (شمسی)،
     YTM و بازده سادهٔ فرابورس. منبع تاریخ سررسید و مقایسهٔ YTM. پاسخ خام: data/raw/rates/ifb_ytm.html
  ۲. TSETMC: کد ابزار با جست‌وجوی «اخزا» و پیشوندهای آن (جست‌وجو حداکثر ≈ ۴۰ نتیجه می‌دهد)، سپس ClosingPriceDailyList هر نماد.
خروجی: data/rates/bills.csv (نماد، insCode، نام، سررسید میلادی و شمسی، YTM فرابورس) و data/rates/bills_daily.csv.gz
(date, symbol, close, last, value, volume, count). اگر سررسید در فرابورس نبود، از انتهای نام TSETMC (YYMMDD شمسی) خوانده می‌شود.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from jalali import j2g  # noqa: E402

OUT = ROOT / "data" / "rates"
RAW = ROOT / "data" / "raw" / "rates"
IFB = "https://www.ifb.ir/ytm.aspx"
CDN = "https://cdn.tsetmc.com/api"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8"}
GAP = 1.5
PREFIXES = ["اخزا"] + [f"اخزا{d}" for d in range(10)] + [f"اخزا{d}" for d in range(10, 20)] + [f"اخزا{d}" for d in range(70, 74)]
BILL = re.compile(r"^اخزا\d+$")              # «کاخزا…» و اختیارها (اخزا11خ1، طاخزا…) کنار می‌روند
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_last = 0.0


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ")).strip()


def get(url: str, referer: str):
    global _last
    w = GAP - (time.time() - _last)
    if w > 0:
        time.sleep(w)
    for k in range(3):
        try:
            r = requests.get(url, headers={**HEAD, "Referer": referer}, timeout=40)
            _last = time.time()
            r.raise_for_status()
            return r
        except Exception as e:  # noqa: BLE001
            if k == 2:
                raise
            print(f"    تلاش دوباره ({e})")
            time.sleep(3)


def ifb_bills() -> list[dict]:
    """جدول اسناد خزانهٔ صفحهٔ YTM فرابورس."""
    html = get(IFB, "https://www.ifb.ir/").text
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "ifb_ytm.html").write_text(html, encoding="utf-8")
    i = html.find("grdytmforkhazaneh")
    t = html[i:html.find("</table>", i)]
    out = []
    for tr in re.findall(r"<tr.*?</tr>", t, flags=re.S):
        c = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if len(c) < 7 or not BILL.match(norm(c[1])):
            continue
        pct = lambda s: float(s.translate(FA).replace("/", ".").replace("%", "")) / 100 if re.search(r"\d", s) and "سررسید" not in s else None  # noqa: E731
        out.append({"symbol": norm(c[1]), "ifb_price": c[2].replace(",", ""), "ifb_last_trade": c[3].translate(FA), "maturity_j": c[4].translate(FA),
                    "ifb_ytm": pct(c[5]), "ifb_simple": pct(c[6])})
    return out


def tse_search() -> dict:
    found = {}
    for p in PREFIXES:
        d = get(f"{CDN}/Instrument/GetInstrumentSearch/{quote(p)}", "https://main.tsetmc.com/").json()
        for it in d.get("instrumentSearch") or []:
            s = norm(it.get("lVal18AFC"))
            if BILL.match(s):
                found[s] = {"ins_code": str(it["insCode"]), "name": norm(it.get("lVal30")), "active": int(it.get("lastDate") or 0)}
    return found


def maturity_from_name(name: str):
    """«اسنادخزانه-م2بودجه02-050923» → ۱۴۰۵/۰۹/۲۳؛ «اسناد خزانه اسلامي960703» → ۱۳۹۶/۰۷/۰۳."""
    m = re.search(r"(\d{6})\s*$", name)
    if not m:
        return None
    yy, mm, dd = int(m.group(1)[:2]), int(m.group(1)[2:4]), int(m.group(1)[4:])
    return (1300 + yy if yy >= 90 else 1400 + yy, mm, dd)


def prices(ins: str) -> list:
    d = get(f"{CDN}/ClosingPrice/GetClosingPriceDailyList/{ins}/0", "https://main.tsetmc.com/").json()
    return sorted([e for e in (d.get("closingPriceDaily") or []) if e.get("dEven")], key=lambda e: e["dEven"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    print("── فرابورس: جدول اسناد خزانه")
    ifb = {b["symbol"]: b for b in ifb_bills()}
    print(f"   {len(ifb)} اخزا؛ با YTM جاری: {sum(1 for b in ifb.values() if b['ifb_ytm'] is not None)}")
    print("── TSETMC: جست‌وجوی کد ابزار")
    tse = tse_search()
    print(f"   {len(tse)} اخزا؛ فقط در فرابورس: {sorted(set(ifb) - set(tse))}؛ فقط در TSETMC: {sorted(set(tse) - set(ifb))}")
    rows = []
    for s in sorted(set(ifb) | set(tse)):
        b, t = ifb.get(s, {}), tse.get(s, {})
        mj = None
        if b.get("maturity_j"):
            mj = tuple(int(x) for x in b["maturity_j"].split("-"))
        elif t.get("name"):
            mj = maturity_from_name(t["name"])
        rows.append({"symbol": s, "ins_code": t.get("ins_code", ""), "name": t.get("name", ""), "active_tse": t.get("active", ""),
                     "maturity_j": "" if not mj else f"{mj[0]:04d}/{mj[1]:02d}/{mj[2]:02d}",
                     "maturity": "" if not mj else j2g(*mj, strict=False).isoformat(),
                     "maturity_src": "ifb" if b.get("maturity_j") else ("name" if mj else ""),
                     "ifb_price": b.get("ifb_price", ""), "ifb_last_trade_j": b.get("ifb_last_trade", "").replace("-", "/"),
                     "ifb_ytm": b.get("ifb_ytm"), "ifb_simple": b.get("ifb_simple"), "ifb_asof": datetime.now().strftime("%Y-%m-%d")})
    with (OUT / "bills.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"   → data/rates/bills.csv ({len(rows)} نماد)")
    if a.list_only:
        return 0
    print("── TSETMC: قیمت روزانه")
    n = 0
    with gzip.open(OUT / "bills_daily.csv.gz", "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "symbol", "close", "last", "yesterday", "value", "volume", "count"])
        for r in rows:
            if not r["ins_code"]:
                continue
            try:
                items = prices(r["ins_code"])
            except Exception as e:  # noqa: BLE001
                print(f"   {r['symbol']}: {e}")
                continue
            for e in items:
                w.writerow([datetime.strptime(str(e["dEven"]), "%Y%m%d").date().isoformat(), r["symbol"], e.get("pClosing"), e.get("pDrCotVal"),
                            e.get("priceYesterday"), e.get("qTotCap"), e.get("qTotTran5J"), e.get("zTotTran")])
            n += len(items)
            print(f"   {r['symbol']}: {len(items)} روز (سررسید {r['maturity_j']})", flush=True)
    print(f"   → data/rates/bills_daily.csv.gz ({n} ردیف)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
