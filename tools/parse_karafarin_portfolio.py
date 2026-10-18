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
import jalali  # noqa: E402
import parse_fund_portfolio as pp  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = ROOT / "data" / "raw" / "karafarin" / "portfolio"
OUT = ROOT / "data" / "funds" / "holdings_کارآفرین.csv"
NUM = re.compile(r"^(-|-?[\d,]+(\.\d+)?)$")      # «-» = صفر (قالب ۱۴۰۴ به بعد)
PCT = re.compile(r"^(\d+(?:\.\d+)?)%?$")      # قالب ۱۳۹۷ درصد را بدون «%» چاپ می‌کند
BIG = re.compile(r"\d{1,3},\d{3}")
# نام‌های کوتاه/لیگاتوردار PDF (pdftotext «لا» را «ال» می‌کند: فوالد) که با نام کامل TSETMC نمی‌خوانند؛ نمادها با پنل بازده تأیید شدند
ALIASES = {"ملی مس": "فملی", "فولاد مبارکه": "فولاد", "فوالد مبارکه": "فولاد", "نفت تهران": "شتران", "گل گهر": "کگل", "نفت و گاز پارسیان": "پارسان",
           "نفت اصفهان": "شپنا", "سرمایه گذاری غدیر": "وغدیر", "مخابرات": "اخابر", "کشتیرانی ایران": "حکشتی", "چادرملو": "کچاد",
           "سرمایه گذاری البرز": "والبر", "عمران فارس": "ثفارس",
           "مپنا": "رمپنا", "پتروشیمی تامین": "تاپیکو", "گروه توسعه ملی ایران": "وبانک", "پتروشیمی خلیج فارس": "فارس", "فولاد کاوه": "کاوه",
           "فولاد هرمزگان": "هرمز", "فولاد امیرکبیر": "فجر", "آذرآب": "فاذر", "پتروشیمی مبین": "مبین", "بورس اوراق بهادار تهران": "بورس",
           "سرمایه گذاری معادن و فلزات": "ومعادن"}
MARKS = re.compile(r"[‪-‮‎‏﻿]")


def text_of(pdf: Path) -> str:
    t = subprocess.run(["pdftotext", "-layout", "-q", str(pdf), "-"], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
    return MARKS.sub("", unicodedata.normalize("NFKC", t)).translate(pp.FA).replace("ي", "ی").replace("ك", "ک").replace("فوالد", "فولاد")


def num(s: str) -> float:
    return 0.0 if s == "-" else float(s.replace(",", ""))


def parse_pdf(pdf: Path):
    """(تاریخ میلادی پایان دوره، [ردیف‌ها]) یا (None, [])."""
    t = text_of(pdf)
    m = re.search(r"منتهی به\s*(1[34]\d{2})/(\d{1,2})/(\d{1,2})", t)
    if not m:
        return None, []
    d = jalali.j2g(*map(int, m.groups()), strict=False)       # تاریخ از pdftotext
    rows, on = [], False
    for ln in t.split("\n"):
        header_like = not BIG.search(ln)                   # سرتیتر/عنوان بخش: عدد هزارگان ندارد
        if on and rows and header_like and re.search(r"درآمد|سپرده|گواهی سپرده|اوراق|واحدهای صندوق|(^|\s)-\s*2\s*[آ-ی]|-1-2", ln):
            break                                          # بخش بعدی؛ جدول‌های درآمد همان نام‌ها را با درصد درآمد تکرار می‌کنند
        if header_like and re.search(r"سرمایه\s*گذاری\s+در\s+سهام", ln) and "درآمد" not in ln:
            on = True                                      # سرتیتر جدول سهام (در هر صفحه تکرار می‌شود)
            continue
        if header_like and "درصد" in ln and "تعداد" in ln:
            on = True                                      # سرستون ستون‌ها (قالب ۱۳۹۷ سرتیتر بخش ندارد)
            continue
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
        hint = pp.norm(names[-2]) if len(names) >= 2 and " " not in names[-2] and len(names[-2]) <= 9 else ""   # ستون «نماد» (قالب ۱۳۹۷)
        rows.append({"name_fa": nm, "symbol_hint": hint, "weight_pct": float(PCT.match(toks[0]).group(1)), "value": num(nums[0]),
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
            s = (r["symbol_hint"] if r["symbol_hint"] in inv else "") or ALIASES.get(r["name_fa"].replace("  ", " ").strip()) or pp.match(r["name_fa"], names) or pp.price_match(r["name_fa"], r["price"], d, inv) or pp.cand_match(r["name_fa"], r["price"], d, names)
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
