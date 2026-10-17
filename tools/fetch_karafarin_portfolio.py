#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت پرتفوی ماهانهٔ «صندوق مشترک شاخصی کارآفرین» از سایت خود صندوق (روی سیستم شما اجرا شود؛ محیط ابری به آن دسترسی ندارد).

این صندوق صدور و ابطال است و نماد بورسی/کدال ندارد؛ سایتش (karafarinindexfund.ir) فهرست گزارش‌ها را با API عمومی می‌دهد
(`/api/v1/public/articles/financialReport`: ۲۵۶ مقاله، ۱۰۶ تا «صورت وضعیت پرتفوی»، هر کدام یک PDF در `/FundData/Articles/<شناسه>.pdf`).
فهرست از ضبط مرورگر (data/raw/rahavard/karafarin_site/022_*.json) هم در مخزن هست؛ این ابزار آن را تازه می‌گیرد و PDFها را دانلود می‌کند.

    python tools/fetch_karafarin_portfolio.py --list                 # فقط فهرست گزارش‌های پرتفوی (بدون دانلود)
    python tools/fetch_karafarin_portfolio.py --n 36 --log kp.txt    # ۳۶ پرتفوی آخر (فاصلهٔ ۳ ثانیه؛ قابل‌ادامه)

خروجی: data/raw/karafarin/portfolio/<تاریخ-میلادی>_<شناسه>.pdf  و  data/raw/karafarin/portfolio/list.json
بعد از آن: tools/parse_karafarin_portfolio.py (pdftotext ← holdings_کارآفرین.csv).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://karafarinindexfund.ir"
OUT = ROOT / "data" / "raw" / "karafarin" / "portfolio"
CAP = ROOT / "data" / "raw" / "rahavard" / "karafarin_site"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json, application/pdf, */*", "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8", "Referer": BASE + "/home/index"}
KEYS = ("پرتفو", "پورتفو", "پرتفوي", "پورتفوي")


def norm(t: str) -> str:
    return (t or "").replace("ي", "ی").replace("ك", "ک")


def is_portfolio(a: dict) -> bool:
    t = norm(a["title"])
    return any(k in t for k in ("پرتفو", "پورتفو")) and "مالی" not in t.split("پرتفو")[0][-12:]


def get_list() -> list:
    try:
        r = requests.get(BASE + "/api/v1/public/articles/financialReport", headers=HEADERS, timeout=60)
        r.raise_for_status()
        items = r.json()
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "list.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        print(f"فهرست تازه: {len(items)} مقاله")
        return items
    except Exception as e:  # noqa: BLE001
        print("دریافت فهرست ناموفق؛ از ضبط مرورگر استفاده می‌شود:", type(e).__name__)
        f = next(iter(sorted(CAP.glob("022_*.json"))), None)
        if not f:
            sys.exit("فهرست نیست")
        return json.loads(f.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="فقط فهرست پرتفوی‌ها را چاپ کن")
    ap.add_argument("--n", type=int, default=36, help="آخرین N گزارش پرتفوی (پیش‌فرض ۳۶)")
    ap.add_argument("--gap", type=float, default=3.0)
    ap.add_argument("--log", help="کپی خروجی در فایل UTF-8")
    a = ap.parse_args()
    if a.log:
        sys.path.insert(0, str(ROOT / "tools"))
        import fetch_dividend_payments as fdp
        sys.stdout = fdp.Tee(a.log)
    items = [x for x in get_list() if is_portfolio(x)]
    items.sort(key=lambda x: x["date"], reverse=True)
    print(f"گزارش پرتفوی: {len(items)} (از {items[-1]['date'][:10]} تا {items[0]['date'][:10]})")
    if a.list:
        for x in items[:a.n]:
            print(f"  {x['date'][:10]}  {norm(x['title'])[:80]}  {x['url']}")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for k, x in enumerate(items[:a.n], 1):
        dst = OUT / f"{x['date'][:10]}_{x['id']}.pdf"
        if dst.exists() and dst.stat().st_size > 1000:
            continue
        try:
            r = requests.get(BASE + x["url"], headers=HEADERS, timeout=120)
            r.raise_for_status()
            dst.write_bytes(r.content)
            print(f"  [{k}/{min(a.n, len(items))}] {dst.name} {len(r.content) // 1024}KB  {norm(x['title'])[:60]}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{k}] خطا {type(e).__name__}: {x['url']}")
        time.sleep(a.gap)
    (OUT / "titles.json").write_text(json.dumps({f"{x['date'][:10]}_{x['id']}": norm(x["title"]) for x in items}, ensure_ascii=False), encoding="utf-8")
    print("تمام.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
