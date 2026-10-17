#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تبدیل پیوندهای Excel پرتفوی ماهانهٔ صندوق‌ها (کدال) به data/funds/holdings_<نماد>.csv

    python tools/parse_fund_portfolio.py

ورودی: data/raw/codal/funds/<نماد>/L_<TracingNo>.meta.json و L_<TracingNo>_att*.xlsx (برگهٔ «سهام»: صورت وضعیت پرتفوی).
خروجی: date (پایان ماه، ISO)، symbol (نماد TSETMC یا خالی)، name_fa (نام در کدال)، weight_pct (درصد از کل دارایی‌ها)،
       qty، price، matched. نمادهای تطبیق‌نیافته در data/funds/holdings_unmatched.csv.
"""
import csv
import difflib
import re
import json
import sys
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_index_funds import j2g, norm  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "codal" / "funds"
OUT = ROOT / "data" / "funds"
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def key(s: str) -> str:
    s = norm(s).replace("‌", " ")
    s = re.sub(r"[\s\.\-\(\)،,_]+", "", s)
    return s


def load_names() -> dict:
    """نام کامل و نماد هر سهم (instruments.csv، instruments_extra.csv) → نماد. فقط سهام."""
    out = {}
    for fn in ("instruments.csv", "instruments_extra.csv"):
        p = ROOT / "data" / fn
        if not p.exists():
            continue
        for r in csv.DictReader(p.open(encoding="utf-8")):
            if r.get("type", "stock") not in ("stock", "fund", ""):
                continue
            sym = norm(r["symbol"])
            if re.search(r"\d$", sym):
                continue
            out.setdefault(key(r["name"]), sym)
            out.setdefault(key(sym), sym)
    return out


# نام کدال که با نام TSETMC فرق دارد (با خروجی holdings_unmatched.csv تکمیل شود)
ALIASES = {"سنگ آهن گهرزمین": "کگهر"}


def match(name: str, names: dict) -> str:
    m = re.search(r"\(([^()]+)\)\s*$", norm(name))
    if m and key(m.group(1)) in names:                         # کیان و ...: «نام شرکت (نماد)»
        return names[key(m.group(1))]
    k = key(name)
    for a, sym in ALIASES.items():
        if key(a) == k:
            return sym
    if k in names:
        return names[k]
    if name.strip().startswith(("ح .", "ح.", "ح ")):
        return ""                                              # حق تقدم
    cand = difflib.get_close_matches(k, names.keys(), n=1, cutoff=0.9)
    return names[cand[0]] if cand else ""


_PX = {}


def price_index():
    """(تاریخ معاملاتی → {قیمت پایانی: [نماد…]}) از پنل سهام بورسی؛ برای تطبیق نام‌های کوتاه‌شدهٔ کدال با قیمت همان روز."""
    if not _PX:
        import build_ui_extra as bx
        _, _, R = bx.base_panel()
        R = R[R.date >= "2022-01-01"]
        R = R.assign(sym=R.symbol.map(norm))
        for d, g in R.groupby("date"):
            m = {}
            for sym, pc in zip(g.sym, g.pClosing):
                m.setdefault(int(round(pc)), []).append(sym)
            _PX[d] = m
        _PX["_dates"] = sorted(k for k in _PX if k != "_dates")
    return _PX


def price_match(name: str, price, date_iso: str, inv_names: dict) -> str:
    try:
        pr = int(round(float(price)))
    except (TypeError, ValueError):
        return ""
    import pandas as pd
    px = price_index()
    ds = [d for d in px["_dates"] if d <= pd.Timestamp(date_iso)]
    for d in ds[-3:][::-1]:                               # آخرین روز معاملاتی تا ۲ روز قبل (روز تعطیل)
        cand = px[d].get(pr, [])
        if len(cand) == 1:
            return cand[0]
        if len(cand) > 1:
            k = key(name)
            best = max(cand, key=lambda c: difflib.SequenceMatcher(None, k, key(inv_names.get(c, c))).ratio())
            return best
    return ""


def month_end(title: str):
    m = re.search(r"منتهی\s*به\s*([\d۰-۹]{4})/([\d۰-۹]{1,2})/([\d۰-۹]{1,2})", title.translate(FA).replace("‌", " "))
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return j2g(y, mo, d).isoformat()


def read_sheets(path: Path) -> list:
    """[(نام برگه، ردیف‌ها)] برای xlsx، xlsx با پسوند اشتباه (zip/30/…) و xls قدیمی؛ نوع فایل از امضای آن تشخیص داده می‌شود."""
    import io
    data = path.read_bytes()
    if data[:2] == b"PK":
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        return [(ws.title, list(ws.iter_rows(values_only=True))) for ws in wb.worksheets]
    if data[:4] == b"\xd0\xcf\x11\xe0":
        import xlrd
        wb = xlrd.open_workbook(file_contents=data)
        return [(sh.name, [tuple(sh.row_values(r)) for r in range(sh.nrows)]) for sh in wb.sheets()]
    return []


MARKS = dict.fromkeys(map(ord, "\u202a\u202b\u202c\u202d\u202e\u200e\u200f\ufeff"))


def clean(v) -> str:
    return str(v).translate(MARKS).strip()


def parse_xlsx(path: Path) -> list[dict]:
    """برگهٔ سهام: قالب صندوق‌ها فرق دارد (نام ستون «شرکت»/«نام شرکت»، ردیف سرستون ۶ تا ۹)؛ ستون «درصد … دارایی» از ۳ ردیف سرستون پیدا می‌شود."""
    for title, rows in read_sheets(path):
        hdr = None
        for i, r in enumerate(rows[:40]):
            cells = [clean(v) for v in (r or ()) if v is not None]
            if any(c in ("شرکت", "نام شرکت", "نام سهام") for c in cells):
                blk = [clean(v) for rr in rows[i:i + 3] for v in (rr or ()) if v is not None]
                if any("درصد" in c and "دارایی" in c for c in blk) and "قیمت" in " ".join(blk):
                    hdr = i
                    break
        if hdr is None:
            continue

        def last(lab, both=None):
            best = None
            for rr in rows[hdr:hdr + 3]:
                for j, v in enumerate(rr or ()):
                    if v is not None and lab in clean(v) and (both is None or both in clean(v)):
                        best = j if best is None else max(best, j)
            return best
        c_pct, c_price, c_qty, c_val = last("درصد", "دارایی"), last("قیمت بازار"), last("تعداد"), last("خالص ارزش فروش")
        c_nm = next((j for j, v in enumerate(rows[hdr]) if v is not None and clean(v) in ("شرکت", "نام شرکت", "نام سهام")), 0)
        out = []
        for r in rows[hdr + 2:]:
            if not r or c_nm >= len(r) or r[c_nm] is None or clean(r[c_nm]) == "":
                continue
            nm = clean(r[c_nm])
            if nm.startswith("جمع"):
                break
            if nm.startswith(("نقل از", "نقل به")):         # ردیف جمع انتقالی بین صفحه‌ها (فیروزه، وبازار، ...) دوباره‌شماری می‌کند
                continue
            v = r[c_pct] if c_pct is not None and c_pct < len(r) else None
            if isinstance(v, (int, float)):
                val = r[c_val] if c_val is not None and c_val < len(r) else None
                out.append({"name_fa": nm, "weight_pct": float(v), "qty": r[c_qty] if c_qty is not None and c_qty < len(r) else None,
                            "price": r[c_price] if c_price is not None and c_price < len(r) else None,
                            "value": float(val) if isinstance(val, (int, float)) else None})
        if out:
            if sum(o["weight_pct"] for o in out) <= 1.5:          # برخی صندوق‌ها کسر (۰ تا ۱) می‌نویسند نه درصد
                for o in out:
                    o["weight_pct"] *= 100
            return out
    return []


def main():
    names = load_names()
    inv = {v: k for k, v in names.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    unmatched = {}
    for fdir in sorted(p for p in RAW.iterdir() if p.is_dir()):
        sym = fdir.name
        recs = []
        for mp in sorted(fdir.glob("L_*.meta.json")):
            meta = json.loads(mp.read_text(encoding="utf-8"))
            title = meta.get("Title") or ""
            if "پورتفوی" not in title and "پرتفوی" not in title:
                continue
            d = month_end(title)
            xs = sorted(fdir.glob(mp.name.replace(".meta.json", "_att*")))
            if not d or not xs:
                continue
            pub = str(meta.get("PublishDateTime") or "").translate(FA)[:10].replace("/", "-")
            if re.match(r"\d{4}-\d\d-\d\d", pub) and d > j2g(*(int(x) for x in pub.split("-"))).isoformat():
                continue                                   # تاریخ آیندهٔ اشتباه در عنوان (مثلاً ۱۴۰۶ به‌جای ۱۴۰۵)
            for it in parse_xlsx(xs[0]):
                s = match(it["name_fa"], names) or price_match(it["name_fa"], it["price"], d, inv)
                if not s:
                    unmatched[(sym, it["name_fa"])] = unmatched.get((sym, it["name_fa"]), 0) + 1
                recs.append({"date": d, "symbol": s, "name_fa": it["name_fa"], "weight_pct": round(it["weight_pct"], 4),
                             "qty": it["qty"], "price": it["price"], "matched": int(bool(s)), "weight_src": "pct", "_value": it.get("value")})
        if not recs:
            continue
        tot = {}
        for r in recs:
            tot[r["date"]] = tot.get(r["date"], 0) + r["weight_pct"]
        bad = sorted(d for d, v in tot.items() if not 50 <= v <= 106)   # مجموع سهام باید ۵۰ تا ~۱۰۵٪ دارایی باشد؛ غیر از این یعنی ستون/برگهٔ اشتباه خوانده شده
        if bad:
            print(f"  {sym}: {len(bad)} ماه با مجموع نامعتبر کنار گذاشته شد: " + "، ".join(f"{d} ({tot[d]:.0f}٪)" for d in bad[:6]))
        # ستون «درصد» در برخی ماه‌ها مقدار ذخیره‌شدهٔ فرمول کهنه دارد (مثلاً فیروزه)؛ جایگزین: وزن از «خالص ارزش فروش» نسبت به جمع سهام
        # (نقد و سایر دارایی‌ها در این ماه‌ها معلوم نیست ⇒ مجموع سهام ۱۰۰٪ فرض می‌شود و weight_src = value)
        fixed = []
        for d in list(bad):
            rr = [r for r in recs if r["date"] == d]
            vs = [r["_value"] for r in rr]
            if rr and all(v is not None and v >= 0 for v in vs) and sum(vs) > 0:
                for r_, v in zip(rr, vs):
                    r_["weight_pct"] = round(v / sum(vs) * 100, 4)
                    r_["weight_src"] = "value_norm"
                fixed.append(d)
        bad = [d for d in bad if d not in fixed]
        if fixed:
            print(f"  {sym}: {len(fixed)} ماه با وزن از ارزش فروش بازسازی شد (نقد نامعلوم): " + "، ".join(fixed[:5]))
        recs = [r for r in recs if r["date"] not in bad]
        for r in recs:
            r.pop("_value", None)
        if not recs:
            continue
        recs.sort(key=lambda r: (r["date"], -r["weight_pct"]))
        with (OUT / f"holdings_{sym}.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
            w.writeheader()
            w.writerows(recs)
        ds = sorted({r["date"] for r in recs})
        tot = {d: sum(r["weight_pct"] for r in recs if r["date"] == d) for d in ds}
        mt = {d: sum(r["weight_pct"] for r in recs if r["date"] == d and r["matched"]) for d in ds}
        print(f"{sym}: {len(ds)} ماه ({ds[0]} تا {ds[-1]})؛ میانگین سهام {sum(tot.values())/len(ds):.1f}٪ از دارایی؛ تطبیق‌یافته {sum(mt.values())/sum(tot.values())*100:.1f}٪؛ "
              f"میانگین تعداد نماد {len(recs)/len(ds):.0f}")
    if unmatched:
        with (OUT / "holdings_unmatched.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["fund", "name_fa", "months"])
            for (f, n), c in sorted(unmatched.items(), key=lambda kv: (-kv[1], kv[0])):
                w.writerow([f, n, c])
        print(f"تطبیق‌نیافته: {len(unmatched)} (فایل holdings_unmatched.csv)")


if __name__ == "__main__":
    main()
