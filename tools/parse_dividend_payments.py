#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""استخراج تاریخ واقعی پرداخت سود از پیوست‌های «زمان‌بندی پرداخت سود» کدال (ن-۱۳) و محاسبهٔ تأخیر.

    python tools/parse_dividend_payments.py            # متن (pdftotext) ← جدول‌ها؛ OCR به‌طور پیش‌فرض خاموش است
    python tools/parse_dividend_payments.py --ocr      # (فقط اگر خواستید) OCR PDFهای اسکن‌شده؛ متن‌های OCR موجود در کش همیشه استفاده می‌شوند

ورودی:  data/raw/codal/collect/<نماد>/30_<TracingNo>_att*.{pdf,jpg,…}  (tools/fetch_dividend_payments.py --attachments)
        data/corporate_actions/codal_agm.csv  (تاریخ مجمع و سود هر سهم؛ --parse)
وابستگی: pdftotext و pdftoppm (poppler)، tesseract با زبان fas برای PDFهای اسکن‌شده (~۷۰٪ پیوست‌ها).
خروجی:
    data/raw/codal/text/<نماد>__<TracingNo>.txt            متن استخراج‌شده (کش؛ OCR دوباره لازم نیست)
    data/corporate_actions/codal_payment_dates.csv          هر پیوست: تاریخ‌های پرداخت به تفکیک گروه سهامدار
    data/corporate_actions/dividend_payment_lags.csv        هر رویداد سود: تاریخ مجمع، DPS، شروع پرداخت (صندوق/حقوقی، سجامی، اولین)، تأخیر به روز

روش (قاعده‌محور، فصل ۲ §۲٫۴ و فصل ۱۰ 7f):
  ۱) سال مالی و تاریخ انتشار هر نامه از «عنوان» نامه در list_30.json (نه از متن پیوست)؛ تاریخ مجمع و DPS از codal_agm.csv با کلید (نماد، پایان سال مالی)؛
     تاریخ استحقاق (ex-date) = روز تعدیل قیمت TSETMC که تفاضلش برابر DPS است (price_adjust.csv) و ۰ تا ۱۲ روز بعد از مجمع است.
  ۲) در متن هر تاریخ (۱۴۰۴/۰۸/۲۳ یا «۵ مرداد ۱۴۰۵») که از ۵ روز قبل از مجمع تا ۴۰۰ روز بعد باشد «تاریخ پرداخت» است. بندهای مربوط به مطالبات سنواتی کنار گذاشته می‌شوند.
  ۳) متن به «بند» (الف/ب/ج، شمارهٔ بند، یا خط خالی) شکسته می‌شود و گروه هر تاریخ از کلیدواژه‌های همان بند می‌آید:
     صندوق (صندوق/سبد)، سجامی (حقیقیِ دارای سجام)، غیرسجامی (ننموده/فاقد/مراجعه به شعب)، حقوقی، عمده.
  ۴) «تاریخ مؤثر برای صندوق» = تاریخ سجامی (صندوق‌ها و سبدهای ثبت‌نام‌شده در سجام معمولاً با حقیقی‌ها یک‌جا می‌گیرند؛ تاریخ «صندوق» جداگانه پرحاشیه است چون در جدول‌های pdftotext
     سلول‌ها روی خط‌های مجاور می‌ریزند)، وگرنه تاریخ صریح صندوق، وگرنه اولین تاریخ نامه؛ ستون basis. تاریخ صریح صندوق به‌عنوان حساسیت نگه داشته می‌شود (lag_fund).
  ۵) برای هر رویداد (نماد × سال مالی) آخرین نامه (اصلاحیه) برای هر گروه ملاک است.
متن‌های OCR که پیشتر در کش مانده‌اند استفاده می‌شوند و با method=ocr علامت می‌خورند (خطاهای OCR با فیلتر بازهٔ تاریخ تا حد زیادی حذف می‌شوند)؛ OCR تازه فقط با --ocr.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import jalali  # noqa: E402

os.environ.setdefault("OMP_THREAD_LIMIT", "1")   # هر فرایند tesseract یک رشته؛ موازی‌سازی با --workers
RAW = ROOT / "data" / "raw" / "codal"
TXT = RAW / "text"
OUT = ROOT / "data" / "corporate_actions"
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يك", "01234567890123456789یک")
DATE = re.compile(r"(1[34]\d{2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})")
GROUPS = [  # ترتیب مهم است: اول خاص‌ترها
    ("fund", ("صندوق", "سبد")),
    ("major", ("عمده",)),
    ("nonsejam", ("ننموده", "غیر سجام", "غیرسجام", "شعب")),
    ("legal", ("حقوقی",)),
    ("sejam", ("سجام",)),
]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "").translate(FA)
    return re.sub(r"[‌‏‎‪-‮]", " ", t)


def kind(path: Path) -> str:
    b = path.read_bytes()[:8]
    return "pdf" if b.startswith(b"%PDF") else "img" if b[:3] == b"\xff\xd8\xff" or b.startswith(b"\x89PNG") else "other"


def extract(path: Path, ocr: bool) -> tuple:
    """(متن، روش) برای یک پیوست، با کش."""
    cache = TXT / f"{path.parent.name}__{path.stem}.txt"
    if cache.exists():
        t = cache.read_text(encoding="utf-8")
        return t, t.split("\n", 1)[0].strip("# ")
    k = kind(path)
    text, how = "", "none"
    if k == "pdf":
        text = subprocess.run(["pdftotext", "-layout", "-q", str(path), "-"], capture_output=True, timeout=120).stdout.decode("utf-8", "replace")
        how = "pdftotext"
        if len(re.findall(r"[؀-ۿﭐ-﻿]", text)) < 80 and ocr:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                subprocess.run(["pdftoppm", "-scale-to", "2200", "-png", "-l", "3", str(path), f"{td}/p"], capture_output=True, timeout=300)
                pages = sorted(Path(td).glob("p*.png"))
                text = "\n".join(subprocess.run(["tesseract", str(p), "-", "-l", "fas"], capture_output=True, timeout=300).stdout.decode("utf-8", "replace") for p in pages)
                how = f"ocr({len(pages)}p)"
    elif k == "img" and ocr:
        import tempfile
        from PIL import Image
        with tempfile.TemporaryDirectory() as td:
            im = Image.open(path)
            im.thumbnail((2200, 2200 * 2))
            im.convert("L").save(f"{td}/i.png")
            text = subprocess.run(["tesseract", f"{td}/i.png", "-", "-l", "fas"], capture_output=True, timeout=300).stdout.decode("utf-8", "replace")
        how = "ocr(img)"
    TXT.mkdir(parents=True, exist_ok=True)
    cache.write_text(f"# {how}\n" + text, encoding="utf-8")
    return text, how


def _job(args):
    p, ocr = args
    try:
        return str(p), *extract(p, ocr)
    except Exception as e:  # noqa: BLE001
        return str(p), "", f"error:{type(e).__name__}"



MONTHS = {"فروردین": 1, "اردیبهشت": 2, "خرداد": 3, "تیر": 4, "مرداد": 5, "شهریور": 6, "مهر": 7, "آبان": 8, "آذر": 9, "دی": 10, "بهمن": 11, "اسفند": 12}
DATE_NAME = re.compile(r"(\d{1,2})\s*(?:ام)?\s*(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")(?:\s*ماه)?(?:\s*سال)?\s*(1[34]\d{2})")
ARREARS = ("سنوات", "سنواتی", "سالهای قبل", "سال های قبل", "سالهای گذشته", "مانده مطالبات", "مطالبات سنوات")
NEG = ("فاقد", "ننموده", "نکرده", "نشده", "غیر سجام", "غیرسجام", "مراجعه", "شعب", "حضوری")
MARK = re.compile(r"^\s*(?:[الف-ی]|\d{1,2})\s*[\)\-_.:－–]")


def jdate(m) -> str | None:
    y, mo, d = map(int, m)
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}/{mo:02d}/{d:02d}"


def g(jd: str) -> pd.Timestamp:
    """تاریخ از متن/OCR: روز نامعتبر به آخرین روز ماه بُرش می‌خورد (ماه نامعتبر همچنان ValueError)."""
    return pd.Timestamp(jalali.parse_j(jd, strict=False))


def items_of(text: str) -> list:
    """بندهای متن (هر بند فهرستی از خطوط): خطی که با «الف)»/«۱-» شروع شود بند تازه است؛ خط خالی هم بند را می‌بندد."""
    out, cur = [], []
    for line in norm(text).split("\n"):
        if not line.strip():
            if cur:
                out.append(cur); cur = []
            continue
        if MARK.match(line) and cur:
            out.append(cur); cur = []
        cur.append(line.strip())
    if cur:
        out.append(cur)
    return out


def dates_in(line: str) -> list:
    res = []
    for m in DATE.finditer(line):
        jd = jdate(m.groups())
        if jd:
            res.append(jd)
    for m in DATE_NAME.finditer(line):
        d, mon, y = m.groups()
        jd = jdate((y, MONTHS[mon], d))
        if jd:
            res.append(jd)
    return res


def groups_of(txt: str) -> set:
    neg = any(w in txt for w in NEG)
    grp = set()
    if any(w in txt for w in ("صندوق", "سبد")):
        grp.add("fund")
    if "عمده" in txt:
        grp.add("major")
    if "حقوقی" in txt and "حقیقی" not in txt.split("حقوقی")[0][-40:]:
        grp.add("legal")
    if neg and ("حقیقی" in txt or "سجام" in txt or "فاقد" in txt):
        grp.add("nonsejam")
    if ("حقیقی" in txt or "سجام" in txt or "سبد" in txt or "صندوق" in txt) and not neg:
        grp.add("sejam")
    return grp


def classify(text: str, anchor: pd.Timestamp | None, pub: str | None = None) -> dict:
    """تاریخ‌های پرداخت به تفکیک گروه. anchor = تاریخ مجمع؛ اگر None، فیلتر بازه اعمال نمی‌شود.
    تاریخ خودِ مجمع (تا ۱ روز بعد) و تاریخ انتشار/سربرگ نامه پرداخت نیستند. خطی که «سنوات/مطالبات سالهای قبل» دارد کنار گذاشته می‌شود.
    گروه هر تاریخ: کلیدواژه‌های همان خط و دو خط مجاور (جدول‌های pdftotext سلول را روی خط‌های کنار هم می‌ریزند)؛ اگر نبود، کل بند."""
    out = {k: [] for k, _ in GROUPS} | {"any": []}
    for lines in items_of(text):
        item_txt = " ".join(lines)
        for i, ln in enumerate(lines):
            if any(w in ln for w in ARREARS):
                continue
            for jd in dates_in(ln):
                try:
                    gd = g(jd)
                except Exception:  # noqa: BLE001
                    continue
                if anchor is not None and not (anchor + pd.Timedelta(days=2) <= gd <= anchor + pd.Timedelta(days=400)):
                    continue
                if pub and jd == pub:
                    continue
                grp = groups_of(" ".join(lines[max(0, i - 1):i + 2])) or groups_of(item_txt)
                out["any"].append(jd)
                for k in grp:
                    out[k].append(jd)
    return {k: sorted(set(v)) for k, v in out.items()}


def ex_dates() -> dict:
    """(نماد، تاریخ مجمع) ← روز تعدیل TSETMC که U − A ≈ DPS (استحقاق)."""
    pa = pd.read_csv(OUT / "price_adjust.csv", dtype={"dEven": str})
    pa["diff"] = pa.pClosingNotAdjusted - pa.pClosing
    pa["d"] = pd.to_datetime(pa.dEven, format="%Y%m%d", errors="coerce")
    return {s: x[["d", "diff"]].dropna().values.tolist() for s, x in pa.groupby("symbol")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ocr", action="store_true", help="OCR تازهٔ PDF/تصویرهای اسکن‌شده (پیش‌فرض خاموش؛ تصمیم مالک پروژه)")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    files = [p for p in sorted((RAW / "collect").glob("*/30_*_att*")) if p.is_file()]
    print(f"{len(files)} پیوست")
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(_job, [(p, a.ocr) for p in files]))
    # فراداده نامه‌ها از list_30.json
    meta = {}
    for lf in (RAW / "collect").glob("*/list_30.json"):
        for x in json.loads(lf.read_text(encoding="utf-8")):
            t = norm(x.get("Title") or "")
            pm = re.search(r"(\d+)\s*ماهه منتهی به\s*(1[34]\d{2}/\d{1,2}/\d{1,2})", t)
            meta[(lf.parent.name, str(x["TracingNo"]))] = {
                "months": int(pm.group(1)) if pm else None, "period_end_j": jdate(DATE.search(pm.group(2)).groups()) if pm else None,
                "pub_j": jdate(DATE.search(norm(x.get("PublishDateTime") or "")).groups()) if DATE.search(norm(x.get("PublishDateTime") or "")) else None,
                "revised": "اصلاحیه" in t, "title": t}
    agm = pd.read_csv(OUT / "codal_agm.csv", dtype=str).dropna(subset=["session_date_j"])
    agm = agm.sort_values("tracing").drop_duplicates(["symbol", "period_end_j"], keep="last").set_index(["symbol", "period_end_j"])
    exd = ex_dates()
    rows = []
    for path, text, how in res:
        p = Path(path)
        sym, tn = p.parent.name, re.search(r"30_(\d+)_", p.name).group(1)
        mt = meta.get((sym, tn), {})
        period = mt.get("period_end_j")
        hit = agm.loc[(sym, period)] if (sym, period) in agm.index else None
        sess = g(hit.session_date_j) if hit is not None else None
        c = classify(text, sess, mt.get("pub_j"))
        rows.append({"symbol": sym, "tracing": tn, "file": p.name, "method": how.split("(")[0], "chars": len(norm(text)), "months": mt.get("months") or "",
                     "period_end_j": period or "", "pub_j": mt.get("pub_j") or "", "revised": int(bool(mt.get("revised"))),
                     "session_date_j": hit.session_date_j if hit is not None else "", "dps_rial": hit.dps_rial if hit is not None else "",
                     **{f"{k}_dates": ";".join(v) for k, v in c.items()}})
    P = pd.DataFrame(rows)
    P.to_csv(OUT / "codal_payment_dates.csv", index=False)
    print("روش استخراج:", P.method.value_counts().to_dict(), "| متن‌دار:", int((P.chars > 200).sum()), "| دارای هر تاریخ معتبر:", int((P.any_dates != "").sum()))

    # یک ردیف برای هر رویداد (نماد × سال مالی ۱۲ماهه): برای هر گروه تاریخ آخرین نامه‌ای که آن گروه را دارد
    def last_first(df, col):
        for _, r in df.sort_values(["pub_j", "tracing"], ascending=False).iterrows():
            ds = sorted(d for d in str(r[col]).split(";") if d)
            if ds:
                return ds[0]
        return ""
    ev = []
    P12 = P[(P.session_date_j != "") & (P.months.astype(str).isin(["12", "12.0"]))]
    for (sym, per), df in P12.groupby(["symbol", "period_end_j"]):
        r = {"symbol": sym, "period_end_j": per, "session_date_j": df.session_date_j.iloc[0], "dps_rial": df.dps_rial.iloc[0], "n_letters": len(df)}
        for k in ("fund", "sejam", "legal", "nonsejam", "major", "any"):
            r[k] = last_first(df, f"{k}_dates")
        ev.append(r)
    E = pd.DataFrame(ev)
    if E.empty:
        print("هیچ رویداد ۱۲ماهه با تاریخ مجمع پیدا نشد؛ dividend_payment_lags.csv ساخته نشد (ابتدا --parse و codal_agm.csv).")
        return
    E["eff"] = [s or f or n for f, s, n in zip(E.fund, E.sejam, E["any"])]
    E["basis"] = ["sejam" if s else "fund" if f else "first" if n else "" for f, s, n in zip(E.fund, E.sejam, E["any"])]
    # روز استحقاق از تعدیل TSETMC
    exs = []
    for _, r in E.iterrows():
        a0 = g(r.session_date_j)
        dps = pd.to_numeric(r.dps_rial, errors="coerce")
        cand = [d for d, df_ in exd.get(r.symbol, []) if a0 - pd.Timedelta(days=1) <= pd.Timestamp(d) <= a0 + pd.Timedelta(days=12) and pd.notna(dps) and abs(df_ - dps) <= max(1.5, 0.002 * dps)]
        exs.append(str(pd.Timestamp(min(cand)).date()) if cand else "")
    E["ex_date"] = exs
    for col in ("fund", "sejam", "legal", "nonsejam", "any", "eff"):
        E[f"lag_{col}"] = [(g(x) - g(s)).days if x else None for x, s in zip(E[col], E.session_date_j)]
    E["lag_eff_ex"] = [(g(x) - pd.Timestamp(e)).days if x and e else None for x, e in zip(E.eff, E.ex_date)]
    E["agm_year"] = E.session_date_j.str[:4]
    E.to_csv(OUT / "dividend_payment_lags.csv", index=False)
    d = pd.to_numeric(E.dps_rial, errors="coerce")
    E2 = E[d > 0]
    print(f"\nرویداد سود ۱۲ماهه: {len(E)} (DPS>0: {len(E2)})؛ با تاریخ مؤثر: {E2.lag_eff.notna().sum()}؛ با روز استحقاق: {E2.lag_eff_ex.notna().sum()}")
    for c in ("lag_eff", "lag_eff_ex", "lag_fund", "lag_sejam", "lag_legal", "lag_nonsejam"):
        s = pd.to_numeric(E2[c], errors="coerce").dropna()
        if len(s):
            print(f"  {c:12s} n={len(s):3d}  میانه={s.median():5.0f}  چارک‌ها={s.quantile(.25):.0f}–{s.quantile(.75):.0f}  کمینه/بیشینه={s.min():.0f}/{s.max():.0f}")
    print("\nبر پایهٔ سال مجمع (تاریخ مؤثر، روز پس از مجمع):")
    for y, x in E2.groupby("agm_year"):
        s = pd.to_numeric(x.lag_eff, errors="coerce").dropna()
        if len(s):
            print(f"  {y}: n={len(s):2d} میانه={s.median():4.0f} چارک‌ها={s.quantile(.25):.0f}–{s.quantile(.75):.0f}")


if __name__ == "__main__":
    main()
