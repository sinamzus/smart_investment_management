#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ادغام تاریخ‌های واقعی پرداخت سود (کدال ن-۱۳ + کارگزاری فارابی) در یک جدول رویداد، با روز استحقاق و وزن جریان سود در شاخص‌ها (فصل ۱۰ 7f).

ورودی:  data/corporate_actions/dividend_payment_lags.csv   (tools/parse_dividend_payments.py؛ تاریخ مؤثر = سجامی)
        data/corporate_actions/payment_dates_farabi.csv    (tools/parse_farabi_dividends.py؛ فقط ردیف‌های سجامی)
        پانل بازده نمادها (build_ui_extra.base_panel) برای روز استحقاق و وزن.
خروجی:  data/corporate_actions/dividend_payment_events.csv
    symbol, agm_j, dps_rial, pay_j, pay_kind, source (codal|farabi|both|conflict→farabi), ex_date, lag_agm, lag_ex,
    y (بازده سود روز استحقاق = r_TR − r_PR), wt (وزن ارزشی نماد در «شاخص كل» همان روز), wK = wt·y (سهم از جریان سود شاخص كل), wEW = y

قواعد:
  • فقط تاریخ پرداخت *سجامی* (صندوق‌ها و حقیقی‌های ثبت‌نام‌شده در سجام)؛ تأخیر مجمع تا پرداخت باید در [۰، ۳۰۰] روز باشد (سقف قانونی ۸ ماه ≈ ۲۴۰ روز [تأیید لازم]).
  • اگر کدال و فارابی هر دو بیایند: تا ۷ روز اختلاف ⇒ کدال (اصلی)؛ بیشتر ⇒ فارابی (اعتبارسنجی متقاطع نشان داد پارسر کدال گاهی نامهٔ مطالبات سنواتی را می‌خواند).
  • روز استحقاق: روز ۱ تا ۱۲ پس از مجمع که بازده سود y در پانل مثبت و y·قیمت دیروز نزدیک‌ترین به DPS است (حداکثر ۳۰٪ خطا؛ y·قیمت دیروز به‌طور ساختاری تا ~۲۵٪ با DPS اعلامی فرق دارد)؛ اگر DPS نبود، روز با بیشترین y.
  • وزن‌ها فقط برای نمادهای پانل (۴۲۹ نماد) محاسبه می‌شود؛ بقیه رویدادها در آمار «جهان» می‌آیند ولی وزن شاخص ندارند.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from fetch_corporate_actions import j2g  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CA = ROOT / "data" / "corporate_actions"
OUT = CA / "dividend_payment_events.csv"


def g(jd: str) -> pd.Timestamp:
    return pd.Timestamp(j2g(*map(int, jd.split("/"))))


def norm(t) -> str:
    return str(t or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").strip().replace("  ", " ")


def load_events() -> pd.DataFrame:
    rows = []
    cf = CA / "dividend_payment_lags.csv"
    if cf.exists():
        C = pd.read_csv(cf, dtype=str).fillna("")
        C = C[(C.eff != "") & (C.session_date_j != "") & (pd.to_numeric(C.dps_rial, errors="coerce") > 0)]
        for _, r in C.iterrows():
            rows.append({"symbol": norm(r.symbol), "agm_j": r.session_date_j, "dps_rial": float(r.dps_rial), "pay_j": r.eff, "pay_kind": "day", "source": "codal"})
    ff = CA / "payment_dates_farabi.csv"
    if ff.exists():
        F = pd.read_csv(ff, dtype=str).fillna("")
        F = F[(F.holder == "sejam") & (F.pay_j != "") & (F.agm_j != "") & ~F.symbol.isin(["نماد", "نام نماد"])]
        for _, r in F.iterrows():
            rows.append({"symbol": norm(r.symbol), "agm_j": r.agm_j, "dps_rial": pd.to_numeric(r.dps_rial, errors="coerce"), "pay_j": r.pay_j, "pay_kind": r.pay_kind, "source": "farabi"})
    A = pd.DataFrame(rows)
    A["lag_agm"] = [(g(p) - g(a)).days for p, a in zip(A.pay_j, A.agm_j)]
    A = A[(A.lag_agm >= 0) & (A.lag_agm <= 300)]
    out = []
    for (s, a), x in A.groupby(["symbol", "agm_j"]):
        c, f = x[x.source == "codal"], x[x.source == "farabi"]
        if len(c) and len(f):
            d = abs((g(c.pay_j.iloc[0]) - g(f.pay_j.iloc[0])).days)
            r = (c if d <= 7 else f).iloc[0].copy()
            r["source"] = "both" if d <= 7 else "conflict→farabi"
        else:
            r = x.iloc[0].copy()
        if pd.isna(r.dps_rial) and len(x.dps_rial.dropna()):
            r["dps_rial"] = x.dps_rial.dropna().iloc[0]
        out.append(r)
    return pd.DataFrame(out).reset_index(drop=True)


def attach_ex_and_weights(E: pd.DataFrame, R: pd.DataFrame) -> pd.DataFrame:
    R = R.copy()
    R["sym"] = R.symbol.map(norm)
    R["y"] = R.r_tr - R.r_pr
    R = R[R.y > 1e-6]
    by = {s: x.sort_values("date") for s, x in R.groupby("sym")}
    ex, y, wt = [], [], []
    for _, r in E.iterrows():
        x = by.get(r.symbol)
        best = None
        if x is not None:
            a0 = g(r.agm_j)
            w = x[(x.date > a0) & (x.date <= a0 + pd.Timedelta(days=12))]
            if len(w):
                impl = w.y * w.priceYesterday
                if pd.notna(r.dps_rial) and r.dps_rial > 0:
                    err = (impl - r.dps_rial).abs() / r.dps_rial
                    ok = w[err <= 0.30]
                    best = ok.loc[err[ok.index].idxmin()] if len(ok) else None     # نزدیک‌ترین به DPS (y·قیمت دیروز ≈ DPS با خطای ساختاری تا ~۲۵٪)
                else:
                    best = w.loc[w.y.idxmax()]
        if best is None:
            ex.append(""); y.append(np.nan); wt.append(np.nan)
        else:
            ex.append(str(best.date.date())); y.append(float(best.y)); wt.append(float(best.wt))
    E = E.copy()
    E["ex_date"], E["y"], E["wt"] = ex, y, wt
    E["lag_ex"] = [(g(p) - pd.Timestamp(e)).days if e else np.nan for p, e in zip(E.pay_j, E.ex_date)]
    E["wK"] = E.wt * E.y
    E["wEW"] = E.y
    return E


def main():
    import build_ui_extra as bx
    E = load_events()
    print(f"رویداد ادغام‌شده: {len(E)} ({E.symbol.nunique()} نماد)؛ منبع: {E.source.value_counts().to_dict()}")
    _, _, R = bx.base_panel()
    E = attach_ex_and_weights(E, R)
    E.to_csv(OUT, index=False, encoding="utf-8")
    m = E[E.ex_date != ""]
    print(f"با روز استحقاق و وزن در پانل: {len(m)} ({m.symbol.nunique()} نماد)")
    L = pd.to_numeric(m.lag_ex, errors="coerce").clip(lower=0)
    print(f"تأخیر از استحقاق (بدون وزن): میانه={L.median():.0f} میانگین={L.mean():.0f} چارک‌ها={L.quantile(.25):.0f}–{L.quantile(.75):.0f}")
    for k, w in (("K", "wK"), ("EW", "wEW")):
        ww = m[w].fillna(0)
        mean = float((L * ww).sum() / ww.sum())
        order = np.argsort(L.values)
        cw = np.cumsum(ww.values[order]) / ww.sum()
        med = float(L.values[order][np.searchsorted(cw, 0.5)])
        print(f"  تأخیر وزنی با جریان سود {k}: میانگین={mean:.0f} میانه={med:.0f}")
    # پوشش: سهم جریان سود هر شاخص در هر سال میلادی که رویدادش تاریخ پرداخت دارد (برای گزارش در Dividend Lab)
    R2 = R.copy()
    R2["y"] = R2.r_tr - R2.r_pr
    R2 = R2[R2.y > 1e-6]
    cov = []
    for y in sorted(set(R2.date.dt.year)):
        x = R2[R2.date.dt.year == y]
        e = m[pd.to_datetime(m.ex_date).dt.year == y]
        if len(x) and (x.wt * x.y).sum() > 0:
            cov.append({"year": int(y), "events": int(len(e)), "cov_K": round(float(e.wK.sum() / (x.wt * x.y).sum()), 3), "cov_EW": round(float(e.wEW.sum() / x.y.sum()), 3)})
    pd.DataFrame(cov).to_csv(CA / "dividend_payment_coverage.csv", index=False)
    print(pd.DataFrame(cov).tail(6).to_string(index=False))
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
