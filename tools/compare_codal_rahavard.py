#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مقایسهٔ ROE و بدهی کدال (سود خالص ÷ حقوق مالکانه) با نسبت‌های رهاورد برای نمادهایی که هر دو را دارند.

هدف: برداشتن [تأیید لازم] از تعریف ROE کدال (فصل ۴ §۴٫۳، فصل ۱۰ 7k) و تصمیم اینکه پایان‌دوره‌ای یا میانگین حقوق مالکانه به رهاورد نزدیک‌تر است.

    python tools/fetch_codal_fundamentals.py --symbols-file data/research/codal_calibration_symbols.csv --log cal.txt   # روی سیستم کاربر
    python tools/compare_codal_rahavard.py

خروجی: data/research/codal_vs_rahavard.csv (جفت سال‌مالی × نماد) و خلاصه روی صفحه.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
FUND = ROOT / "data" / "fundamentals"


def norm(s):
    return s.str.replace(r"[‌\s]+", "", regex=True)


def main():
    C = pd.read_csv(FUND / "codal_long.csv", dtype={"ins_code": str})
    R = pd.read_csv(FUND / "rahavard_long.csv", dtype={"ins_code": str})
    R = R[R.stmt == "ratio"].copy()
    R["rn"] = norm(R.row)
    R["fy_year"] = R.fy.str[:4].astype(int)
    R = R.sort_values(["audited", "represented"])
    def rah(pred, name):
        x = R[pred(R.rn)].groupby(["ins_code", "fy_year"]).value.last().rename(name)
        return x
    RR = pd.concat([rah(lambda s: s.str.contains("ROE"), "roe_r"), rah(lambda s: s == "نسبتبدهیبهارزشویژه", "de_r"), rah(lambda s: s == "نسبتبدهی", "da_r")], axis=1)
    C["pref"] = (C.col == "cur").astype(int)
    V = C.sort_values("pref").groupby(["ins_code", "fy_year", "key"]).value.last().unstack("key")
    for k in ("equity", "net_income", "liabilities", "assets", "liab_cur", "liab_noncur"):
        if k not in V:
            V[k] = np.nan
    V["liabilities"] = V.liabilities.fillna(V.liab_cur + V.liab_noncur).fillna(V.assets - V.equity)
    V = V.reset_index().sort_values(["ins_code", "fy_year"])
    V["equity_prev"] = V.groupby("ins_code").equity.shift(1)
    V.loc[V.groupby("ins_code").fy_year.diff() != 1, "equity_prev"] = np.nan          # فقط سال‌های متوالی
    V["roe_end"] = 100 * V.net_income / V.equity
    V["roe_avg"] = 100 * V.net_income / ((V.equity + V.equity_prev) / 2)
    V["roe_beg"] = 100 * V.net_income / V.equity_prev
    V["de_c"] = V.liabilities / V.equity
    V["da_c"] = V.liabilities / V.assets
    M = V.merge(RR.reset_index(), on=["ins_code", "fy_year"], how="inner")
    M = M.replace([np.inf, -np.inf], np.nan)
    if M.empty:
        sys.exit("نمادی با هر دو منبع نیست؛ ابتدا دریافت نمادهای واسنجی را اجرا کنید.")
    sym = C.drop_duplicates("ins_code").set_index("ins_code").symbol
    M.insert(1, "symbol", M.ins_code.map(sym))
    M.to_csv(ROOT / "data" / "research" / "codal_vs_rahavard.csv", index=False, encoding="utf-8-sig")
    print(f"{M.ins_code.nunique()} نماد، {len(M)} جفت سال‌مالی\n")
    def rep(a, b, label):
        m = M[[a, b]].dropna()
        m = m[(m[b].abs() < 1e3) & (m[a].abs() < 1e3)]
        if len(m) < 5:
            print(f"{label}: داده کافی نیست"); return None
        rel = (m[a] - m[b]).abs() / np.maximum(m[b].abs(), 1e-9)
        sp = m[a].rank().corr(m[b].rank())
        print(f"{label:<28} n={len(m):4d}  اسپیرمن={sp:5.3f}  میانهٔ |اختلاف|={float((m[a] - m[b]).abs().median()):8.2f}  میانهٔ تفاوت نسبی={float(rel.median()):6.3f}  در ±۱۰٪: {float((rel < 0.1).mean()):5.2f}  سوگیری میانه (کدال − رهاورد)={float((m[a] - m[b]).median()):7.2f}")
        return sp
    print("ROE (درصد)")
    s = {k: rep(k, "roe_r", f"  {k}") for k in ("roe_end", "roe_avg", "roe_beg")}
    print("\nبدهی")
    rep("de_c", "de_r", "  بدهی÷حقوق")
    rep("da_c", "da_r", "  بدهی÷دارایی")
    best = max((k for k in s if s[k] is not None), key=lambda k: s[k], default=None)
    print(f"\nنزدیک‌ترین تعریف ROE به رهاورد (اسپیرمن): {best}")
    print("تفاوت‌های بزرگ (|ROE کدال پایان‌دوره − رهاورد| > ۲۰ واحد):")
    big = M[(M.roe_end - M.roe_r).abs() > 20][["symbol", "fy_year", "roe_end", "roe_avg", "roe_r", "de_c", "de_r"]].head(15)
    print(big.round(1).to_string(index=False) if len(big) else "  ندارد")


if __name__ == "__main__":
    main()
