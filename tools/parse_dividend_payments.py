#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""استخراج تاریخ واقعی پرداخت سود از پیوست‌های «زمان‌بندی پرداخت سود» کدال (ن-۱۳) و محاسبهٔ تأخیر.

    python tools/parse_dividend_payments.py            # متن (pdftotext / OCR) ← جدول‌ها
    python tools/parse_dividend_payments.py --no-ocr   # فقط PDFهای متنی

ورودی:  data/raw/codal/collect/<نماد>/30_<TracingNo>_att*.{pdf,jpg,…}  (tools/fetch_dividend_payments.py --attachments)
        data/corporate_actions/codal_agm.csv  (تاریخ مجمع و سود هر سهم؛ --parse)
وابستگی: pdftotext و pdftoppm (poppler)، tesseract با زبان fas برای PDFهای اسکن‌شده (~۷۰٪ پیوست‌ها).
خروجی:
    data/raw/codal/text/<نماد>__<TracingNo>.txt            متن استخراج‌شده (کش؛ OCR دوباره لازم نیست)
    data/corporate_actions/codal_payment_dates.csv          هر پیوست: تاریخ‌های پرداخت به تفکیک گروه سهامدار
    data/corporate_actions/dividend_payment_lags.csv        هر رویداد سود: تاریخ مجمع، DPS، شروع پرداخت (صندوق/حقوقی، سجامی، اولین)، تأخیر به روز

روش (قاعده‌محور، فصل ۲ §۲٫۴ و فصل ۱۰ 7f): در متن هر تاریخ ۱۳xx/۱۴xx که بعد از تاریخ مجمع و حداکثر ۴۰۰ روز بعد از آن است «تاریخ پرداخت»
فرض می‌شود و با کلیدواژه‌های همان سطر/جمله به گروه نسبت داده می‌شود: صندوق (صندوق/سبد)، حقوقی، سجامی (حقیقیِ ثبت‌نام‌شده در سجام)،
غیرسجامی (ثبت‌نام ننموده/غیر سجامی/شعب بانک)، عمده. برای یک صندوق سرمایه‌گذاری مرتبط‌ترین تاریخ «صندوق»، سپس «حقوقی» است.
"""
import argparse
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
from fetch_corporate_actions import j2g  # noqa: E402

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


def jdate(m) -> str | None:
    y, mo, d = map(int, m)
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}/{mo:02d}/{d:02d}"


def g(jd: str) -> pd.Timestamp:
    return pd.Timestamp(j2g(*map(int, jd.split("/"))))


def classify(text: str, session: pd.Timestamp | None) -> dict:
    """تاریخ‌های پرداخت به تفکیک گروه. هر جمله/سطر جداگانه؛ کلیدواژه در همان جمله یا ۱۲۰ نویسهٔ قبل از تاریخ."""
    t = norm(text)
    out = {k: [] for k, _ in GROUPS} | {"any": []}
    for seg in re.split(r"[\n.؛;]", t):
        for m in DATE.finditer(seg):
            jd = jdate(m.groups())
            if not jd:
                continue
            try:
                gd = g(jd)
            except Exception:  # noqa: BLE001
                continue
            if session is not None and not (session < gd <= session + pd.Timedelta(days=400)):
                continue
            ctx = seg[max(0, m.start() - 160):m.start()] + " " + seg
            grp = next((k for k, kws in GROUPS if any(w in ctx for w in kws)), None)
            out["any"].append(jd)
            if grp:
                out[grp].append(jd)
    return {k: sorted(set(v)) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    files = [p for p in sorted((RAW / "collect").glob("*/30_*_att*")) if p.is_file()]
    print(f"{len(files)} پیوست")
    with ProcessPoolExecutor(a.workers) as ex:
        res = list(ex.map(_job, [(p, not a.no_ocr) for p in files]))
    agm = pd.read_csv(OUT / "codal_agm.csv", dtype=str).dropna(subset=["session_date_j"])
    agm = agm.sort_values("tracing").drop_duplicates(["symbol", "period_end_j"], keep="last")
    rows = []
    for path, text, how in res:
        p = Path(path)
        sym, tn = p.parent.name, re.search(r"30_(\d+)_", p.name).group(1)
        t = norm(text)
        pm = re.search(r"منتهی به\s*(?:\S+\s+){0,3}?(1[34]\d{2}/\d{1,2}/\d{1,2})", t)
        period = jdate(DATE.search(pm.group(1)).groups()) if pm else None
        if not period:   # «۲۹ اسفند ۱۴۰۰» و مشابه
            ym = re.search(r"منتهی به\s*(?:\d{1,2}\s+)?اسفند\s*(?:ماه\s*)?(1[34]\d{2})", t)
            period = f"{ym.group(1)}/12/29" if ym else None
        cand = agm[agm.symbol == sym]
        hit = cand[cand.period_end_j.str[:4] == period[:4]] if period else cand.iloc[0:0]
        sess = g(hit.session_date_j.iloc[0]) if len(hit) else None
        c = classify(text, sess)
        rows.append({"symbol": sym, "tracing": tn, "file": p.name, "method": how, "chars": len(t), "period_end_j": period or "",
                     "session_date_j": hit.session_date_j.iloc[0] if len(hit) else "", "dps_rial": hit.dps_rial.iloc[0] if len(hit) else "",
                     **{f"{k}_dates": ";".join(v) for k, v in c.items()}})
    P = pd.DataFrame(rows)
    P.to_csv(OUT / "codal_payment_dates.csv", index=False)
    print(P.method.str.split("(").str[0].value_counts().to_dict())

    # یک ردیف برای هر رویداد سود (نماد × سال مالی): اولین تاریخ هر گروه روی همهٔ نسخه‌ها/پیوست‌ها
    def first(s):
        ds = sorted({d for x in s.dropna() for d in str(x).split(";") if d})
        return ds[0] if ds else ""
    E = P[P.session_date_j != ""].groupby(["symbol", "period_end_j"]).agg(
        session_date_j=("session_date_j", "first"), dps_rial=("dps_rial", "first"),
        fund=("fund_dates", first), legal=("legal_dates", first), sejam=("sejam_dates", first),
        nonsejam=("nonsejam_dates", first), any=("any_dates", first), n_letters=("tracing", "nunique")).reset_index()
    for col in ("fund", "legal", "sejam", "nonsejam", "any"):
        E[f"lag_{col}"] = [(g(x) - g(s)).days if x else None for x, s in zip(E[col], E.session_date_j)]
    E["inst"] = [f or l or "" for f, l in zip(E.fund, E.legal)]
    E["lag_inst"] = [(g(x) - g(s)).days if x else None for x, s in zip(E.inst, E.session_date_j)]
    E.to_csv(OUT / "dividend_payment_lags.csv", index=False)
    d = pd.to_numeric(E.dps_rial, errors="coerce")
    E2 = E[d > 0]
    print(f"\nرویداد سود: {len(E)} (با DPS>0: {len(E2)})؛ با تاریخ صندوق/حقوقی: {E2.lag_inst.notna().sum()}؛ با هر تاریخ: {E2.lag_any.notna().sum()}")
    for c in ("lag_inst", "lag_fund", "lag_legal", "lag_sejam", "lag_any"):
        s = pd.to_numeric(E2[c], errors="coerce").dropna()
        if len(s):
            print(f"  {c:10s} n={len(s):3d}  میانه={s.median():5.0f}  چارک‌ها={s.quantile(.25):.0f}–{s.quantile(.75):.0f}  کمینه/بیشینه={s.min():.0f}/{s.max():.0f}")


if __name__ == "__main__":
    main()
