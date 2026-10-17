#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""امتیاز کیفیت (Quality) هر سهم در هر تاریخ، از صورت‌های مالی سالانهٔ رهاورد۳۶۵ (tools/fetch_rahavard_fundamentals.py).

روش (فصل ۴ §۴٫۳ و فصل ۱۱؛ سادهٔ شدهٔ MSCI Quality):
  سه مؤلفه از آخرین سال مالی «شناخته‌شده» تا تاریخ t:
    ۱) سودآوری = ROE (بازدهی سرمایه)                           — بیشتر بهتر
    ۲) اهرم    = بدهی به حقوق صاحبان سهام (D/E)                — کمتر بهتر
    ۳) ثبات سود = انحراف معیار ROE در حداکثر ۵ سال مالی اخیر   — کمتر بهتر (دست‌کم ۳ سال)
  هر مؤلفه: وینزورایز ۱٪–۹۹٪ سراسری ← Z درون صنعت (دست‌کم ۶ سهم در صنعت، وگرنه Z سراسری) ← برش ±۳ ← میانگین Z مؤلفه‌های موجود (دست‌کم ۲ مؤلفه).
  حقوق صاحبان سهام منفی ← سهم بیرون می‌ماند. مؤلفهٔ ثبات به‌جای «انحراف معیار رشد EPS» (MSCI) است چون رشد اسمی EPS در تورم ایران
  را تورم می‌چرخاند؛ ROE بی‌مقیاس است.
زمان دانستن (point-in-time): سال مالی از «تاریخ اعلام» اولین EPS ۱۲‌ماههٔ همان سال (rahavard_eps.csv، period = 12) به بعد قابل‌استفاده است
  (+۱ روز برای معامله)؛ اگر نبود، پایان سال مالی + ۱۲۰ روز [تأیید لازم]. سال مالی قدیمی‌تر از ۵۴۰ روز کنار می‌رود.
تاریخ ستون‌های جدول رهاورد به‌عنوان تاریخ انتشار استفاده نمی‌شود (آخرین نسخهٔ سال مالی را نشان می‌دهد، نه نخستین انتشار).
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from fetch_corporate_actions import j2g  # noqa: E402

FUND = ROOT / "data" / "fundamentals"
STALE_DAYS, DEFAULT_LAG, MIN_SECTOR = 540, 120, 6


def available() -> bool:
    return (FUND / "rahavard_long.csv").exists() and (FUND / "rahavard_eps.csv").exists()


def fy_date(s: str) -> pd.Timestamp:
    y, m, d = map(int, s.split("/"))
    return pd.Timestamp(str(j2g(y, m, d))[:10])


def load_records() -> dict:
    """ins_code → DataFrame[fy_end, avail, roe, de, equity] برای هر سال مالی."""
    L = pd.read_csv(FUND / "rahavard_long.csv", dtype={"ins_code": str})
    L = L[L.stmt.isin(["ratio", "bs"])].copy()
    E = pd.read_csv(FUND / "rahavard_eps.csv", dtype={"ins_code": str})
    E = E[E.period == 12].copy()
    E["date"] = pd.to_datetime(E["date"])
    E["fy"] = pd.to_datetime(E["fy"])
    first = E.groupby(["ins_code", "fy"]).date.min()
    L["fy_end"] = L.fy.map({s: fy_date(s) for s in L.fy.unique()})
    L["row_n"] = L.row.str.replace(r"[‌\s]+", "", regex=True)
    pick = {"roe": L.row_n.str.contains("ROE"), "de": L.row_n == "نسبتبدهیبهارزشویژه",
            "equity": (L.stmt == "bs") & L.row_n.str.startswith("جمعحقوقصاحبانسهام") & ~L.row_n.str.contains("مصوب")}
    parts = []
    for k, m in pick.items():
        x = L[m].sort_values(["audited", "represented"]).groupby(["ins_code", "fy_end"]).value.last().rename(k)   # حسابرسی‌شده/تجدیدارائه‌شده ترجیح دارد
        parts.append(x)
    P = pd.concat(parts, axis=1).reset_index()
    P["avail"] = [first.get((c, f), pd.NaT) for c, f in zip(P.ins_code, P.fy_end)]
    P["avail"] = P.avail.fillna(P.fy_end + pd.Timedelta(days=DEFAULT_LAG)) + pd.Timedelta(days=1)
    return {c: g.sort_values("fy_end").reset_index(drop=True) for c, g in P.groupby("ins_code")}


def raw_components(rec: dict, when: pd.Timestamp):
    """(roe, de, roe_std, fy_end) آخرین دادهٔ شناخته‌شده تا when یا None."""
    g = rec[rec.avail <= when]
    if g.empty:
        return None
    last = g.iloc[-1]
    if (when - last.fy_end).days > STALE_DAYS or not (last.equity > 0):
        return None
    h = g[g.equity > 0].roe.dropna().tail(5)
    return last.roe, last.de, (h.std(ddof=1) if len(h) >= 3 else np.nan), last.fy_end


def zsec(x: pd.Series, sec: pd.Series) -> pd.Series:
    lo, hi = x.quantile(0.01), x.quantile(0.99)
    x = x.clip(lo, hi)
    g, m, s = x.groupby(sec), x.groupby(sec).transform("mean"), x.groupby(sec).transform("std")
    n = x.groupby(sec).transform("count")
    z_glob = (x - x.mean()) / (x.std() or 1)
    z = (x - m) / s.replace(0, np.nan)
    return z.where(n >= MIN_SECTOR, z_glob).clip(-3, 3)


def scores(dates, cols, sector: pd.Series, recs: dict | None = None) -> pd.DataFrame:
    """DataFrame[date × ins_code] امتیاز ترکیبی (NaN = بی‌داده). sector: ins_code → نام صنعت."""
    recs = recs or load_records()
    out = pd.DataFrame(np.nan, index=pd.DatetimeIndex(dates), columns=list(cols))
    sec_all = sector.reindex(out.columns).fillna("؟")
    for t in out.index:
        rows = {}
        for c in out.columns:
            if c in recs:
                v = raw_components(recs[c], t)
                if v is not None:
                    rows[c] = v
        if len(rows) < 30:
            continue
        D = pd.DataFrame(rows, index=["roe", "de", "sd", "fy"]).T
        D[["roe", "de", "sd"]] = D[["roe", "de", "sd"]].astype(float)
        sec = sec_all.reindex(D.index)
        Z = pd.concat([zsec(D.roe, sec), -zsec(D.de, sec), -zsec(D.sd.dropna(), sec.reindex(D.sd.dropna().index)).reindex(D.index)], axis=1)
        ok = Z.notna().sum(axis=1) >= 2
        out.loc[t, Z.index[ok]] = Z[ok].mean(axis=1).values
    return out


def coverage(S: pd.DataFrame) -> dict:
    n = S.notna().sum(axis=1)
    return {"min": int(n.min()), "median": int(n.median()), "max": int(n.max()), "first": str(n[n > 0].index[0].date()) if (n > 0).any() else None}


if __name__ == "__main__":
    if not available():
        sys.exit("ابتدا tools/fetch_rahavard_fundamentals.py را روی سیستم خود اجرا و push کنید.")
    R = load_records()
    print(f"{len(R)} نماد، میانگین {np.mean([len(g) for g in R.values()]):.1f} سال مالی")
