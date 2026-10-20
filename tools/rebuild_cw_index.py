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
  • قاعدهٔ ۷ (fix_unadjusted_capital_events): افزایش سرمایه‌ای که مبنای روزانه آن تعدیل نشده با تعداد سهام اصلاح می‌شود.
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

    # سود نقدی = کاهش مبنا (f < ۱) بدون تغییر تعداد سهام در ±۷ روز، به شرط تأیید (ممیزی ۲۰۲۶-۱۰-۲۰؛ فصل ۰۲ §۲٫۴):
    #   (۱) TSETMC خودش در ±۱۰ روز رویداد تعدیل ثبت کرده باشد (price_adjust.csv)؛ تغییر مبنای بی‌رویداد (۴۶۹ ردیف، بیشتر بهار ۲۰۲۰ و ۲۰۲۳،
    #       میانهٔ ۰٫۸٪) بازنشانی قیمت مبنا است نه سود؛
    #   (۲) افزایش مبنا (f > ۱؛ ۲۳۷ ردیف) هرگز سود نیست؛
    #   (۳) «سود» بالای ۳۰٪ فقط با سود اعلام‌شده (فارابی، رهاورد، fundai) در ±۶۰ روز پذیرفته می‌شود؛ وگرنه احتمالاً افزایش سرمایهٔ ثبت‌نشده است.
    # ردیف ردشده بازدهٔ کل (r_tr) را عوض نمی‌کند (همان مبنای TSETMC، سازگار با شاخص رسمی)؛ فقط در بازده سود (div_yield) و شاخص قیمت نمی‌آید.
    pa = ROOT / "data/corporate_actions/price_adjust.csv"
    adj_dates = {}
    if pa.exists():
        A = pd.read_csv(pa, dtype={"ins_code": str})
        A["d"] = pd.to_datetime(A.dEven.astype(int).astype(str), format="%Y%m%d")
        adj_dates = {c: g.d.values for c, g in A.groupby("ins_code")}
    ann = {}
    dm = ROOT / "data/corporate_actions/dividend_events_merged.csv"
    if dm.exists():
        M = pd.read_csv(dm, dtype={"ins_code": str})
        M = M[M[["farabi_dps", "rv_dps", "fd_dps"]].max(axis=1) > 0]
        ann = {c: pd.to_datetime(g.ex_date).values for c, g in M.groupby("ins_code")}

    def within(tab, c, d, days):
        a = tab.get(c)
        return a is not None and (np.abs((a - np.datetime64(d)).astype("timedelta64[D]").astype(int)) <= days).any()

    adj = R[(R.f - 1).abs() > 1e-3]
    cap = pd.Series([near(c, d) for c, d in zip(adj.ins_code, adj.date)], index=adj.index)
    cand = adj[~cap & (adj.f < 1)]
    conf = pd.Series([within(adj_dates, c, d, 10) if adj_dates else True for c, d in zip(cand.ins_code, cand.date)], index=cand.index)
    big = (1 - cand.f) > 0.30
    big_ok = pd.Series([within(ann, c, d, 60) for c, d in zip(cand.ins_code, cand.date)], index=cand.index)
    keep = conf & (~big | big_ok)
    R["is_dividend"] = False
    R.loc[keep[keep].index, "is_dividend"] = True
    print(f"سود نقدی: {int(keep.sum())} ردیف؛ رد شد: افزایش مبنا {int((~cap & (adj.f > 1)).sum())}، بدون تعدیل TSETMC {int((~conf).sum())}، "
          f"بالای ۳۰٪ بدون سود اعلام‌شده {int((conf & big & ~big_ok).sum())}")
    R["r_tr"] = R.r
    R["r_pr"] = np.where(R.is_dividend, R.pClosing / R.prevC - 1, R.r)
    return fix_unadjusted_capital_events(R, sc)


def fix_unadjusted_capital_events(R: pd.DataFrame, sc: pd.DataFrame, max_abs: float = 0.25) -> pd.DataFrame:
    """قاعدهٔ ۷: در برخی ردیف‌های قدیمی (عمدتاً ۲۰۱۴) روز افزایش سرمایه مبنا (priceYesterday) تعدیل نشده
    (f = 1) و بازده خام −۳۰٪ تا −۶۰٪ می‌شود، در حالی که شاخص رسمی آن را تعدیل‌شده می‌بیند.
    اگر در همان روز افزایش تعداد سهام ثبت شده باشد، بازده با ضریب shares_old/shares_new بازمحاسبه می‌شود
    (فقط اگر بازده جدید در ±max_abs باشد)."""
    inc = sc[sc.shares_new > sc.shares_old][["ins_code", "date", "shares_old", "shares_new"]].drop_duplicates(["ins_code", "date"], keep="last")
    R = R.reset_index(drop=True)
    m = R.reset_index().merge(inc, on=["ins_code", "date"], how="left").set_index("index")
    cand = m.shares_old.notna() & ((m.f - 1).abs() < 1e-3)
    alt = m.pClosing / (m.prevC * m.shares_old / m.shares_new) - 1
    use = cand & (alt.abs() <= max_abs) & (alt.abs() < m.r.abs())
    R.loc[use[use].index, ["r_tr", "r_pr"]] = np.column_stack([alt[use], alt[use]])
    R["capital_fixed"] = use.reindex(R.index).fillna(False)
    print(f"قاعدهٔ ۷: {int(R.capital_fixed.sum())} ردیف افزایش سرمایهٔ تعدیل‌نشده در مبنا اصلاح شد")
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
