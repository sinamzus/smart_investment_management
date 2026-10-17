#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت «زمان‌بندی پرداخت سود نقدی» از سایت پشتیبانی کارگزاری فارابی (help.irfarabi.com) — منبع تاریخ واقعی پرداخت سود (فصل ۱۰، 7f).

چرا این منبع: کارگزاری فارابی نامه‌های ن-۱۳ کدال را برای *همهٔ نمادها* به متن/جدول HTML تبدیل می‌کند (پست‌های دستهٔ «سود نقدی»، ۱۵۹ پست از ۱۴۰۲ تا ۱۴۰۵؛
جدول‌های ماهانه/هفتگی با ستون‌های نماد، سجامی/غیرسجامی، زمان مجمع، DPS، تاریخ واریز). OCR لازم نیست و پریمیوم هم نیست.

روش: API عمومی وردپرس (wp-json) با ۴ تا ۵ درخواست کل محتوا را می‌دهد؛ نیازی به خزیدن صفحه‌به‌صفحه (و فشار روی سایت) نیست.

    python tools/fetch_farabi_dividends.py --log farabi.txt
        ← data/raw/farabi/posts_cat<ID>_p<N>.json  (پاسخ خام؛ قابل push)
    python tools/parse_farabi_dividends.py
        ← data/corporate_actions/payment_dates_farabi.csv

محیط ابری Claude به این سایت دسترسی مستقیم ندارد؛ روی سیستم شما اجرا شود.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://help.irfarabi.com/wp-json/wp/v2"
OUT = ROOT / "data" / "raw" / "farabi"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8"}
CATS = {35: "سود نقدی", 3: "اخبار (شامل جدول ماهانهٔ تجمیعی ۱۴۰۴–۱۴۰۵)"}   # شناسه‌ها با wp-json/wp/v2/categories دیده شد (۲۰۲۶-۱۰-۱۷)
FIELDS = "id,date,modified,slug,link,title,content,categories"


def get(url: str, params: dict) -> requests.Response:
    for k in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=60)
            if r.status_code in (200, 400):        # 400 = صفحهٔ بعد از آخر
                return r
            print(f"   HTTP {r.status_code} ({k + 1}/3)")
        except requests.RequestException as e:
            print(f"   خطا {type(e).__name__} ({k + 1}/3)")
        time.sleep(3 * (k + 1))
    raise SystemExit("دریافت ناموفق؛ بعداً دوباره بزنید (ادامه می‌دهد).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", help="کپی خروجی در فایل UTF-8")
    ap.add_argument("--per-page", type=int, default=50)
    a = ap.parse_args()
    if a.log:
        sys.path.insert(0, str(ROOT / "tools"))
        import fetch_dividend_payments as fdp
        sys.stdout = fdp.Tee(a.log)
    OUT.mkdir(parents=True, exist_ok=True)
    tot = 0
    for cid, name in CATS.items():
        print(f"\n══ دستهٔ {cid}: {name} ══")
        page = 1
        while True:
            r = get(f"{BASE}/posts", {"categories": cid, "per_page": a.per_page, "page": page, "_fields": FIELDS})
            if r.status_code == 400:
                break
            posts = r.json()
            if not posts:
                break
            (OUT / f"posts_cat{cid}_p{page}.json").write_text(json.dumps(posts, ensure_ascii=False), encoding="utf-8")
            tot += len(posts)
            print(f"  صفحه {page}: {len(posts)} پست ({posts[-1]['date'][:10]} … {posts[0]['date'][:10]})؛ جمع تا اینجا {tot}")
            if len(posts) < a.per_page:
                break
            page += 1
            time.sleep(1.5)
    print(f"\nتمام: {tot} پست در {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
