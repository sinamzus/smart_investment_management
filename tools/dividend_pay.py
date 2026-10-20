#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""روز پرداخت واقعی هر سود نقدی برای مدل «تأخیر سود و وام پل» همتاساز (فصل ۳ §۳٫۵).

ورودی: Market (signals.Market؛ mk.Y بازده سود نقدی روز استحقاق) و data/corporate_actions/dividend_events_merged.csv.
خروجی: {(t, i): p} — روز استحقاق t و ستون نماد i ⇒ اندیس نخستین روز معاملاتی ≥ تاریخ پرداخت (اگر پس از پایان داده باشد، mk.n).
اولویت تاریخ پرداخت: فارابی، سپس fundai؛ اگر نبود یا پیش از استحقاق بود: استحقاق + PAY_LAG_DAYS (همان build_ui_portfolio.py).
رویداد پانل با رویداد فهرست سود اگر تاریخ استحقاقشان حداکثر MATCH_DAYS روز فاصله داشته باشد تطبیق داده می‌شود.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PAY_LAG_DAYS = 96                     # میانهٔ تأخیر استحقاق تا پرداخت (فصل ۳ §۳٫۵)؛ همان build_ui_portfolio.PAY_LAG_DAYS
MATCH_DAYS = 7


def _jiso(s):
    from jalali import j2g_str
    try:
        y, m, d = (int(x) for x in str(s).split("/"))
        return j2g_str(y, m, d, strict=False)
    except Exception:  # noqa: BLE001
        return None


def pay_days(mk) -> dict:
    Y = np.nan_to_num(mk.Y)
    ti, ii = np.nonzero(Y > 0)
    if not len(ti):
        return {}
    M = pd.read_csv(ROOT / "data/corporate_actions/dividend_events_merged.csv", dtype={"ins_code": str})
    M["ex"] = pd.to_datetime(M.ex_date, errors="coerce")
    pay = []
    for x in M.itertuples():
        p = _jiso(x.farabi_pay_j) if pd.notna(x.farabi_pay_j) else None
        if not p and pd.notna(x.fd_pay):
            p = str(x.fd_pay)[:10]
        pay.append(pd.Timestamp(p) if p else pd.NaT)
    M["pay"] = pay
    M = M.dropna(subset=["ex"])
    by = {c: g.sort_values("ex") for c, g in M.groupby("ins_code")}
    dates = mk.dates
    out = {}
    real = 0
    for t, i in zip(ti, ii):
        d = dates[t]
        p = pd.NaT
        g = by.get(str(mk.cols[i]))
        if g is not None:
            gap = (g.ex - d).abs()
            j = gap.idxmin()
            if gap[j] <= pd.Timedelta(days=MATCH_DAYS) and pd.notna(g.pay[j]) and g.pay[j] >= d:
                p = g.pay[j]
                real += 1
        if pd.isna(p):
            p = d + pd.Timedelta(days=PAY_LAG_DAYS)
        out[(int(t), int(i))] = max(int(dates.searchsorted(p)), int(t) + 1)   # نخستین روز معاملاتی ≥ پرداخت (دست‌کم فردا)؛ پس از پایان داده = mk.n
    pay_days.real = real                                                # شمار رویدادهای با تاریخ پرداخت واقعی (گزارش)
    return out


def lag_summary(mk, pays: dict) -> dict:
    """میانه و میانگین تأخیر (روز تقویمی) و سهم رویدادهای با تاریخ پرداخت واقعی — برای گزارش."""
    lags = [(mk.dates[min(p, mk.n - 1)] - mk.dates[t]).days for (t, _), p in pays.items() if p < mk.n]
    return {"n": len(pays), "real": getattr(pay_days, "real", None), "median": float(np.median(lags)) if lags else None, "mean": float(np.mean(lags)) if lags else None}
