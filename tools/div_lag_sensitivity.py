#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حساسیت برتری استراتژی به تأخیر دریافت سود نقدی (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹، B1).

بازده کل نظری (r_TR) سود را همان روز استحقاق دوباره سرمایه‌گذاری می‌کند؛ پول واقعاً L روز بعد می‌رسد (فصل ۰۳ §۳٫۵: میانگین ≈ ۵۷ روز
تقویمی برای «شاخص كل»). اینجا سری بازده هر نماد با سود «با تأخیر» ساخته می‌شود: r_lag = r_PR + y شیفت‌خورده به L روز معاملاتی بعد
(در فاصله، مطالبه بی‌بازده است) و بک‌تست مشخصات داده‌شده با همین سری تکرار می‌شود. معیارها (از جمله div_yield) دست نمی‌خورند.

    python tools/div_lag_sensitivity.py                 # مشخصات قفل‌شدهٔ زنده (tools/live_ledger.frozen_spec) با L = ۰، ۴۰، ۶۰ روز معاملاتی
    python tools/div_lag_sensitivity.py --lags 0,40     # روزهای معاملاتی
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_lab as bl  # noqa: E402
import construction as cn  # noqa: E402
import factor_engine as fe  # noqa: E402


def lagged_market(mk, L: int):
    """نسخه‌ای از Market که در آن سود نقدی به‌جای سرمایه‌گذاری مجدد در روز استحقاق، L روز معاملاتی بی‌بازده می‌ماند (L = ۰ ⇒ همان TR).

    حق سود متعلق به دارندهٔ روز استحقاق است؛ پس هزینهٔ تأخیر هم باید به همان روز و همان دارنده نسبت داده شود، نه به دارندهٔ روز
    پرداخت (نسخهٔ اول سود را به روز t+L منتقل می‌کرد و استراتژی‌ای که بعد از استحقاق می‌خرد سود نکسب‌کرده را می‌گرفت — بازده بالا می‌رفت).
    روش: در TR، سود y در روز t با قیمت همان روز بازسرمایه‌گذاری و تا t+L به y·G می‌رسد (G = رشد سهم در L روز بعد)؛ با تأخیر، همان
    مطالبه در t+L فقط y است. معادل در روز t: y به y/G کاهش می‌یابد ⇒ X'_t = X_t − y_t·(1 − 1/G_t). G از بازده‌های بعدی ساخته می‌شود
    (حسابداری بازده تحقق‌یافته، نه ورودی تصمیم؛ معیارها دست نمی‌خورند)."""
    if L <= 0:
        return mk
    m2 = copy.copy(mk)
    Y = np.nan_to_num(mk.Y)                             # بخش مثبت r_TR − r_PR (سود نقدی روز استحقاق؛ Market.Y)
    LR = np.log1p(np.nan_to_num(mk.X))
    c = np.vstack([np.zeros(mk.k), np.cumsum(LR, axis=0)])
    n = mk.n
    hi = np.minimum(np.arange(n) + 1 + L, n)            # جمع لگاریتم بازده روزهای t+1 .. t+L
    G = np.exp(c[hi] - c[np.arange(n) + 1])
    X2 = np.where(np.isnan(mk.X), np.nan, np.nan_to_num(mk.X) - Y * (1.0 - 1.0 / G))
    m2.X = X2
    return m2


def run(spec, lags):
    mk, lab, _ = bl.get_lab()
    cost = spec.get("cost_bp", bl.COST)
    out = []
    for L in lags:
        m2 = lagged_market(mk, L)
        lab2 = cn.Lab(m2, lab.idx, lab.S)
        res = cn.backtest(lab2, spec, live=False)
        st = fe.stats_of(res, "S", cost)
        out.append((L, st["excess_net"], st["t_net"], st["ann_net"], st["ann_all_net"]))
        print(f"L = {L:>3} روز معاملاتی: برتری خالص {st['excess_net']:+.2f}٪ (t = {st['t_net']:.2f})؛ استراتژی {st['ann_net']:.2f}٪، مرجع {st['ann_all_net']:.2f}٪")
    base = out[0]
    for L, ex, t, s, a in out[1:]:
        print(f"  اثر تأخیر {L}: استراتژی {s - base[3]:+.2f}، مرجع {a - base[4]:+.2f}، برتری {ex - base[1]:+.2f} واحد درصد")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lags", default="0,40,60")
    a = ap.parse_args()
    import live_ledger as ll
    run(ll.frozen_spec(), [int(x) for x in a.lags.split(",")])


if __name__ == "__main__":
    main()
