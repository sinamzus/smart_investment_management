#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی «شاخص كل (هم وزن)» از قیمت‌های روزانهٔ نمادها و مقایسه با سری رسمی.

    python tools/rebuild_ew_index.py            # گزارش مقایسه
    python tools/rebuild_ew_index.py --save     # ذخیرهٔ سری بازسازی‌شده در data/derived/

قواعد (از آزمون روی داده، فصل ۰۳ §۳.۴):
  1. بازدهی روزانهٔ هر نماد = pClosing / priceYesterday − 1  (قیمت مبنای روز؛ فصل ۰۲ §۲.۴)
  2. فقط سهام بازار «bourse» (با افزودن فرابورس خطا بیشتر می‌شود)
     و بدون نمادهای تکراری با پسوند رقم (مثل «سخزر3» در کنار «سخزر»: همان سهم با قیمت
     یکسان؛ ۲۸۶ از ۶۵۲ نماد) — شمارش مضاعف و خطای ۲۰۲۶ را حذف می‌کند
  3. روز اول معامله هر نماد حذف می‌شود (مبنای قراردادی ۱۰۰۰ ریال، بازده بی‌معنی)
  4. ردیف‌های بدون معامله با بازده صفر می‌مانند (نماد در شاخص هست)
  5. ردیف‌های داده‌ای معیوب حذف می‌شوند: pClosing ≤ 1 یا بازده ≤ −۹۰٪ یا priceYesterday ≤ 0
  6. شاخص = میانگین ساده بازدهی نمادها در هر روز، تجمعی هندسی
"""
import argparse
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = {"TR": "67130298613737946", "PR": "8384385859414435"}  # كل (هم وزن) / قيمت (هم وزن)


def load_panel() -> pd.DataFrame:
    inst = pd.read_csv(ROOT / "data/instruments.csv", dtype={"ins_code": str})
    extra_p = ROOT / "data/instruments_extra.csv"
    if extra_p.exists():  # سهام خارج از MarketWatch (fetch_stock_daily.py --search)
        ex = pd.read_csv(extra_p, dtype={"ins_code": str})
        ex = ex[~ex.ins_code.isin(inst.ins_code) & ~ex.name.str.startswith("آتی")].assign(market="bourse", type="stock", base_volume=0)
        info_p = ROOT / "data/corporate_actions/instrument_info.csv"
        if info_p.exists():  # بازار واقعی از flow (۱ = بورس، ۲ = فرابورس)
            fl = pd.read_csv(info_p, dtype={"ins_code": str}).set_index("ins_code").flow
            ex["market"] = ex.ins_code.map(fl).map({1: "bourse", 2: "farabourse"}).fillna("bourse")
        inst = pd.concat([inst, ex[["ins_code", "symbol", "name", "market", "type", "base_volume"]]], ignore_index=True)
    cols = ["dEven", "pClosing", "priceYesterday", "zTotTran"]
    frames = []
    for f in glob.glob(str(ROOT / "data/prices/*.csv.gz")):
        d = pd.read_csv(f, usecols=cols, dtype=float)
        d["ins_code"] = os.path.basename(f).split(".")[0]
        frames.append(d)
    P = pd.concat(frames, ignore_index=True)
    P["date"] = pd.to_datetime(P["dEven"].astype(int).astype(str), format="%Y%m%d")
    P = P.merge(inst[["ins_code", "symbol", "market", "type", "name"]], on="ins_code", how="left")
    # تصحیح طبقه‌بندی با فهرست رسمی اعضای «شاخص كل» (data/index_constituents.csv):
    # شرکت‌هایی مثل «وصندوق» (سرمایه‌گذاری صندوق بازنشستگی) و «بورس» به‌خطا صندوق/اوراق شمرده می‌شدند.
    cons_p = ROOT / "data/index_constituents.csv"
    if cons_p.exists():
        cons = pd.read_csv(cons_p, dtype={"ins_code": str})
        kmem = set(cons[cons.index_code == "32097828799138957"].ins_code)
        P.loc[P.ins_code.isin(kmem) & (P.type != "stock"), ["market", "type"]] = ["bourse", "stock"]
    P.loc[P.name.fillna("").str.startswith("ص ") & ~P.ins_code.isin(kmem if cons_p.exists() else set()), "type"] = "fund"
    return P


def daily_returns(P: pd.DataFrame, markets=("bourse",)) -> pd.DataFrame:
    P = P[P.market.isin(markets) & (P.type == "stock")].copy()
    syms = set(P.symbol)
    dup = P.symbol.str.contains(r"\d$") & P.symbol.str.replace(r"\d+$", "", regex=True).isin(syms)
    P = P[~dup].copy()                                  # قاعدهٔ ۲ (تکراری‌های رقمی)
    P["traded"] = P.zTotTran > 0
    first = P[P.traded].groupby("ins_code").date.min().rename("first_trade")
    P = P.merge(first, on="ins_code", how="left")
    P = P[P.date > P.first_trade]                      # قاعدهٔ ۳
    P = P[(P.priceYesterday > 0) & (P.pClosing > 1)]    # قاعدهٔ ۵
    P["r"] = P.pClosing / P.priceYesterday - 1          # قاعدهٔ ۱
    return P[P.r > -0.9]


def clean_level(d: pd.Series) -> tuple[pd.Series, list]:
    """رفع جهش‌های ×۱۰ / ÷۱۰ در سطح شاخص رسمی (خطای دادهٔ منبع).

    - جفتِ «افت ~÷۱۰ و بازگشت ~×۱۰» ظرف ۳ ردیف = ردیف‌های وسط خطای تک‌روزه‌اند → حذف.
    - افت ÷۱۰ بدون بازگشت = تغییر مقیاس دائمی → بقیهٔ سری ×۱۰ می‌شود (و برعکس).
    """
    d = d.copy()
    events = []
    i = 1
    while i < len(d):
        r = d.iloc[i] / d.iloc[i - 1]
        if 0.07 <= r <= 0.13 or 7.5 <= r <= 13.0:
            f = 10.0 if r < 1 else 0.1
            back = None
            for k in range(i + 1, min(i + 4, len(d))):
                rr = d.iloc[k] / d.iloc[k - 1]
                if (r < 1 and 7.5 <= rr <= 13.0) or (r > 1 and 0.07 <= rr <= 0.13):
                    back = k
                    break
            if back is not None:
                events.append((d.index[i], "glitch", back - i))
                d = d.drop(d.index[i:back])
                continue
            events.append((d.index[i], "rescale", f))
            d.iloc[i:] = d.iloc[i:] * f
        i += 1
    return d, events


def official(code: str) -> pd.Series:
    d = pd.read_csv(ROOT / f"data/indices/index_{code}.csv", parse_dates=["date"]).set_index("date").close
    d, _ = clean_level(d)
    return d.pct_change().dropna()


def compare(mine: pd.Series, off: pd.Series, name: str) -> pd.DataFrame:
    j = pd.concat([mine, off], axis=1, join="inner").dropna()
    j.columns = ["mine", "official"]
    j = j[j.index >= "2014-03-20"]
    d = j.mine - j.official
    print(f"{name}: n={len(j)} corr={j.mine.corr(j.official):.4f} mean={d.mean()*1e4:.2f}bp "
          f"MAD={d.abs().mean()*1e4:.2f}bp TE={d.std()*np.sqrt(252)*100:.2f}% "
          f"days>50bp={(d.abs() > 5e-3).sum()} cum_ratio={(1+j.mine).prod()/(1+j.official).prod():.3f}")
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    R = daily_returns(load_panel())
    mine = R.groupby("date").r.mean()
    n = R.groupby("date").ins_code.nunique()
    print(f"روز: {len(mine)}، میانگین تعداد نماد در روز: {n.mean():.0f}\n")
    jt = compare(mine, official(OFFICIAL["TR"]), "در برابر كل (هم وزن)    [TR]")
    jp = compare(mine, official(OFFICIAL["PR"]), "در برابر قيمت (هم وزن)  [PR]")
    d = (jp.mine - jp.official)
    print("\nMAD سالانه در برابر PR (bp):", {y: round(v * 1e4, 1) for y, v in d.abs().groupby(d.index.year).mean().items()})
    print("میانگین اختلاف سالانه (bp):  ", {y: round(v * 1e4, 1) for y, v in d.groupby(d.index.year).mean().items()})
    print("\nبیشترین اختلاف‌ها در برابر PR:")
    print((d.abs().sort_values(ascending=False).head(8) * 1e4).round(1).to_string())
    if a.save:
        out = ROOT / "data/derived"
        out.mkdir(parents=True, exist_ok=True)
        s = pd.DataFrame({"ret": mine, "n_symbols": n})
        s["index"] = 10000 * (1 + s.ret).cumprod()
        s.to_csv(out / "ew_rebuilt_bourse.csv", index_label="date")
        print("ذخیره شد:", out / "ew_rebuilt_bourse.csv")


if __name__ == "__main__":
    main()
