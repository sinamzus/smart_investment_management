#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پارس PDFهای «صورت وضعیت پرتفوی» صندوق مشترک شاخصی کارآفرین ← data/funds/holdings_کارآفرین.csv (همان قالب پرتفوی‌های کدال).

ورودی: data/raw/karafarin/portfolio/<تاریخ>_<شناسه>.pdf  (tools/fetch_karafarin_portfolio.py)
ابزار:  pdftotext -layout (PDFها متنی‌اند؛ OCR لازم نیست)
هر ردیف سهام یک خط است با ستون‌های (به ترتیب چاپ): درصد به کل دارایی‌ها، خالص ارزش فروش، بهای تمام‌شده، قیمت بازار هر سهم، تعداد، … ، نام شرکت (آخر).
ردیف‌های اختیار خرید/فروش (بدون درصد) و بخش‌های سپرده/اوراق دیده نمی‌شوند. تاریخ گزارش = «برای ماه منتهی به …» (پایان دوره، روز ۲۱ شمسی).
نام ← نماد با همان match/price_match پرتفوی‌های کدال (parse_fund_portfolio)؛ مجموع درصد سهام باید ۵۰ تا ~۱۰۶ باشد وگرنه آن ماه کنار می‌رود.
"""
import csv
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from fetch_corporate_actions import j2g  # noqa: E402
import parse_fund_portfolio as pp  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = ROOT / "data" / "raw" / "karafarin" / "portfolio"
OUT = ROOT / "data" / "funds" / "holdings_کارآفرین.csv"
NUM = re.compile(r"^(-|-?[\d,]+(\.\d+)?)$")      # «-» = صفر (قالب ۱۴۰۴ به بعد)
PCT = re.compile(r"^(\d+(?:\.\d+)?)%$")
# نام‌های کوتاه/لیگاتوردار PDF (pdftotext «لا» را «ال» می‌کند: فوالد) که با نام کامل TSETMC نمی‌خوانند؛ نمادها با پنل بازده تأیید شدند
ALIASES = {"ملی مس": "فملی", "فولاد مبارکه": "فولاد", "فوالد مبارکه": "فولاد", "نفت تهران": "شتران", "گل گهر": "کگل", "نفت و گاز پارسیان": "پارسان",
           "نفت اصفهان": "شپنا", "سرمایه گذاری غدیر": "وغدیر", "مخابرات": "اخابر", "کشتیرانی ایران": "حکشتی", "چادرملو": "کچاد",
           "سرمایه گذاری البرز": "والبر", "عمران فارس": "ثفارس"}
MARKS = re.compile(r"[‪-‮‎‏﻿]")


def text_of(pdf: Path) -> str:
    t = subprocess.run(["pdftotext", "-layout", "-q", str(pdf), "-"], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
    return MARKS.sub("", unicodedata.normalize("NFKC", t)).translate(pp.FA).replace("ي", "ی").replace("ك", "ک")


def num(s: str) -> float:
    return 0.0 if s == "-" else float(s.replace(",", ""))


def parse_pdf(pdf: Path):
    """(تاریخ میلادی پایان دوره، [ردیف‌ها]) یا (None, [])."""
    t = text_of(pdf)
    m = re.search(r"منتهی به\s*(1[34]\d{2})/(\d{1,2})/(\d{1,2})", t)
    if not m:
        return None, []
    d = j2g(*map(int, m.groups()))
    rows, on = [], False
    for ln in t.split("\n"):
        if re.search(r"درآمد", ln) and on and rows:
            break                                          # بخش‌های بعدی (درآمد/سود فروش) همان نام‌ها را با درصد درآمد تکرار می‌کنند
        if re.search(r"سرمایه\s*گذاری\s+در\s+سهام", ln):
            if not re.search(r"درآمد", ln):
                on = True                                  # سرتیتر جدول سهام؛ در هر صفحه تکرار می‌شود
            continue
        if on and re.search(r"-\s*2\b|-1-2|سپرده|گواهی سپرده|واحدهای صندوق", ln) and not PCT.match((ln.split() or [""])[0]):
            if rows:
                break
        if not on:
            continue
        toks = [x.strip() for x in re.split(r"\s{2,}", ln.strip()) if x.strip()]
        if len(toks) < 6 or not PCT.match(toks[0]):
            continue
        nums = [x for x in toks[1:] if NUM.match(x)]
        names = [x for x in toks[1:] if re.search(r"[آ-ی]", x)]
        if len(nums) < 4 or not names:
            continue
        nm = pp.norm(names[-1])
        if nm.startswith("جمع") or "نقل" in nm or nm.startswith("اختیار"):
            continue                                       # جمع ستون/صفحه («جمع نقل به صفحه بعد») و اختیار معامله (درصد ندارد/مجموع را دوبار می‌شمارد)
        rows.append({"name_fa": nm, "weight_pct": float(PCT.match(toks[0]).group(1)), "value": num(nums[0]),
                     "price": num(nums[2]), "qty": num(nums[3])})
    return str(d.date()) if hasattr(d, "date") else str(d), rows


def main():
    pdfs = sorted(RAW.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"ورودی نیست: {RAW}")
    names = pp.load_names()
    inv = {v: k for k, v in names.items()}
    recs, unmatched, skipped = [], {}, []
    for f in pdfs:
        d, rows = parse_pdf(f)
        if not d or not rows:
            skipped.append(f.name)
            continue
        tot = sum(r["weight_pct"] for r in rows)
        if not 50 <= tot <= 106:
            skipped.append(f"{f.name} (مجموع {tot:.0f}٪)")
            continue
        for r in rows:
            s = ALIASES.get(r["name_fa"].replace("  ", " ").strip()) or pp.match(r["name_fa"], names) or pp.price_match(r["name_fa"], r["price"], d, inv) or pp.cand_match(r["name_fa"], r["price"], d, names)
            if not s:
                unmatched[r["name_fa"]] = unmatched.get(r["name_fa"], 0) + 1
            recs.append({"date": d, "symbol": s, "name_fa": r["name_fa"], "weight_pct": round(r["weight_pct"], 4), "qty": r["qty"],
                         "price": r["price"], "matched": int(bool(s)), "weight_src": "pct"})
    if skipped:
        print("کنار گذاشته شد:", "؛ ".join(skipped))
    recs.sort(key=lambda r: (r["date"], -r["weight_pct"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    ds = sorted({r["date"] for r in recs})
    tot = {x: sum(r["weight_pct"] for r in recs if r["date"] == x) for x in ds}
    mt = {x: sum(r["weight_pct"] for r in recs if r["date"] == x and r["matched"]) for x in ds}
    print(f"کارآفرین: {len(ds)} ماه ({ds[0]} تا {ds[-1]})؛ میانگین سهام {sum(tot.values()) / len(ds):.1f}٪ از دارایی؛ "
          f"تطبیق‌یافته {sum(mt.values()) / sum(tot.values()) * 100:.1f}٪؛ میانگین تعداد نماد {len(recs) / len(ds):.0f}")
    if unmatched:
        print(f"تطبیق‌نیافته ({len(unmatched)}):", "؛ ".join(f"{n}×{c}" for n, c in sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]))
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
