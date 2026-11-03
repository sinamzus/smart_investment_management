#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت دادهٔ صندوق‌های سهامی فعال (غیرشاخصی) برای تفکیک فاکتوری (فصل ۷ §۷٫۹) — روی سیستم خودتان، بدون پروکسی.

    python tools/fetch_active_funds.py                    # همهٔ صندوق‌های ACTIVE
    python tools/fetch_active_funds.py --only "جوانه کوچک"
    python tools/fetch_active_funds.py --all [--resume]   # همهٔ صندوق‌های «در سهام» و «بخشی» فهرست فیپیران

همان توابع tools/fetch_index_funds.py (قیمت بازار TSETMC اگر صندوق قابل معامله است، و بازده و سطح NAV روزانهٔ فیپیران با شمارهٔ ثبت)، ولی خروجی در data/funds/active/ تا فهرست
صندوق‌های شاخصی (funds.csv و صفحهٔ «ردیابی صندوق‌ها») دست نخورد:
  data/funds/active/nav_<نماد>.csv   ‏(date, ret_daily, ret_price, nav_cancel, nav_issue, nav_stat, aum, source)؛ در --all فشرده (.csv.gz)
  data/funds/active/price_<نماد>.csv.gz
  data/funds/active/funds.csv         مشخصات (نام، کد، شمارهٔ ثبت فیپیران، سبک اعلام‌شده، نوع فیپیران)
در --all پاسخ خام هر صندوق ذخیره نمی‌شود (هر صندوق ≈ ۱ مگابایت)؛ فقط فهرست fundcompare در data/raw/funds/.
"""
import argparse
import csv
import datetime as dt
import gzip
import re
import shutil
import sys
from pathlib import Path

import requests

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
# fund/fundtype فیپیران: ۶ «در سهام»، ۲۱ «بخشی»؛ ۲۲ اهرمی و ۲۳ شاخصی بیرون (شاخصی‌ها در funds.csv اصلی)
TYPES = {6: "سهامی", 21: "بخشی"}
INVEST = {"IssuanceAndCancellation": "صدور و ابطالی", "Negotiable": "قابل معامله"}


def fund_list() -> list[dict]:
    """فهرست همهٔ صندوق‌ها با نوع، مدیر و تاریخ آغاز (POST fund/fundcompare)."""
    r = requests.post(f"{fi.FIPIRAN_BASES[0]}/fund/fundcompare", json={"regNos": [], "showMarketMakers": False},
                      headers={**fi.HEADERS, "Referer": "https://fipiran.ir/"}, timeout=60)
    r.raise_for_status()
    d = r.json()
    fi.save_raw("fipiran_fund_fundcompare.json", d)
    return d["items"] if isinstance(d, dict) else d


def short_name(name: str) -> str:
    s = re.sub(r"^\s*صندوق\s+(سرمایه\s*گذاری\s+)?", "", name.strip())
    return re.sub(r'[\\/:*?"<>|]', " ", s).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append")
    ap.add_argument("--no-price", action="store_true")
    ap.add_argument("--all", action="store_true", help="همهٔ صندوق‌های «در سهام» و «بخشی» فهرست فیپیران")
    ap.add_argument("--resume", action="store_true", help="با --all: صندوقی که NAV امروزش هست دوباره گرفته نشود")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    fi.OUT = OUT                                                          # tse_prices و write_nav در همین پوشه می‌نویسند
    todo = {sym: (name, ins, reg, style, "") for sym, (name, ins, reg, style) in ACTIVE.items()}
    if a.all:
        by_reg = {v[2]: k for k, v in ACTIVE.items()}
        for it in fund_list():
            if it.get("fundType") not in TYPES:
                continue
            reg = str(it["regNo"])
            sym = by_reg.get(reg) or short_name(it["name"])
            if sym in todo and todo[sym][2] != reg:
                sym = f"{sym} {reg}"
            style = todo[sym][3] if sym in todo else f"{TYPES[it['fundType']]}، {INVEST.get(it.get('typeOfInvest'), '')}".strip("، ")
            todo[sym] = (it["name"], todo.get(sym, ("", "", "", "", ""))[1], reg, style,
                         f"{it['fundType']}|{it.get('typeOfInvest', '')}|{it.get('manager', '')}|{(it.get('initiationDate') or '')[:10]}|{it.get('netAsset') or ''}")
        print(f"{len(todo)} صندوق")
    meta = []
    today = dt.date.today()
    for sym, (name, ins, reg, style, extra) in todo.items():
        if a.only and sym not in a.only:
            continue
        ft, inv, mgr, init, aum = (extra.split("|") + [""] * 5)[:5]
        m = {"symbol": sym, "name": name, "ins_code": ins, "style": style, "n_price": 0, "n_nav": 0, "fipiran_regno": reg,
             "fund_type": ft, "invest": inv, "manager": mgr, "initiation": init, "net_asset": aum}
        gz = OUT / f"nav_{sym}.csv.gz"
        if a.all and a.resume and gz.exists() and dt.date.fromtimestamp(gz.stat().st_mtime) == today:
            meta.append(m)
            continue
        print(f"── {sym} · {name}", flush=True)
        if ins and not a.no_price and not a.all:
            try:
                m["n_price"] = fi.tse_prices(ins, sym)
                print(f"    قیمت بازار: {m['n_price']} روز")
            except Exception as e:  # noqa: BLE001
                print(f"    TSETMC: {e}")
        if a.all:
            fi.save_raw = lambda *_: None                                 # پاسخ خام هر صندوق ذخیره نمی‌شود
        navs = fi.fipiran_nav({"symbol": sym, "name": name}, {"regNo": reg}, quick=a.all)
        if navs:
            fi.write_nav(sym, navs, "fipiran")
            if a.all:
                src = OUT / f"nav_{sym}.csv"
                with src.open("rb") as i, gzip.open(gz, "wb") as o:
                    shutil.copyfileobj(i, o)
                src.unlink()
            m["n_nav"] = len(navs)
            print(f"    NAV: {len(navs)} روز ({navs[0]['date']} تا {navs[-1]['date']})")
        meta.append(m)
    p = OUT / "funds.csv"
    old = {r["symbol"]: r for r in csv.DictReader(p.open(encoding="utf-8"))} if p.exists() else {}
    for m in meta:
        o = old.get(m["symbol"], {})
        old[m["symbol"]] = {**o, **{k: v for k, v in m.items() if v not in ("", 0) or k not in o}}
    cols = list(dict.fromkeys(k for r in old.values() for k in r))
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(old.values())
    return 0


if __name__ == "__main__":
    sys.exit(main())
