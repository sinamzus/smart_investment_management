#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ساخت بستهٔ داده برای UI (ui/data/data.js) از دادهٔ واقعی مخزن.

    python tools/build_ui_data.py

ورودی: data/indices (رسمی)، data/prices، data/corporate_actions، data/instruments.csv
خروجی: ui/data/data.js  (window.SIM_DATA = {...})  — با file:// هم باز می‌شود، بدون سرور.
هیچ عددی ساختگی نیست؛ همه از همان محاسبه‌هایی می‌آیند که در tools/rebuild_*.py استفاده شده است.
"""
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

import rebuild_cw_index as cw
import rebuild_ew_index as ew
import rebuild_ew_rebalanced as ewr

ROOT = ew.ROOT
OUT = ROOT / "ui" / "data" / "data.js"
START = "2014-03-20"


def r4(x, n=4):
    return None if pd.isna(x) else round(float(x), n)


def stats(mine: pd.Series, off: pd.Series, start=START) -> dict:
    j = pd.concat([mine, off], axis=1, join="inner").dropna()
    j.columns = ["m", "o"]
    j = j[j.index >= start]
    d = j.m - j.o
    return {"n": int(len(j)), "corr": r4(j.m.corr(j.o), 4), "te": r4(d.std() * np.sqrt(252) * 100, 2),
            "mad_bp": r4(d.abs().mean() * 1e4, 1), "mean_bp": r4(d.mean() * 1e4, 2),
            "cum_ratio": r4((1 + j.m).prod() / (1 + j.o).prod(), 3),
            "td_bp": r4(((1 + j.m).prod() / (1 + j.o).prod() - 1) * 1e4, 0),
            "days50": int((d.abs() > 5e-3).sum()), "from": str(j.index[0].date()), "to": str(j.index[-1].date())}


def levels(x: pd.Series, dates) -> list:
    s = (1 + x.reindex(dates).fillna(0)).cumprod() * 100
    return [round(float(v), 3) for v in s]


def period_returns(mine: pd.Series, off: pd.Series, dates) -> list:
    out = []
    for lab, n in [("۱ ماه", 21), ("۳ ماه", 63), ("۶ ماه", 126), ("۱ سال", 252), ("۳ سال", 756), ("از ابتدا", None)]:
        idx = dates if n is None else dates[-n:]
        a = ((1 + off.reindex(idx).fillna(0)).prod() - 1) * 100
        b = ((1 + mine.reindex(idx).fillna(0)).prod() - 1) * 100
        out.append({"label": lab, "off": r4(a, 2), "mine": r4(b, 2), "diff_bp": r4((b - a) * 100, 0)})
    return out


def dev_days(mine: pd.Series, off: pd.Series, contrib: pd.DataFrame, k=10) -> list:
    j = pd.concat([mine, off], axis=1, join="inner").dropna()
    j.columns = ["m", "o"]
    j = j[j.index >= START]
    d = (j.m - j.o)
    out = []
    for dt in d.abs().sort_values(ascending=False).head(k).index:
        c = contrib[contrib.date == dt].copy()
        c["a"] = c.contrib.abs()
        top = c.sort_values("a", ascending=False).head(3)
        out.append({"date": str(dt.date()), "mine": r4(j.m[dt] * 100, 2), "off": r4(j.o[dt] * 100, 2),
                    "diff_bp": r4(d[dt] * 1e4, 1),
                    "top": [{"sym": s, "bp": r4(v * 1e4, 0)} for s, v in zip(top.symbol, top.contrib)]})
    return out


def main():
    inst = pd.read_csv(ROOT / "data/instruments.csv", dtype={"ins_code": str})
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    adj = pd.read_csv(ROOT / "data/corporate_actions/price_adjust.csv", dtype={"ins_code": str})

    panel = ew.load_panel()
    R = cw.classify_events(ew.daily_returns(panel), sc)
    R["shares"] = cw.shares_timeline(R, sc, info)
    R = R.dropna(subset=["shares"]).copy()
    R["w"] = R.priceYesterday * R.shares
    den = R.groupby("date").w.sum()
    R["wt"] = R.w / R.date.map(den)
    nsym = R.groupby("date").ins_code.nunique()

    # ── شاخص ارزش‌وزن (TR-type) و هم‌وزن (فصل شمسی) ──
    k_mine = (R.r_tr * R.wt).groupby(R.date).sum()
    M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M = M[M.index >= "2014-03-19"]
    ew_mine = ewr.portfolio_returns(M, ewr.rebalance_flags(M.index, "jalali-quarter"))
    k_off, ew_off = ew.official("32097828799138957"), ew.official(ew.OFFICIAL["TR"])

    dates = k_off.index[k_off.index >= START].intersection(k_mine.index).intersection(ew_off.index).intersection(ew_mine.index)

    # ── روزهای بیشترین انحراف + مشارکت نمادها ──
    R["contrib_k"] = R.r_tr * R.wt
    nday = R.date.map(nsym)
    R["contrib_ew"] = R.r_tr / nday
    ck = R[["date", "symbol", "contrib_k"]].rename(columns={"contrib_k": "contrib"})
    ce = R[["date", "symbol", "contrib_ew"]].rename(columns={"contrib_ew": "contrib"})

    # ── ترکیب فعلی ──
    last = R.date.max()
    L = R[R.date == last].merge(info[["ins_code", "sector_name"]], on="ins_code", how="left")
    L["w_cw"] = L.wt
    L["w_ew"] = 1.0 / len(L)
    L = L.sort_values("w_cw", ascending=False)
    sec = L.groupby("sector_name").agg(w_cw=("w_cw", "sum"), n=("ins_code", "count")).sort_values("w_cw", ascending=False)
    comp = {
        "asof": str(last.date()), "n": int(len(L)), "top1": r4(L.w_cw.iloc[0] * 100, 2),
        "top5": r4(L.w_cw.head(5).sum() * 100, 1), "top10": r4(L.w_cw.head(10).sum() * 100, 1),
        "eff_n": r4(1 / (L.w_cw ** 2).sum(), 1), "w_ew": r4(100 / len(L), 3),
        "top": [{"sym": r.symbol, "name": r["name"], "sector": r.sector_name, "w_cw": r4(r.w_cw * 100, 2),
                 "w_ew": r4(r.w_ew * 100, 3)} for _, r in L.head(15).iterrows()],
        "sectors": [{"name": n, "w_cw": r4(v.w_cw * 100, 1), "n": int(v.n)} for n, v in sec.head(8).iterrows()],
    }

    # ── شمارش قواعد پاک‌سازی (برای نوار Lineage و QA) ──
    P = panel[(panel.market == "bourse") & (panel.type == "stock")]
    digit_dup = P.symbol.str.contains(r"\d$") & P.symbol.str.replace(r"\d+$", "", regex=True).isin(set(P.symbol))
    qa = {"rows_bourse_stock": int(len(P)), "rows_digit_dups": int(digit_dup.sum()),
          "rows_used": int(len(R)), "rule7_fixed": int(R.get("capital_fixed", pd.Series(dtype=bool)).sum()),
          "dividend_events": int(R.is_dividend.sum())}

    data = {
        "meta": {
            "built": datetime.now().strftime("%Y-%m-%d %H:%M"), "asof": str(dates[-1].date()), "start": START,
            "n_instruments": int(panel.ins_code.nunique()), "n_stocks_bourse": int(P.ins_code.nunique()),
            "n_price_rows": int(len(panel)), "n_adjust_events": int(len(adj)), "n_share_events": int(len(sc)),
            "n_universe_last": int(len(L)), "universe": "بورس · سهام · بدون نمادهای فنی رقم‌دار",
        },
        "series": {"dates": [str(d.date()) for d in dates], "K_off": levels(k_off, dates), "K_mine": levels(k_mine, dates),
                   "EW_off": levels(ew_off, dates), "EW_mine": levels(ew_mine, dates)},
        "stats": {
            "K": {"all": stats(k_mine, k_off), "y2016": stats(k_mine, k_off, "2016-01-01")},
            "EW": {"all": stats(ew_mine, ew_off), "y2016": stats(ew_mine, ew_off, "2016-01-01")},
        },
        "periods": {"K": period_returns(k_mine, k_off, dates), "EW": period_returns(ew_mine, ew_off, dates)},
        "devdays": {"K": dev_days(k_mine, k_off, ck), "EW": dev_days(ew_mine, ew_off, ce)},
        "comp": comp, "qa": qa,
        "labels": {"K": {"title": "شاخص كل (ارزش‌وزن)", "off": "شاخص كل — رسمی", "mine": "بازسازی (بازده کل)",
                         "method": "ارزش‌وزن C/B−1 · تعداد سهام تاریخی"},
                   "EW": {"title": "شاخص كل (هم وزن)", "off": "كل (هم وزن) — رسمی", "mine": "بازسازی (ریبالانس فصل شمسی)",
                          "method": "هم‌وزن · ریبالانس فصلی با رانش وزن"}},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("window.SIM_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} ({OUT.stat().st_size/1e3:.0f} KB)  asof={data['meta']['asof']}  points={len(dates)}")
    print(json.dumps(data["stats"], ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
