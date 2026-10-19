#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ممیزی کمّی سوگیری‌ها روی دادهٔ واقعی (فصل ۰۸ §۸٫۶؛ ممیزی ۲۰۲۶-۱۰-۱۹). اعداد را چاپ می‌کند؛ چیزی نمی‌نویسد.

    python tools/audit_bias.py

- بقا: شمار نمادهای پانل عملیاتی به تفکیک سال ورود و سال خروج (در بازار سالم خروج سالانه صفر نیست).
- بی‌معاملگی: سهم ردیف‌های با حجم صفر در سال‌های نمونه.
- استراتژی قفل‌شده (tools/live_ledger.frozen_spec): میانگین وزن در نمادهای بی‌معاملهٔ روز سیگنال/اجرا پیش از فیلتر (آنچه مدل قدیمی
  معامله می‌کرد) و سهم وزن منجمد (نگه‌داشته و غیرقابل‌فروش) پس از قاعدهٔ A2.
- بنیادی: شمار اعلام‌های سالانهٔ رهاورد با تاریخ ناممکن (هم‌زمان/پیش از پایان سال مالی) پیش از جابه‌جایی.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_lab as bl  # noqa: E402
import construction as cn  # noqa: E402
import live_ledger as ll  # noqa: E402


def main():
    mk, lab, _ = bl.get_lab()
    X, vol = mk.X, mk.vol
    has = ~np.isnan(X)
    first = np.argmax(has, axis=0)
    last = mk.n - 1 - np.argmax(has[::-1], axis=0)
    fl = pd.DataFrame({"first": mk.dates[first].year, "last": mk.dates[last].year})
    print(f"پانل عملیاتی: {mk.k} نماد؛ ورود به تفکیک سال: {fl['first'].value_counts().sort_index().to_dict()}")
    print(f"  خروج به تفکیک سال آخرین داده: {fl['last'].value_counts().sort_index().to_dict()}")
    years = pd.Series(mk.dates.year)
    for y in sorted(set(years))[::3]:
        m = (years == y).values
        if has[m].sum():
            print(f"  {y}: ردیف {has[m].sum()}، حجم صفر {100 * (has[m] & ~(np.nan_to_num(vol[m]) > 0)).sum() / has[m].sum():.1f}٪")
    spec = ll.frozen_spec()
    res = cn.backtest(lab, spec, keep_weights=1, live=False)
    ze = []
    for k_, (r, w) in enumerate(res["weights"]):
        a = lab.me[r]
        tr = mk.tradable(a, spec.get("delay", 0))
        ze.append(w[~tr].sum() - res["frozen"][k_])      # وزن غیرمنجمد در نماد غیرقابل‌معامله = خرید ناممکن (باید صفر باشد)
    print(f"استراتژی قفل‌شده ({len(res['weights'])} ماه): وزن منجمد (نگه‌داشته، روز اجرا بی‌معامله) میانگین {100 * np.nanmean(res['frozen']):.2f}٪، "
          f"بیشینه {100 * np.nanmax(res['frozen']):.2f}٪؛ وزن خریدهٔ ناممکن (باید ۰ باشد) بیشینه {100 * max(ze):.3f}٪")
    f = ROOT / "data/fundamentals/rahavard_eps.csv"
    if f.exists():
        E = pd.read_csv(f, dtype={"ins_code": str}, parse_dates=["date", "fy"])
        a = E[E.period == 12]
        print(f"رهاورد: {len(a)} اعلام سالانه؛ تاریخ ناممکن (≤ پایان سال مالی): {(a.date <= a.fy).sum()} (در signals.clamp_announce جابه‌جا می‌شود)")


if __name__ == "__main__":
    main()
