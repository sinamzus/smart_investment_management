#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت دادهٔ صندوق‌های سهامی فعال (غیرشاخصی) برای تفکیک فاکتوری (فصل ۷ §۷٫۹) — روی سیستم خودتان، بدون پروکسی.

    python tools/fetch_active_funds.py                    # همهٔ صندوق‌های ACTIVE
    python tools/fetch_active_funds.py --only "جوانه کوچک"

همان توابع tools/fetch_index_funds.py (قیمت بازار TSETMC اگر صندوق قابل معامله است، و بازده و سطح NAV روزانهٔ فیپیران با شمارهٔ ثبت)، ولی خروجی در data/funds/active/ تا فهرست
صندوق‌های شاخصی (funds.csv و صفحهٔ «ردیابی صندوق‌ها») دست نخورد:
  data/funds/active/nav_<نماد>.csv   ‏(date, ret_daily, ret_price, nav_cancel, nav_issue, nav_stat, aum, source)
  data/funds/active/price_<نماد>.csv.gz
  data/funds/active/funds.csv         مشخصات (نام، کد، شمارهٔ ثبت فیپیران، سبک اعلام‌شده)
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import fetch_index_funds as fi  # noqa: E402

OUT = ROOT / "data" / "funds" / "active"
# نام کوتاه → (نام کامل، insCode در TSETMC یا "" برای صندوق صدور و ابطالی، شمارهٔ ثبت فیپیران، سبک/نوع)
# گزینش (۲۰۲۶-۱۱-۰۳): بزرگ‌ترین صندوق‌های سهامی با سبک‌های متفاوت، فصل ۷ §۷٫۹. صندوق اهرمی کنار ماند: بازده روزانه و سطح NAV
# فیپیران دو سری متفاوت (احتمالاً واحد عادی و کل صندوق) می‌دهند و β آن قابل‌تفسیر نیست.
ACTIVE = {
    "جوانه کوچک": ("صندوق س.جوانه کوچک گندم-سهام", "67455383896188985", "12339", "سهام کوچک"),
    "پیشرو مفید": ("صندوق مشترک پیشرو مفید", "", "10851", "سهامی صدور و ابطالی، بزرگ‌ترین"),
    "اطلس مفید": ("صندوق توسعه اطلس مفید", "", "11215", "سهامی قابل معامله، بزرگ‌ترین"),
    "هستی‌بخش آگاه": ("صندوق هستی بخش آگاه", "", "11341", "سهامی قابل معامله"),
    "مشترک آگاه": ("صندوق مشترک آگاه", "", "10616", "سهامی صدور و ابطالی (هم‌مدیر هستی‌بخش)"),
    "مانا الگوریتم": ("صندوق مشترک مانا الگوریتم", "", "10896", "سهامی، الگوریتمی"),
    "ارزش‌آفرین بیدار": ("صندوق ارزش آفرین بیدار", "", "11712", "سهامی قابل معامله"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append")
    ap.add_argument("--no-price", action="store_true")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    fi.OUT = OUT                                                          # tse_prices و write_nav در همین پوشه می‌نویسند
    meta = []
    for sym, (name, ins, reg, style) in ACTIVE.items():
        if a.only and sym not in a.only:
            continue
        print(f"── {sym} · {name}")
        m = {"symbol": sym, "name": name, "ins_code": ins, "style": style, "n_price": 0, "n_nav": 0, "fipiran_regno": reg}
        if ins and not a.no_price:
            try:
                m["n_price"] = fi.tse_prices(ins, sym)
                print(f"    قیمت بازار: {m['n_price']} روز")
            except Exception as e:  # noqa: BLE001
                print(f"    TSETMC: {e}")
        navs = fi.fipiran_nav({"symbol": sym, "name": name}, {"regNo": reg})
        if navs:
            fi.write_nav(sym, navs, "fipiran")
            m["n_nav"] = len(navs)
            print(f"    NAV: {len(navs)} روز ({navs[0]['date']} تا {navs[-1]['date']})")
        meta.append(m)
    p = OUT / "funds.csv"
    old = {r["symbol"]: r for r in csv.DictReader(p.open(encoding="utf-8"))} if p.exists() else {}
    old.update({m["symbol"]: m for m in meta})
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(meta[0] if meta else next(iter(old.values()))))
        w.writeheader()
        w.writerows(old.values())
    return 0


if __name__ == "__main__":
    sys.exit(main())
