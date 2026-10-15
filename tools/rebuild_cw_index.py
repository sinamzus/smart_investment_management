#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی شاخص ارزش‌وزن بورس («شاخص كل» و «قيمت وزني-ارزشي») و مقایسه با سری‌های رسمی.

    python tools/rebuild_cw_index.py            # گزارش
    python tools/rebuild_cw_index.py --save     # ذخیره در data/derived/cw_rebuilt_bourse.csv

روش (فصل ۰۳ §۳.۴):
  • وزن هر نماد = قیمت مبنای روز × تعداد سهام همان روز (تاریخچه از GetInstrumentShareChange).
    نمادهای بدون رویداد تغییر سرمایه: تعداد سهام ثابت = zTitad از instrument_info.csv (اگر موجود).
  • دو نوع بازده نماد:
      TR-type: C / B − 1 (قیمت مبنا؛ سود نقدی روز استحقاق جبران می‌شود) ← «شاخص كل»
      PR-type: برای ردیف‌هایی که تعدیل مبنا «سود نقدی» است (نه تغییر سرمایه)، C / C_prev − 1
               یعنی افت قیمت ناشی از سود جبران نمی‌شود ← «شاخص قيمت (وزني-ارزشي)»
  • رویداد تعدیل = ردیفی که B ≠ C_prev؛ «تغییر سرمایه» اگر در ±۷ روز آن تغییر تعداد سهام ثبت شده باشد،
    وگرنه «سود نقدی». (طبقه‌بندی تقریبی؛ رویداد ترکیبی سود+سرمایه به‌عنوان سرمایه می‌ماند.)
  • قواعد پاک‌سازی ردیف مانند rebuild_ew_index.py.
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import rebuild_ew_index as ew

ROOT = ew.ROOT
CODES = {"K": "32097828799138957", "P": "5798407779416661"}   # شاخص كل / قيمت(وزني-ارزشي)


def shares_timeline(df: pd.DataFrame, sc: pd.DataFrame, info: pd.DataFrame | None) -> pd.Series:
    """تعداد سهام در هر ردیف: بعد از رویداد = shares_new؛ قبل از اولین رویداد = shares_old اولی."""
    cur = {}
    if info is not None:
        cur = dict(zip(info.ins_code.astype(str), pd.to_numeric(info.zTitad, errors="coerce")))
    ev = {c: g.sort_values("date") for c, g in sc.groupby("ins_code")}
    out = pd.Series(np.nan, index=df.index)
    for code, g in df.groupby("ins_code"):
        e = ev.get(code)
        if e is None or e.empty:
            if code in cur and cur[code] > 0:
                out.loc[g.index] = cur[code]
            continue
        idx = np.searchsorted(e.date.values, g.date.values, side="right") - 1
        out.loc[g.index] = np.where(idx >= 0, e.shares_new.values[np.clip(idx, 0, None)], e.shares_old.values[0])
    return out


def classify_events(R: pd.DataFrame, sc: pd.DataFrame) -> pd.DataFrame:
    P = ew.load_panel()[["ins_code", "date", "pClosing"]].sort_values(["ins_code", "date"])
    P["prevC"] = P.groupby("ins_code").pClosing.shift(1)
    R = R.merge(P[["ins_code", "date", "prevC"]], on=["ins_code", "date"], how="left")
    R["f"] = R.priceYesterday / R.prevC
    ev_dates = {c: g.date.values for c, g in sc.groupby("ins_code")}

    def near(c, d):
        a = ev_dates.get(c)
        return a is not None and (np.abs((a - np.datetime64(d)).astype("timedelta64[D]").astype(int)) <= 7).any()

    adj = R[(R.f - 1).abs() > 1e-3]
    cap = pd.Series([near(c, d) for c, d in zip(adj.ins_code, adj.date)], index=adj.index)
    R["is_dividend"] = False
    R.loc[cap[~cap].index, "is_dividend"] = True
    R["r_tr"] = R.r
    R["r_pr"] = np.where(R.is_dividend, R.pClosing / R.prevC - 1, R.r)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    info_p = ROOT / "data/corporate_actions/instrument_info.csv"
    info = pd.read_csv(info_p, dtype={"ins_code": str}) if info_p.exists() else None
    print("instrument_info.csv:", "موجود" if info is not None else "نیست (نمادهای بدون رویداد سرمایه کنار می‌روند)")

    R = classify_events(ew.daily_returns(ew.load_panel()), sc)
    R["shares"] = shares_timeline(R, sc, info)
    miss = R[R.shares.isna()]
    print(f"ردیف بدون تعداد سهام: {len(miss)} از {len(R)}؛ نماد: {miss.ins_code.nunique()}")
    R = R.dropna(subset=["shares"]).copy()
    R["w"] = R.priceYesterday * R.shares
    den = R.groupby("date").w.sum()
    res = pd.DataFrame({
        "ret_tr": (R.r_tr * R.w).groupby(R.date).sum() / den,
        "ret_pr": (R.r_pr * R.w).groupby(R.date).sum() / den,
        "n_symbols": R.groupby("date").ins_code.nunique(),
    })
    print()
    for lab, col, off in [("TR-type در برابر «شاخص كل»        ", "ret_tr", "K"), ("PR-type در برابر «قيمت وزني-ارزشي»", "ret_pr", "P")]:
        ew.compare(res[col], ew.official(CODES[off]), lab)
    print("\nضربدری (باید بدتر باشد، برای اطمینان):")
    ew.compare(res.ret_tr, ew.official(CODES["P"]), "TR-type در برابر قيمت وزني-ارزشي")
    ew.compare(res.ret_pr, ew.official(CODES["K"]), "PR-type در برابر شاخص كل")
    d = res.ret_tr - ew.official(CODES["K"]).reindex(res.index)
    d = d[d.index >= "2014-03-20"].dropna()
    print("\nMAD سالانهٔ TR-type در برابر كل (bp):", {y: round(v * 1e4, 1) for y, v in d.abs().groupby(d.index.year).mean().items()})
    if a.save:
        out = ROOT / "data/derived"
        out.mkdir(parents=True, exist_ok=True)
        res["index_tr"] = 1000 * (1 + res.ret_tr).cumprod()
        res["index_pr"] = 1000 * (1 + res.ret_pr).cumprod()
        res.to_csv(out / "cw_rebuilt_bourse.csv", index_label="date")
        print("ذخیره شد:", out / "cw_rebuilt_bourse.csv")


if __name__ == "__main__":
    main()
