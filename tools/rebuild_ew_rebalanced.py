#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی «شاخص كل (هم وزن)» با ریبالانس دوره‌ای (نه روزانه) و مقایسه با سری رسمی.

    python tools/rebuild_ew_rebalanced.py            # جدول مقایسهٔ سیاست‌های ریبالانس
    python tools/rebuild_ew_rebalanced.py --save     # ذخیرهٔ بهترین سیاست (فصل شمسی)

یافتهٔ کلیدی (فصل ۰۳ §۳.۴): شاخص هم‌وزن رسمی «روزانه ریبالانس» نیست. بازده هم‌وزن روزانه‌ریبالانس
~۳۰٪ کمتر از سری رسمی است؛ با ریبالانس فصلی (آغاز فصل شمسی) سطح تجمعی ≈ ۱٫۰۲ و خطای ردیابی ۱٫۲٪.
سیاست: وزن‌ها بین ریبالانس‌ها با بازده رانش می‌کنند؛ نمادهای جدید تا ریبالانس بعدی وارد نمی‌شوند.
"""
import argparse

import numpy as np
import pandas as pd

import rebuild_cw_index as cw
import rebuild_ew_index as ew

ROOT = ew.ROOT


def g2j(gy: int, gm: int, gd: int):
    """میلادی → شمسی (الگوریتم استاندارد)."""
    g_dm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_dm[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def rebalance_flags(dates: pd.DatetimeIndex, policy: str) -> np.ndarray:
    n = len(dates)
    f = np.zeros(n, bool)
    f[0] = True
    if policy == "daily":
        f[:] = True
    elif policy.startswith("every"):
        f[:: int(policy[5:])] = True
    elif policy.startswith("cal-"):
        key = dates.to_period({"cal-month": "M", "cal-quarter": "Q", "cal-year": "Y"}[policy])
        f[1:] = key[1:] != key[:-1]
    elif policy.startswith("jalali-"):
        J = np.array([g2j(d.year, d.month, d.day) for d in dates])
        jy, jm = J[:, 0], J[:, 1]
        key = {"jalali-month": jy * 100 + jm, "jalali-quarter": jy * 10 + (jm - 1) // 3,
               "jalali-halfyear": jy * 10 + (jm - 1) // 6, "jalali-year": jy}[policy]
        f[1:] = key[1:] != key[:-1]
    else:
        raise ValueError(policy)
    return f


def portfolio_returns(M: pd.DataFrame, flags: np.ndarray) -> pd.Series:
    X = M.values
    n, k = X.shape
    w = np.zeros(k)
    out = np.zeros(n)
    for t in range(n):
        avail = ~np.isnan(X[t])
        if flags[t] or w.sum() == 0:
            w = np.where(avail, 1.0, 0.0)
        else:
            w = np.where(avail, w, 0.0)
            if w.sum() == 0:
                w = np.where(avail, 1.0, 0.0)
        w = w / w.sum()
        r = np.where(avail, X[t], 0.0)
        rp = (w * r).sum()
        out[t] = rp
        w = w * (1 + r) / (1 + rp)
    return pd.Series(out, index=M.index)


def evaluate(x: pd.Series, off: pd.Series) -> str:
    j = pd.concat([x, off], axis=1, join="inner").dropna()
    j.columns = ["m", "o"]
    j = j[j.index >= "2014-03-20"]
    d = j.m - j.o
    return (f"corr={j.m.corr(j.o):.4f} TE={d.std()*np.sqrt(252)*100:5.2f}% "
            f"cum_ratio={(1+j.m).prod()/(1+j.o).prod():.3f} mean={d.mean()*1e4:5.2f}bp")


POLICIES = ["daily", "every5", "every21", "every63", "every126", "cal-month", "cal-quarter",
            "jalali-month", "jalali-quarter", "jalali-halfyear", "jalali-year"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    R = cw.classify_events(ew.daily_returns(ew.load_panel()), sc)
    M_tr = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M_pr = R.pivot_table(index="date", columns="ins_code", values="r_pr", aggfunc="last")
    M_tr, M_pr = M_tr[M_tr.index >= "2014-03-19"], M_pr[M_pr.index >= "2014-03-19"]
    off_tr, off_pr = ew.official(ew.OFFICIAL["TR"]), ew.official(ew.OFFICIAL["PR"])
    print(f"\n{'سیاست ریبالانس':18s} | در برابر «كل (هم وزن)» [TR] | در برابر «قيمت (هم وزن)» [PR]")
    best = None
    for p in POLICIES:
        f = rebalance_flags(M_tr.index, p)
        s_tr, s_pr = portfolio_returns(M_tr, f), portfolio_returns(M_pr, f)
        print(f"{p:18s} | {evaluate(s_tr, off_tr)} | {evaluate(s_pr, off_pr)}")
        if p == "jalali-quarter":
            best = (s_tr, s_pr)
    if a.save and best is not None:
        out = ROOT / "data/derived"
        out.mkdir(parents=True, exist_ok=True)
        res = pd.DataFrame({"ret_tr": best[0], "ret_pr": best[1]})
        res["index_tr"] = 10000 * (1 + res.ret_tr).cumprod()
        res["index_pr"] = 10000 * (1 + res.ret_pr).cumprod()
        res.to_csv(out / "ew_rebuilt_jalali_quarter.csv", index_label="date")
        print("ذخیره شد:", out / "ew_rebuilt_jalali_quarter.csv")


if __name__ == "__main__":
    main()
