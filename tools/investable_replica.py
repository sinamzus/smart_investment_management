#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ماکت سرمایه‌پذیر شاخص‌های رسمی با تأخیر پرداخت سود نقدی (فصل ۳ §۳.۵).

    python tools/investable_replica.py                  # جدول سناریوها
    python tools/investable_replica.py --save           # data/derived/investable_*.csv

مسئله: شاخص‌های «بازده کل» رسمی (TR) سود نقدی را همان روز استحقاق (افت قیمت) دوباره سرمایه‌گذاری می‌کنند،
ولی پولش بعداً (L روز) می‌رسد. مجری که شاخص را عیناً (بدون محدودیت سرمایه) بخرد این تفاوت را تحمل می‌کند.

داده: فقط سری‌های رسمی: TR و PR (قیمت) هر شاخص. سود نقدی روزانه y_t = r_TR − r_PR (بخش مثبت).
  K  : «شاخص كل»(TR) و «قيمت وزني-ارزشي»(PR)       EW: «كل (هم وزن)»(TR) و «قيمت (هم وزن)»(PR)

مدل (ارزش پرتفوی V، مطالبات سود A به مبلغ ریال):
  V_t = V_{t-1}(1 + r_PR,t) + پرداخت‌های رسیده؛  در روز استحقاق مبلغ V_{t-1}·y_t به مطالبات اضافه و بعد از L روز تقویمی
  (اولین روز معاملاتی) پرداخت و با وزن‌های همان روز سرمایه‌گذاری می‌شود. NAV = V + A (مطالبات به ارزش اسمی).
راهبردها:
  A «نقدی»   : بدون تأمین مالی؛ مطالبات تا پرداخت بی‌بازده می‌مانند.
  B «تأمین‌مالی‌شده»: در روز استحقاق معادل مطالبات با نرخ rb (سالانه) وام گرفته و همان لحظه به شاخص اضافه می‌شود،
                 با پرداخت سود وام بسته می‌شود؛ هزینه = بهرهٔ وام فقط.
"""
import argparse

import numpy as np
import pandas as pd

import rebuild_ew_index as ew

ROOT = ew.ROOT
PAIRS = {
    "K": ("32097828799138957", "5798407779416661"),
    "EW": ("67130298613737946", "8384385859414435"),
}


def load_pair(name: str):
    tr = ew.official(PAIRS[name][0])
    pr = ew.official(PAIRS[name][1])
    j = pd.concat([tr, pr], axis=1, join="inner").dropna()
    j.columns = ["tr", "pr"]
    j = j[j.index >= "2009-01-01"]
    j["y_raw"] = j.tr - j.pr
    j["y"] = j.y_raw
    return j


def simulate(j: pd.DataFrame, lag_days, rb: float | None = None) -> pd.DataFrame:
    """lag_days: عدد (ثابت) یا فهرست (lag, سهم) برای مخلوط تأخیرها."""
    mix = [(lag_days, 1.0)] if np.isscalar(lag_days) else list(lag_days)
    dates = j.index
    n = len(dates)
    pay_idx = [np.searchsorted(dates.values, (dates + pd.Timedelta(days=int(L))).values, side="left") for L, _ in mix]
    shares = [s for _, s in mix]
    V = 1.0
    A = 0.0
    B = 0.0          # وام (راهبرد B)
    due = np.zeros(n + 1)
    nav = np.empty(n)
    prev = None
    for t in range(n):
        d = dates[t]
        days = 0 if prev is None else (d - prev).days
        prev = d
        if rb is not None and B > 0:
            V -= B * rb * days / 365.0          # بهره از پرتفوی پرداخت می‌شود (فروش واحد)، وام اصل می‌ماند
        V *= 1 + j.pr.iloc[t]
        y = j.y.iloc[t]
        if y != 0:
            amt = V * y / (1 + j.pr.iloc[t])      # مبلغ سود بر پایهٔ ارزش پایان روز قبل
            for pi, s in zip(pay_idx, shares):
                k = min(pi[t], n)
                due[k] += amt * s
            A += amt
            if rb is not None:
                V += amt
                B += amt
        paid = due[t]
        if paid != 0:
            A -= paid
            if rb is not None:
                B -= paid
            else:
                V += paid
        nav[t] = V + A - B
    return pd.Series(nav, index=dates)


def stats(nav: pd.Series, tr: pd.Series) -> dict:
    r = nav.pct_change().fillna(nav.iloc[0] - 1)
    d = (r - tr).dropna()
    yrs = (d.index[-1] - d.index[0]).days / 365.25      # سال تقویمی (بازار ایران ~۲۴۰ روز معاملاتی، نه ۲۵۲)
    cum_nav, cum_tr = (1 + r).prod(), (1 + tr).prod()
    gap = (cum_nav / cum_tr) ** (1 / yrs) - 1
    return {"cum_ratio": cum_nav / cum_tr, "gap_pct_yr": gap * 100, "te_pct": d.std() * np.sqrt(252) * 100}


def report(name: str, j: pd.DataFrame, lags, rates):
    yrs = (j.index[-1] - j.index[0]).days / 365.25
    y_ann = j.y.sum() / yrs * 100
    print(f"\n── {name}: {j.index[0].date()}..{j.index[-1].date()} ({len(j)} روز)؛ سود نقدی ضمنی ≈ {y_ann:.2f}٪ در سال؛ "
          f"y منفی حذف‌شده: {(-j.y_raw.clip(upper=0)).sum()*100:.2f} واحد درصد در کل دوره")
    rows = []
    for L in lags:
        a = stats(simulate(j, L), j.tr)
        row = {"lag": L, "A_cum": a["cum_ratio"], "A_gap_yr": a["gap_pct_yr"], "A_te": a["te_pct"]}
        for rb in rates:
            b = stats(simulate(j, L, rb), j.tr)
            row[f"B{int(rb*100)}_gap_yr"] = b["gap_pct_yr"]
            row[f"B{int(rb*100)}_te"] = b["te_pct"]
        rows.append(row)
    df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(df.round(3).to_string(index=False))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--lags", default="0,30,60,90,120,180,240")
    ap.add_argument("--rates", default="0.25,0.35")
    a = ap.parse_args()
    lags = [int(x) for x in a.lags.split(",")]
    rates = [float(x) for x in a.rates.split(",")]
    out = {}
    for name in PAIRS:
        j = load_pair(name)
        out[name] = report(name, j, lags, rates)
        # فصلی‌بودن سود: سهم هر ماه شمسی از کل y
        m = j.y.groupby([j.index.map(lambda d: ew_g2j_month(d))]).sum()
        print("سهم ماه شمسی از کل سود نقدی (٪):", {k: round(v / j.y.sum() * 100, 1) for k, v in m.items()})
    if a.save:
        o = ROOT / "data/derived"
        for name, df in out.items():
            df.to_csv(o / f"investable_lag_scenarios_{name}.csv", index=False)
        print("ذخیره شد")


def ew_g2j_month(d):
    from rebuild_ew_rebalanced import g2j
    return g2j(d.year, d.month, d.day)[1]


if __name__ == "__main__":
    main()
