#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت پرتفوی ماهانهٔ صندوق‌های شاخصی از کدال (روی سیستم شما اجرا شود؛ محیط ابری به کدال دسترسی ندارد).

هدف: برای جداکردن «ترکیب پرتفوی» از «زمان‌بندی سود» در خطای ردیابی (فصل ۳ §۳٫۶)، موجودی هر صندوق در چند تاریخ لازم است.
ساختار نامه‌های پرتفوی کدال هنوز دیده نشده؛ مثل دفعهٔ سود نقدی، اول probe می‌کنیم و بعد parser می‌نویسیم.

    python tools/fetch_fund_portfolio.py --probe کاردان --log probe_port.txt
        همهٔ نامه‌های صندوق را فهرست می‌کند، کدها/عنوان‌ها را گروه می‌کند، عنوان‌های دارای «پرتفو/پورتفو/صورت وضعیت» را نشان
        می‌دهد و چند نمونه را (HTML و پیوند پیوست) در data/raw/codal/funds/<نماد>/ ذخیره می‌کند.
    python tools/fetch_fund_portfolio.py --collect 12 --log collect_port.txt
        برای هر ۸ صندوق، آخرین N نامهٔ پرتفو را (فاصلهٔ ۸ ثانیه، قابل‌ادامه، توقف روی 429) ذخیره می‌کند.

محدودیت کدال (429): همان قاعدهٔ fetch_dividend_payments.py؛ فاصلهٔ ۸ ثانیه و توقف فوری.
خروجی تحلیل بعد از parser: data/funds/holdings_<نماد>.csv با ستون‌های date,symbol,weight_pct  ← tools/analyze_fund_holdings.py
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

import fetch_dividend_payments as fdp   # فقط ابزارهای دریافت کدال همین مخزن (fetch، SEARCH، Blocked ...)

ROOT = fdp.ROOT
OUT = ROOT / "data" / "raw" / "codal" / "funds"
FUND_SYMBOLS = ["کاردان", "آرام", "وبازار", "هوشمند", "هم وزن", "هم تراز", "همسنگ", "فیروزه"]
KEYS = ("صورت وضعیت پورتفوی", "صورت وضعیت پرتفوی")   # نامهٔ ماهانهٔ پرتفوی (پیوست Excel)؛ در probe روی کاردان دیده شد


def list_all(sym: str) -> list:
    items = []
    for p in range(1, 40):
        d = fdp.fetch(fdp.SEARCH.format(page=p, sym=quote(sym))).json()
        got = d.get("Letters") or []
        items += got
        if p == 1:
            print(f"  Total={d.get('Total')}؛ کلیدهای یک نامه: {list(got[0].keys()) if got else '—'}")
        if len(items) >= d.get("Total", 0) or not got:
            break
    return items


def related(items: list) -> list:
    return [x for x in items if any(k in (x.get("Title") or "") for k in KEYS)]


def save_letter(sym: str, it: dict) -> None:
    d = OUT / sym
    d.mkdir(parents=True, exist_ok=True)
    tn = str(it.get("TracingNo"))
    stem = d / f"L_{tn}"
    if (d / f"L_{tn}.html").exists() and (any(d.glob(f"L_{tn}_att*")) or it.get("HasHtml")):
        return
    url = it.get("Url") or ""
    full = url if url.startswith("http") else "https://codal.ir" + url
    r = fdp.fetch(full)
    (d / f"L_{tn}.html").write_bytes(r.content)
    (d / f"L_{tn}.meta.json").write_text(json.dumps({k: it.get(k) for k in ("Title", "LetterCode", "PublishDateTime", "SentDateTime", "TracingNo", "Url", "HasHtml", "HasAttachment")}, ensure_ascii=False), encoding="utf-8")
    if it.get("HasAttachment") and not it.get("HasHtml"):
        # همان صفحهٔ Attachment.aspx پیوندها را دارد (یک درخواست کمتر)؛ تا اولین Excel دانلود می‌شود
        for k, link in enumerate(fdp.attachment_links(r.text)[:3]):
            rr = fdp.fetch("https://codal.ir" + link)
            path = fdp.save_attachment(rr, d / f"L_{tn}_att{k}")
            if str(path).lower().endswith((".xlsx", ".xls")):
                break


def probe(sym: str, n_save: int) -> None:
    print(f"\n══ {sym} ══")
    items = list_all(sym)
    (OUT / sym).mkdir(parents=True, exist_ok=True)
    (OUT / sym / "list.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    by = defaultdict(list)
    for x in items:
        by[x.get("LetterCode")].append(x.get("Title", ""))
    print(f"نامه‌ها: {len(items)}؛ گروه‌بندی بر پایهٔ LetterCode:")
    for c, ts in sorted(by.items(), key=lambda kv: -len(kv[1]))[:25]:
        print(f"  {c!s:8s} {len(ts):4d}  {ts[0][:90]}")
    rel = related(items)
    print(f"عنوان‌های مرتبط با پرتفو: {len(rel)}")
    for x in rel[:15]:
        print(f"  {x.get('PublishDateTime')} | {x.get('LetterCode')} | {x.get('Title', '')[:90]} | HasHtml={x.get('HasHtml')} Att={x.get('HasAttachment')} | {x.get('Url')}")
    for x in rel[:n_save]:
        try:
            save_letter(sym, x)
        except fdp.Blocked:
            raise
        except Exception as e:  # noqa: BLE001
            print("  ذخیره ناموفق:", e)
    if rel:
        f = OUT / sym / f"L_{rel[0].get('TracingNo')}.html"
        if f.exists():
            print("\n── متن نمونهٔ آخرین نامه (۱۲۰۰ نویسه) ──")
            print(fdp.text_of(f.read_text(encoding="utf-8", errors="replace"))[:1200])


def collect(n: int) -> None:
    for sym in FUND_SYMBOLS:
        print(f"\n══ {sym} ══")
        try:
            items = list_all(sym)
            rel = sorted(related(items), key=lambda x: str(x.get("PublishDateTime")), reverse=True)[:n]
            print(f"  نامهٔ مرتبط: {len(rel)}")
            for x in rel:
                save_letter(sym, x)
        except fdp.Blocked:
            print("  ⛔ کدال محدودیت داد؛ چند ساعت بعد همین دستور را دوباره بزنید (ادامه می‌دهد).")
            return
        except Exception as e:  # noqa: BLE001
            print("  خطا:", e)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", help="نماد صندوق (مثلاً کاردان)")
    ap.add_argument("--collect", type=int, help="آخرین N نامهٔ پرتفو برای هر صندوق (پیشنهاد ۲۴ ≈ ۲ سال؛ ۲ درخواست برای هر نامه)")
    ap.add_argument("--save", type=int, default=3, help="در --probe چند نمونه ذخیره شود")
    ap.add_argument("--gap", type=float, default=8.0)
    ap.add_argument("--log", help="کپی خروجی در فایل UTF-8")
    a = ap.parse_args()
    fdp.MIN_GAP = a.gap
    fdp.PATIENT[0] = False
    if a.log:
        sys.stdout = fdp.Tee(a.log)
    if a.probe:
        probe(a.probe, a.save)
    elif a.collect:
        collect(a.collect)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
