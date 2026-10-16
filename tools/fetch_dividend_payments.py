#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جمع‌آوری تاریخ واقعی پرداخت سود نقدی (مرحلهٔ ۱: probe).

محیط ابری Claude به TSETMC/کدال دسترسی ندارد (کد ۰۰۰/۴۰۳)؛ این اسکریپت باید روی سیستم شما اجرا شود.
ساختار پاسخ کدال از حافظه نوشته شده و تست نشده است، پس اول فقط «probe» می‌کنیم: پاسخ خام را در
data/raw/codal/ ذخیره می‌کند و خلاصه چاپ می‌کند تا parser و حالت --collect روی نمونهٔ واقعی ساخته شود.

    pip install requests
    python tools/fetch_dividend_payments.py --sample 3          # سه نمادِ بزرگ «شاخص كل» (بدون تایپ فارسی)
    python tools/fetch_dividend_payments.py --probe فملی        # یا نماد دلخواه

خروجی:
    data/raw/codal/search_<symbol>_p<N>.json   صفحه‌های نتیجهٔ جست‌وجو
    data/raw/codal/letter_<TracingNo>.html     متن چند اطلاعیهٔ «پرداخت سود» / «تصمیمات مجمع» (نمونه)
    و در ترمینال: تعداد کل نامه‌ها، کدهای نوع نامه (LetterCode) با نمونهٔ عنوان، و عنوان‌های دارای «سود».
"""
import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):   # خروجی فارسی هنگام pipe/redirect در ویندوز (cp1252) خطا ندهد
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = ROOT / "data" / "raw" / "codal"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Origin": "https://codal.ir", "Referer": "https://codal.ir/",
}
SEARCH = ("https://search.codal.ir/api/search/v2/q?&Audited=true&AuditorRef=-1&Category=-1&Childs=true&CompanyState=-1"
          "&CompanyType=-1&Consolidatable=true&IsNotAudited=false&Length=-1&LetterType=-1&Mains=true&NotAudited=true"
          "&NotConsolidatable=true&PageNumber={page}&Publisher=false&Symbol={sym}&TracingNo=-1&search=true")
KEYS = ("پرداخت سود", "تقسیم سود", "سود نقدی", "تصمیمات مجمع", "مجمع عمومی")


def fetch(url: str, retries: int = 5, timeout: int = 40) -> requests.Response:
    last = None
    for k in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        print(f"    … تلاش {k+1}/{retries} ناموفق: {str(last)[:90]}")
        time.sleep(3 * (k + 1))
    raise RuntimeError(f"{url[-60:]} -> {last}")


DIAG_URLS = [
    ("tsetmc (مرجع: باید کار کند)", "https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/60523145697836739"),
    ("codal صفحهٔ اصلی", "https://www.codal.ir/"),
    ("codal بدون www", "https://codal.ir/"),
    ("search.codal ریشه", "https://search.codal.ir/"),
    ("search.codal حداقل", "https://search.codal.ir/api/search/v2/q?Symbol=%D8%AE%D9%88%D8%AF%D8%B1%D9%88&PageNumber=1&search=true"),
    ("search.codal کامل", SEARCH.format(page=1, sym="%D8%AE%D9%88%D8%AF%D8%B1%D9%88")),
    ("search.codal با Length=20", SEARCH.format(page=1, sym="%D8%AE%D9%88%D8%AF%D8%B1%D9%88").replace("Length=-1", "Length=20")),
]


def diag() -> None:
    """هر نشانی را یک بار با timeout کوتاه امتحان می‌کند؛ کد وضعیت، زمان و ابتدای پاسخ را چاپ می‌کند."""
    import socket
    for host in ("cdn.tsetmc.com", "codal.ir", "search.codal.ir"):
        try:
            print(f"DNS {host} -> {socket.gethostbyname(host)}")
        except Exception as e:  # noqa: BLE001
            print(f"DNS {host} ناموفق: {e!r}")
    for lab, url in DIAG_URLS:
        t0 = time.time()
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            print(f"[{lab}] HTTP {r.status_code} در {time.time()-t0:.1f}s، {len(r.content)} بایت؛ {r.headers.get('content-type','')}\n    {r.text[:160]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[{lab}] خطا بعد از {time.time()-t0:.1f}s: {type(e).__name__}: {str(e)[:150]}")


def diag2() -> None:
    """کدال: codal.ir کار می‌کند ولی search.codal.ir تا timeout می‌رود. چند شکل درخواست/هدر و curl.exe را امتحان می‌کند."""
    import shutil
    import subprocess
    sym = "%D8%AE%D9%88%D8%AF%D8%B1%D9%88"
    q_full = SEARCH.format(page=1, sym=sym)
    UA = HEADERS["User-Agent"]
    browser = {
        "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br", "Origin": "https://codal.ir", "Referer": "https://codal.ir/",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"', "sec-ch-ua-mobile": "?0", "sec-ch-ua-platform": '"Windows"',
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site",
    }
    tests = [
        ("search.codal، فقط UA", q_full, {"User-Agent": UA}),
        ("search.codal، هدرهای کامل مرورگر", q_full, browser),
        ("search.codal، کامل، Referer=www.codal.ir", q_full, {**browser, "Origin": "https://www.codal.ir", "Referer": "https://www.codal.ir/"}),
        ("codal.ir/api/search/v2/q (همان API روی هاست اصلی)", q_full.replace("https://search.codal.ir", "https://codal.ir"), browser),
        ("codal.ir/ReportList.aspx (صفحهٔ قدیمی)", "https://codal.ir/ReportList.aspx?search&Symbol=" + sym + "&LetterType=-1&Category=-1&PageNumber=1", browser),
    ]
    for lab, url, hd in tests:
        t0 = time.time()
        try:
            r = requests.get(url, headers=hd, timeout=12)
            print(f"[{lab}] HTTP {r.status_code} در {time.time()-t0:.1f}s، {len(r.content)} بایت\n    {r.text[:160]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[{lab}] خطا بعد از {time.time()-t0:.1f}s: {type(e).__name__}")
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        print("curl پیدا نشد")
        return
    for lab, url in (("curl search.codal", q_full), ("curl search.codal --http1.1", q_full)):
        cmd = [curl, "-s", "-m", "15", "-o", "-", "-w", "\n[curl http=%{http_code} t=%{time_total}s]", "-H", "Origin: https://codal.ir", "-H", "Referer: https://codal.ir/",
               "-H", "Accept: application/json, text/plain, */*", "-A", UA] + (["--http1.1"] if "1.1" in lab else []) + [url]
        try:
            out = subprocess.run(cmd, capture_output=True, timeout=25).stdout.decode("utf-8", "replace")
            print(f"[{lab}] {out[:260]!r}")
        except Exception as e:  # noqa: BLE001
            print(f"[{lab}] خطا: {type(e).__name__}")


def scan_types(sym: str, lo: int, hi: int) -> None:
    """برای یک نماد، هر LetterType (و سپس Category) را جدا می‌پرسد؛ Total و نمونهٔ عنوان را چاپ می‌کند تا
    نوعِ «اطلاعیهٔ پرداخت سود» / «تصمیمات مجمع» پیدا شود (کد نوع از حافظه نیست؛ از خروجی خوانده می‌شود)."""
    base = SEARCH.format(page=1, sym=quote(sym))
    for param, rng in (("LetterType", range(lo, hi + 1)), ("Category", range(lo, min(hi, 30) + 1))):
        print(f"\n══ {sym}: پویش {param} ═══")
        for v in rng:
            url = base.replace(f"{param}=-1", f"{param}={v}")
            try:
                r = requests.get(url, headers=HEADERS, timeout=20)
                d = r.json()
            except Exception as e:  # noqa: BLE001
                print(f"  {param}={v}: خطا {type(e).__name__}")
                continue
            tot, lt = d.get("Total", 0), d.get("Letters") or []
            if tot:
                titles = "؛ ".join(sorted({(x.get("Title") or "")[:48] for x in lt})[:3])
                codes = ",".join(sorted({str(x.get("LetterCode")) for x in lt}))
                print(f"  {param}={v:3d} Total={tot:5d} کد={codes:12s} {titles}")
            time.sleep(0.4)


def text_of(html: str) -> str:
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def probe(sym: str, pages: int, letters: int) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"\n══ {sym} ══")
    items, total = [], None
    for p in range(1, pages + 1):
        r = fetch(SEARCH.format(page=p, sym=quote(sym)))
        (RAW / f"search_{sym}_p{p}.json").write_bytes(r.content)
        d = r.json()
        total = d.get("Total", total)
        got = d.get("Letters") or []
        items += got
        if p == 1:
            print("کلیدهای پاسخ:", list(d.keys()))
            if got:
                print("کلیدهای یک نامه:", list(got[0].keys()))
        if not got:
            break
        time.sleep(1.0)
    print(f"Total={total}؛ نامهٔ خوانده‌شده={len(items)}")
    by = defaultdict(list)
    for it in items:
        by[it.get("LetterCode")].append(it.get("Title", ""))
    print("کدهای نامه (تعداد، نمونهٔ عنوان):")
    for code, ts in sorted(by.items(), key=lambda kv: -len(kv[1]))[:25]:
        print(f"  {code!s:8s} {len(ts):4d}  {ts[0][:90]}")
    hits = [it for it in items if any(k in it.get("Title", "") for k in KEYS)]
    print(f"عنوان‌های مرتبط با سود/مجمع: {len(hits)}")
    for it in hits[:15]:
        print(f"  {it.get('PublishDateTime') or it.get('SentDateTime')} | {it.get('LetterCode')} | {it.get('Title','')[:100]} | {it.get('Url')}")
    done = 0
    for it in hits:
        if done >= letters:
            break
        url = it.get("Url") or ""
        if not url:
            continue
        full = url if url.startswith("http") else "https://codal.ir" + url
        try:
            r = fetch(full)
        except Exception as e:  # noqa: BLE001
            print("  دریافت نامه ناموفق:", e)
            continue
        tn = it.get("TracingNo") or re.sub(r"\W", "", url)[-12:]
        (RAW / f"letter_{tn}.html").write_bytes(r.content)
        t = text_of(r.text)
        print(f"\n  ── نامهٔ {tn} ({it.get('Title','')[:60]}) طول متن {len(t)}")
        print("  ", t[:900])
        done += 1
        time.sleep(1.0)


class Tee:
    """چاپ هم‌زمان روی کنسول و فایل UTF-8 (جلوگیری از خراب‌شدن حروف فارسی در redirect/pipe پاورشل)."""
    def __init__(self, path):
        self.f = open(path, "w", encoding="utf-8")
        self.o = sys.stdout

    def write(self, t):
        self.o.write(t)
        self.f.write(t)

    def flush(self):
        self.o.flush()
        self.f.flush()


LT_PAY = 30   # LetterType «زمان‌بندی پرداخت سود» (ن-۱۳)؛ از خروجی --scan-types خوانده شد
LT_AGM = 20   # «تصمیمات مجمع عمومی عادی سالیانه» (ن-۵۲)


def payments(sym: str, letter_type: int, nl: int) -> None:
    """همهٔ نامه‌های یک LetterType را برای نماد می‌خواند؛ فهرست (تاریخ، عنوان، Url، پرچم‌ها) را چاپ و چند نامه را دانلود می‌کند."""
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"\n══ {sym}: LetterType={letter_type} ══")
    items = []
    for p in range(1, 6):
        url = SEARCH.format(page=p, sym=quote(sym)).replace("LetterType=-1", f"LetterType={letter_type}")
        r = fetch(url)
        d = r.json()
        got = d.get("Letters") or []
        (RAW / f"type{letter_type}_{sym}_p{p}.json").write_bytes(r.content)
        items += got
        if len(items) >= d.get("Total", 0) or not got:
            break
        time.sleep(0.8)
    print(f"{len(items)} نامه")
    for it in items:
        print(f"  {it.get('PublishDateTime')} | {it.get('TracingNo')} | {it.get('Title','')[:70]} | html={it.get('HasHtml')} att={it.get('HasAttachment')} xl={it.get('HasExcel')} pdf={it.get('HasPdf')} | {it.get('Url')}")
    done = 0
    for it in items:
        if done >= nl or not it.get("Url"):
            continue
        full = it["Url"] if it["Url"].startswith("http") else "https://codal.ir" + it["Url"]
        try:
            r = fetch(full)
        except Exception as e:  # noqa: BLE001
            print("  دریافت ناموفق:", str(e)[:120])
            continue
        tn = it.get("TracingNo")
        (RAW / f"pay_{tn}.html").write_bytes(r.content)
        links = sorted(set(re.findall(r'href="([^"]+\.(?:pdf|xls|xlsx|doc|docx|zip)[^"]*)"', r.text, re.I)) | set(re.findall(r'href="([^"]*Attachment[^"]*)"', r.text, re.I)))[:8]
        print(f"\n  ── {tn} طول متن {len(text_of(r.text))}؛ پیوندها: {links}")
        print("  ", text_of(r.text)[:700])
        done += 1
        time.sleep(0.8)


def sample_symbols(n: int) -> list:
    """n نمادِ بزرگ (تعداد سهام) از اعضای «شاخص كل» که در instrument_info.csv هست."""
    import csv
    cons = ROOT / "data" / "index_constituents.csv"
    info = ROOT / "data" / "corporate_actions" / "instrument_info.csv"
    k = {r["ins_code"] for r in csv.DictReader(cons.open(encoding="utf-8")) if r["index_code"] == "32097828799138957"}
    rows = [r for r in csv.DictReader(info.open(encoding="utf-8")) if r["ins_code"] in k and r.get("flow") == "1" and r.get("symbol")]
    rows.sort(key=lambda r: -float(r.get("zTitad") or 0))
    return [r["symbol"] for r in rows[:n]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", action="append", metavar="SYMBOL", help="نماد (قابل تکرار)")
    ap.add_argument("--diag", action="store_true", help="فقط اتصال را عیب‌یابی کن (DNS و چند نشانی کدال/TSETMC)")
    ap.add_argument("--diag2", action="store_true", help="عیب‌یابی دوم کدال: هدرها، هاست اصلی، صفحهٔ قدیمی، curl")
    ap.add_argument("--scan-types", metavar="SYMBOL", help="پویش LetterType و Category (۱ تا ۹۹) برای یک نماد؛ نوع «پرداخت سود» را پیدا می‌کند")
    ap.add_argument("--payments", action="append", metavar="SYMBOL", help="نامه‌های «زمان‌بندی پرداخت سود» (LetterType=30) این نماد را فهرست و چند نمونه را دانلود کن")
    ap.add_argument("--agm", action="append", metavar="SYMBOL", help="نامه‌های «تصمیمات مجمع» (LetterType=20) این نماد را فهرست و چند نمونه را دانلود کن")
    ap.add_argument("--log", metavar="FILE", help="خروجی را (UTF-8) در فایل هم بنویس")
    ap.add_argument("--sample", type=int, metavar="N", help="N نمادِ بزرگِ شاخص كل را probe کن (بدون تایپ نام فارسی)")
    ap.add_argument("--pages", type=int, default=3, help="حداکثر صفحهٔ نتیجه برای هر نماد (پیش‌فرض ۳)")
    ap.add_argument("--letters", type=int, default=2, help="چند نامهٔ نمونه دانلود شود (پیش‌فرض ۲؛ برای --payments/--agm مثلاً ۴)")
    a = ap.parse_args()
    if a.log:
        sys.stdout = Tee(a.log)
    for lt, lst in ((LT_PAY, a.payments), (LT_AGM, a.agm)):
        for sy in lst or []:
            try:
                payments(sy, lt, a.letters)
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {sy}: {type(e).__name__}: {str(e)[-220:]}")
    if a.payments or a.agm:
        return
    if a.diag:
        diag()
        return
    if a.diag2:
        diag2()
        return
    if a.scan_types:
        scan_types(a.scan_types, 1, 99)
        return
    syms = list(a.probe or []) + (sample_symbols(a.sample) if a.sample else [])
    if not syms:
        ap.print_help()
        return
    for s in syms:
        try:
            probe(s, a.pages, a.letters)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {s}: {type(e).__name__}: {str(e)[:200]}\n    ← اگر timeout است: python tools/fetch_dividend_payments.py --diag را اجرا و خروجی را بفرستید")


if __name__ == "__main__":
    main()
