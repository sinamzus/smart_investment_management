#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت دادهٔ صندوق‌های سهامی فعال (غیرشاخصی) برای تفکیک فاکتوری (فصل ۷ §۷٫۹) — روی سیستم خودتان، بدون پروکسی.

    python tools/fetch_active_funds.py                    # همهٔ صندوق‌های ACTIVE
    python tools/fetch_active_funds.py --only "جوانه کوچک"

همان توابع tools/fetch_index_funds.py (قیمت بازار TSETMC و بازده/NAV روزانهٔ فیپیران)، ولی خروجی در data/funds/active/ تا فهرست
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
# نماد TSETMC → (نام، insCode، نام فیپیران، سبک اعلام‌شده در نام صندوق)
ACTIVE = {
    "جوانه کوچک": ("صندوق س.جوانه کوچک گندم-سهام", "67455383896188985", "جوانه کوچک گندم", "سهام کوچک"),
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
    rows = fi.fipiran_list()
    meta = []
    for sym, (name, ins, fip, style) in ACTIVE.items():
        if a.only and sym not in a.only:
            continue
        print(f"── {sym} · {name}")
        m = {"symbol": sym, "name": name, "ins_code": ins, "style": style, "n_price": 0, "n_nav": 0, "fipiran_regno": ""}
        if not a.no_price:
            try:
                m["n_price"] = fi.tse_prices(ins, sym)
                print(f"    قیمت بازار: {m['n_price']} روز")
            except Exception as e:  # noqa: BLE001
                print(f"    TSETMC: {e}")
        row = next((r for r in rows if fi.norm(r.get("name", "")).replace(" ", "") == fi.norm(fip).replace(" ", "")), None)
        if not row:
            print(f"    فیپیران: «{fip}» در فهرست نبود")
        else:
            m["fipiran_regno"] = str(row.get("regNo") or "")
            navs = fi.fipiran_nav({"symbol": sym, "name": name}, row)
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
