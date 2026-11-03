#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نرخ بدون ریسک از اسناد خزانهٔ اسلامی (اخزا) → data/derived/rf_daily.csv و ui/data/rates.js (window.SIM_RATES) — فصل ۷ §۷٫۱۰

    python tools/build_rf.py            # پس از tools/fetch_treasury_bills.py

اخزا اوراق بی‌کوپن دولت با ارزش اسمی ۱٬۰۰۰٬۰۰۰ ریال است؛ بازده تا سررسید هر ورقه در هر روز معامله:
    YTM = (1,000,000 / P)^(365 / d) − 1     P = قیمت پایانی TSETMC، d = روز تقویمی تا سررسید
(همان فرمول فرابورس؛ با YTM جاری جدول فرابورس مقایسه می‌شود). در هر روز فقط اوراقی وارد می‌شوند که:
  سررسیدشان نگذشته (d ≥ MIN_DAYS)، آن روز معامله داشته‌اند (حجم و دفعات > ۰) و قیمتشان زیر اسمی است.
نرخ روز:
  vw   میانگین YTM وزن‌گرفته با ارزش معاملهٔ همان روز (سرخط؛ مبنای rf تفکیک فاکتوری)
  med  میانه
  y1   نرخ یک‌ساله: درون‌یابی خطی YTM روی d در ۳۶۵ روز (فقط اگر ورقه‌ای هم کوتاه‌تر و هم بلندتر از یک سال معامله شده باشد)
روز بدون معاملهٔ اخزا نرخ ندارد؛ در سری روزانهٔ rf_ann (ستون rf) آخرین نرخ معلوم تا ۲۰ روز تقویمی ادامه می‌یابد.
همهٔ اوراق، سررسیدشده هم، در جدول «همهٔ اخزاها» با تاریخچه‌شان می‌آیند.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from jalali import j2g  # noqa: E402
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RATES = ROOT / "data" / "rates"
OUT_CSV = ROOT / "data" / "derived" / "rf_daily.csv"
OUT_JS = ROOT / "ui" / "data" / "rates.js"
FACE = 1_000_000.0
MIN_DAYS = 15                 # ورقهٔ نزدیک سررسید: چند روز اختلاف قیمت YTM را بی‌معنا بزرگ می‌کند
FFILL_DAYS = 20


def ytm(price, days):
    with np.errstate(all="ignore"):
        return np.power(FACE / np.asarray(price, float), 365.0 / np.asarray(days, float)) - 1


def load():
    B = pd.read_csv(RATES / "bills.csv", dtype={"ins_code": str})
    B["maturity"] = pd.to_datetime(B.maturity)
    D = pd.read_csv(RATES / "bills_daily.csv.gz", parse_dates=["date"])
    D = D.merge(B[["symbol", "maturity"]], on="symbol", how="left")
    D["days"] = (D.maturity - D.date).dt.days
    D["traded"] = (D.volume > 0) & (D["count"] > 0) & (D.close > 0)
    D["ytm"] = np.where(D.traded & (D.days > 0), ytm(D.close, D.days.clip(lower=1)), np.nan)
    return B, D


def interp_1y(g: pd.DataFrame):
    g = g.sort_values("days")
    lo, hi = g[g.days <= 365], g[g.days > 365]
    if lo.empty or hi.empty:
        return np.nan
    a, b = lo.iloc[-1], hi.iloc[0]
    return float(a.ytm + (b.ytm - a.ytm) * (365 - a.days) / (b.days - a.days))


def daily(D: pd.DataFrame) -> pd.DataFrame:
    U = D[D.traded & (D.days >= MIN_DAYS) & (D.close < FACE) & np.isfinite(D.ytm)]
    rows = []
    for d, g in U.groupby("date"):
        w = g.value.clip(lower=0)
        rows.append({"date": d, "vw": float(np.average(g.ytm, weights=w)) if w.sum() > 0 else float(g.ytm.mean()),
                     "med": float(g.ytm.median()), "y1": interp_1y(g), "n": int(len(g)), "value": float(g.value.sum())})
    S = pd.DataFrame(rows).set_index("date")
    cal = pd.date_range(S.index.min(), S.index.max(), freq="D")
    S = S.reindex(cal)
    S["rf"] = S.vw.ffill(limit=FFILL_DAYS)
    return S


def main():
    B, D = load()
    S = daily(D)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    S.dropna(subset=["rf"]).round(6).to_csv(OUT_CSV, index_label="date")
    T = S.dropna(subset=["vw"])
    print(f"نرخ روزانه: {T.index.min().date()} تا {T.index.max().date()}، {len(T)} روز معامله؛ "
          f"آخرین vw {100 * T.vw.iloc[-1]:.2f}٪، میانه {100 * T.med.iloc[-1]:.2f}٪، یک‌ساله {100 * T.y1.iloc[-1]:.2f}٪ ({int(T.n.iloc[-1])} ورقه)")
    for y in sorted(set(T.index.year)):
        x = T[T.index.year == y]
        print(f"  {y}: میانگین vw {100 * x.vw.mean():.1f}٪  (کمینه {100 * x.vw.min():.1f}، بیشینه {100 * x.vw.max():.1f})، میانگین شمار ورقه {x.n.mean():.1f}")
    last = D.date.max()
    # جدول همهٔ اوراق
    allb = []
    for r in B.itertuples():
        x = D[(D.symbol == r.symbol) & D.traded]
        live = pd.notna(r.maturity) and r.maturity > last
        lt = x.iloc[-1] if len(x) else None
        allb.append({"s": r.symbol, "mat": None if pd.isna(r.maturity) else str(r.maturity.date()), "mat_j": r.maturity_j if isinstance(r.maturity_j, str) else "",
                     "live": bool(live), "first": None if lt is None else str(x.date.min().date()), "last": None if lt is None else str(lt.date.date()),
                     "ndays": int(len(x)), "value_bn": round(float(x.value.sum()) / 1e9, 1),
                     "last_price": None if lt is None else float(lt.close), "last_ytm": None if lt is None or not np.isfinite(lt.ytm) else round(float(lt.ytm), 5),
                     "last_days": None if lt is None else int(lt.days),
                     "ifb_ytm": None if pd.isna(r.ifb_ytm) else float(r.ifb_ytm), "ifb_price": None if pd.isna(r.ifb_price) else float(r.ifb_price),
                     "ifb_last_j": r.ifb_last_trade_j if isinstance(r.ifb_last_trade_j, str) else ""})
    # مقایسه با فرابورس: فرمول و تاریخ سررسید ما روی قیمت و روز آخرین معاملهٔ جدول فرابورس (روز دریافت ممکن است هنوز در قیمت‌های پایانی نباشد)
    for a, r in zip(allb, B.itertuples()):
        a["ifb_check"] = None
        if a["ifb_ytm"] is not None and a["ifb_price"] and a["ifb_last_j"] and pd.notna(r.maturity):
            t = pd.Timestamp(j2g(*map(int, a["ifb_last_j"].split("/")), strict=False))
            a["ifb_check"] = round(float(ytm(a["ifb_price"], (r.maturity - t).days)), 5)
    cmp = [abs(a["ifb_check"] - a["ifb_ytm"]) for a in allb if a["ifb_check"] is not None]
    print(f"مقایسه با YTM فرابورس ({len(cmp)} ورقه، روی قیمت و روز فرابورس): بیشینهٔ اختلاف {100 * max(cmp) if cmp else float('nan'):.3f} واحد درصد")
    # منحنی هر روز معامله (برای انتخاب تاریخ در صفحه): فقط ۲۶۰ روز آخر
    U = D[D.traded & (D.days >= MIN_DAYS) & (D.close < FACE) & np.isfinite(D.ytm)]
    recent = sorted(U.date.unique())[-260:]
    curves = {str(pd.Timestamp(d).date()): [[g.symbol, int(g.days), round(float(g.ytm), 5), round(float(g.value) / 1e9, 2)] for g in U[U.date == d].itertuples()] for d in recent}
    W = S.dropna(subset=["rf"])
    out = {"asof": str(last.date()), "ifb_asof": str(B.ifb_asof.iloc[0]), "min_days": MIN_DAYS, "ffill_days": FFILL_DAYS,
           "series": {"date": [str(d.date()) for d in W.index], **{c: [None if v != v else round(float(v), 5) for v in W[c].values] for c in ["vw", "med", "y1", "rf"]},
                      "n": [0 if v != v else int(v) for v in W.n.values], "value_bn": [0 if v != v else round(float(v) / 1e9, 1) for v in W.value.values]},
           "bills": allb, "curves": curves}
    OUT_JS.write_text("window.SIM_RATES = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"→ {OUT_CSV.relative_to(ROOT)}، {OUT_JS.relative_to(ROOT)} ({OUT_JS.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
