#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پارس پست‌های «زمان‌بندی پرداخت سود نقدی» کارگزاری فارابی ← جدول تاریخ واقعی پرداخت (فصل ۱۰، 7f).

ورودی: data/raw/farabi/posts_cat*_p*.json  (tools/fetch_farabi_dividends.py)
خروجی: data/corporate_actions/payment_dates_farabi.csv با ستون‌های
    symbol, holder (sejam|nonsejam), agm_j, fiscal_end_j, dps_rial, pay_text, pay_j, pay_kind (day|from|month|range), method,
    post_id, post_date, src (table|prose)

دو قالب پست:
  الف) جدول HTML با سرستون «نام نماد | سجام سهامدار | زمان مجمع | سود نقدی … | تاریخ واریز | نحوه پرداخت» (پست‌های ماهانه/هفتگی و تجمیعی ۱۴۰۴–۱۴۰۵)
  ب) متن آزاد «پیرو اطلاعیه … با نماد “X” برای سال مالی منتهی به … سهامدارانی که در تاریخ D … مشمول دریافت N ریال …» (پست‌های هر نماد، ۱۴۰۲)
تاریخ پرداخت می‌تواند روز دقیق (day)، «از …» (from)، فقط ماه (month؛ روز ۱۵ فرض می‌شود، ±۱۵ روز) یا بازه (range؛ ابتدای بازه) باشد.
اگر یک (نماد، سجامی/غیرسجامی، تاریخ مجمع) در چند پست بیاید، جدیدترین پست می‌ماند (پست تجمیعی به‌روزرسانی می‌شود).
"""
import json
import re
import sys
import unicodedata
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import jalali  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RAW = ROOT / "data" / "raw" / "farabi"
OUT = ROOT / "data" / "corporate_actions" / "payment_dates_farabi.csv"
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك", "01234567890123456789یک")
MONTHS = {"فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4, "مرداد": 5, "شهریور": 6, "مهر": 7, "آبان": 8, "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12}
MON_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
DATE = re.compile(r"(1[34]\d{2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})")
DAYMON = re.compile(r"(\d{1,2})\s*(?:ام)?\s*(" + MON_RE + r")(?:\s*ماه)?(?:\s*(1[34]\d{2}))?")
ONLYMON = re.compile(r"(" + MON_RE + r")\s*ماه")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", unescape(t or "")).translate(FA)
    return re.sub(r"[‌‏‎‪-‮]", " ", t).replace("\xa0", " ")


def clean(t: str) -> str:
    return re.sub(r"\s+", " ", norm(t)).strip()


def g(jd: str):
    return pd.Timestamp(jalali.parse_j(jd, strict=False))     # متن پست‌ها: روز نامعتبر بُرش می‌خورد


def jd_of(y, m, d) -> str | None:
    y, m, d = int(y), int(m), int(d)
    return f"{y:04d}/{m:02d}/{d:02d}" if 1 <= m <= 12 and 1 <= d <= 31 else None


class Tables(HTMLParser):
    """جدول‌ها را به‌صورت فهرست ردیف‌ها (فهرست متن سلول‌ها) درمی‌آورد."""

    def __init__(self):
        super().__init__()
        self.tables, self._row, self._cell, self._in = [], None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(clean("".join(self._cell)))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            if any(self._row):
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_pay(text: str, agm_j: str | None) -> tuple:
    """(تاریخ شمسی، نوع) از متن ستون «تاریخ واریز»."""
    t = clean(text)
    if not t or t in ("—", "-", "–"):
        return None, None
    lead_from = t.startswith("از")
    ds = [jd_of(*m.groups()) for m in DATE.finditer(t)]
    ds = [d for d in ds if d]
    if ds:
        return ds[0], ("from" if lead_from else "range" if re.search(r"الی|تا", t) and len(ds) > 1 else "day")
    m = DAYMON.search(t)
    anchor = g(agm_j) if agm_j else None
    if m:
        d, mon, y = m.groups()
        mo = MONTHS[mon]
        years = [int(y)] if y else ([int(agm_j[:4]), int(agm_j[:4]) + 1] if agm_j else [])
        for yy in years:
            jd = jd_of(yy, mo, d)
            if jd and (anchor is None or anchor < g(jd) <= anchor + pd.Timedelta(days=330)):
                return jd, ("range" if re.search(r"الی|تا", t) else "from" if lead_from else "day")
        return None, None
    m = ONLYMON.search(t)
    if m and agm_j:
        mo = MONTHS[m.group(1)]
        day = 1 if "ابتدای" in t else 15
        for yy in (int(agm_j[:4]), int(agm_j[:4]) + 1):
            jd = jd_of(yy, mo, day)
            if jd and anchor < g(jd) <= anchor + pd.Timedelta(days=330):
                return jd, "month"
    return None, None


def holder_of(txt: str) -> str:
    t = clean(txt)
    return "nonsejam" if ("غیر" in t or "غیرسجام" in t) else "sejam"


def parse_dps(txt: str) -> float | None:
    m = re.search(r"([\d,\.]+)", clean(txt).replace("٬", ","))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def table_rows(post: dict) -> list:
    tp = Tables()
    tp.feed(post["content"]["rendered"])
    out = []
    for tb in tp.tables:
        head = None
        for i, row in enumerate(tb):
            hs = " ".join(row)
            if "نماد" in hs and ("واریز" in hs or "مجمع" in hs) and head is None:
                head = {k: next((j for j, c in enumerate(row) if kw in c), None)
                        for k, kw in (("sym", "نماد"), ("holder", "سجام"), ("agm", "مجمع"), ("dps", "سود"), ("pay", "واریز"), ("how", "نحوه"))}
                continue
            if head is None or head["sym"] is None or head["pay"] is None:
                continue
            get = lambda k: row[head[k]] if head[k] is not None and head[k] < len(row) else ""   # noqa: E731
            sym = get("sym")
            if not sym:
                continue
            am = DATE.search(get("agm"))
            agm_j = jd_of(*am.groups()) if am else None
            pay_j, kind = parse_pay(get("pay"), agm_j)
            out.append({"symbol": sym.replace("‌", " ").strip(), "holder": holder_of(get("holder")), "agm_j": agm_j or "", "fiscal_end_j": "",
                        "dps_rial": parse_dps(get("dps")), "pay_text": get("pay"), "pay_j": pay_j or "", "pay_kind": kind or "",
                        "method": get("how"), "src": "table"})
    return out


def prose_rows(post: dict) -> list:
    t = clean(re.sub(r"<[^>]+>", " ", post["content"]["rendered"]))
    ttl = clean(post["title"]["rendered"])
    sm = re.search(r"با نماد\s*[“\"«]\s*([^”\"»]+?)\s*[”\"»]", t) or re.search(r"نماد\s+(\S+)\s*$", ttl)
    if not sm:
        return []
    sym = sm.group(1).strip()
    fe = re.search(r"منتهی به\s*(1[34]\d{2}/\d{1,2}/\d{1,2})", t)
    am = re.search(r"در تاریخ\s*(1[34]\d{2}/\d{1,2}/\d{1,2})\s*سهامدار", t)
    dm = re.search(r"دریافت\s*([\d,\.]+)\s*ریال", t)
    agm_j = jd_of(*DATE.search(am.group(1)).groups()) if am else None
    rows = []
    for sent in re.split(r"(?<=[\.؛])\s+|\n", t):
        ds = [jd_of(*m.groups()) for m in DATE.finditer(sent)]
        ds = [d for d in ds if d and d != agm_j and (not fe or d != jd_of(*DATE.search(fe.group(1)).groups()))]
        if not ds or not ("سجام" in sent or "واریز" in sent or "پرداخت" in sent):
            continue
        hold = "nonsejam" if re.search(r"غیر\s*سجام|فاقد|شعب|مراجعه", sent) else "sejam"
        pay_j, kind = parse_pay(sent, agm_j)
        if not pay_j:
            pay_j, kind = ds[0], "day"
        rows.append({"symbol": sym, "holder": hold, "agm_j": agm_j or "", "fiscal_end_j": jd_of(*DATE.search(fe.group(1)).groups()) if fe else "",
                     "dps_rial": parse_dps(dm.group(1)) if dm else None, "pay_text": sent[:160], "pay_j": pay_j, "pay_kind": kind, "method": "", "src": "prose"})
    return rows


def main():
    files = sorted(RAW.glob("posts_cat*_p*.json"))
    if not files:
        sys.exit(f"ورودی نیست: {RAW} (ابتدا tools/fetch_farabi_dividends.py)")
    posts = {}
    for f in files:
        for p in json.loads(f.read_text(encoding="utf-8")):
            posts[p["id"]] = p
    print(f"{len(posts)} پست از {len(files)} فایل")
    rows = []
    n_tab = n_pro = 0
    for p in posts.values():
        r = table_rows(p)
        src = "table"
        if not r:
            r = prose_rows(p)
            src = "prose"
        if not r:
            continue
        n_tab += src == "table"
        n_pro += src == "prose"
        for x in r:
            rows.append({**x, "post_id": p["id"], "post_date": p["date"][:10], "post_title": clean(p["title"]["rendered"])[:80]})
    D = pd.DataFrame(rows)
    D = D.sort_values(["post_date", "post_id"]).drop_duplicates(["symbol", "holder", "agm_j"], keep="last").sort_values(["agm_j", "symbol", "holder"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    D.to_csv(OUT, index=False, encoding="utf-8")
    ok = D[D.pay_j != ""]
    print(f"پست جدولی {n_tab}، متنی {n_pro}؛ ردیف {len(D)} ({D.symbol.nunique()} نماد)؛ با تاریخ پرداخت {len(ok)}")
    print("نوع تاریخ:", ok.pay_kind.value_counts().to_dict(), "| سجامی:", int((ok.holder == 'sejam').sum()))
    sj = ok[(ok.holder == "sejam") & (ok.agm_j != "")].copy()
    sj["lag"] = [(g(p) - g(a)).days for p, a in zip(sj.pay_j, sj.agm_j)]
    for k, x in sj.groupby("pay_kind"):
        print(f"  تأخیر مجمع→پرداخت سجامی [{k}] n={len(x)} میانه={x.lag.median():.0f} چارک‌ها={x.lag.quantile(.25):.0f}–{x.lag.quantile(.75):.0f}")
    sj["year"] = sj.agm_j.str[:4]
    for y, x in sj.groupby("year"):
        print(f"  مجمع {y}: n={len(x)} میانه={x.lag.median():.0f}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
