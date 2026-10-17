#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تجزیهٔ بازده فعال صندوق شاخصی با موجودی پرتفو (فصل ۳ §۳٫۶): ترکیب پرتفو، نقد، تأخیر سود، یا باقیمانده؟

ورودی: data/funds/holdings_<نماد>.csv با ستون‌های date (ISO، تاریخ گزارش پرتفو), symbol (نماد بورس), weight_pct (درصد از کل دارایی)
(پس از parser نامه‌های کدال: tools/fetch_fund_portfolio.py). درصدهای مجموع < ۱۰۰ = نقد و سایر.

برای هر گزارش در تاریخ D تا گزارش بعدی D′ (حداکثر ۴۵ روز تقویمی)، با وزن‌های D و خرید و نگهداری:
  hold_TR     : بازده کل (TR) سهام با وزن‌های پرتفو، نقد بدون بازده
  hold_TR_nc  : همان با وزن‌های بازنرمال‌شده بدون نقد
  hold_lag    : سهام با بازده قیمتی (PR) + سودها L روز بعد از استحقاق دریافت می‌شوند (طلب بی‌بازده) + نقد بدون بازده
  b           : مرجع TR رسمی؛ f: NAV صندوق (همان بازده روزانه)
اثرها (واحد درصد، مرکب روی بازه):
  ترکیب  = hold_TR_nc − b           ← سهام پرتفو با وزن واقعی در برابر شاخص، با فرض سود فوراً سرمایه‌گذاری و بدون نقد
  نقد    = hold_TR − hold_TR_nc     ← بازده‌ای که نقد نگه‌داشته‌شده از دست می‌دهد
  تأخیر  = hold_lag − hold_TR       ← هزینهٔ دریافت دیرهنگام سود (L روز)
  باقی   = f − hold_lag             ← کارمزد، قیمت‌گذاری NAV (آخرین معامله)، معاملات درون ماه، سهام خارج از دادهٔ ما
نماد ناشناس (در جهان ما نیست) در «پوشش» می‌آید؛ پوشش کم یعنی تحلیل را باید با احتیاط خواند.
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

import build_ui_extra as bx
import rebuild_ew_index as ew
import rebuild_ew_rebalanced as ewr

ROOT = ew.ROOT
FUNDS = Path(os.environ.get("SIM_FUNDS_DIR", ROOT / "data" / "funds"))
LAG = 90
MAXWIN = 45


def norm(t) -> str:
    return str(t or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ").strip().replace("  ", " ")


_PANEL = {}


def panel():
    if not _PANEL:
        _, _, R = bx.base_panel()
        R = R[R.date >= "2014-03-19"].copy()
        R["sym"] = R.symbol.map(norm)
        _PANEL["tr"] = R.pivot_table(index="date", columns="sym", values="r_tr", aggfunc="last")
        _PANEL["pr"] = R.pivot_table(index="date", columns="sym", values="r_pr", aggfunc="last")
    return _PANEL["tr"], _PANEL["pr"]


def load_holdings(sym: str) -> pd.DataFrame | None:
    p = FUNDS / f"holdings_{sym}.csv"
    if not p.exists():
        return None
    h = pd.read_csv(p, parse_dates=["date"])
    h["symbol"] = h.symbol.map(norm)
    return h


def _window(h_d: pd.DataFrame, tr: pd.DataFrame, pr: pd.DataFrame, days: pd.DatetimeIndex, lag: int):
    """سه مسیر بازده (TR، TR بدون نقد، قیمت+سود با تأخیر) روی روزهای days برای وزن‌های h_d."""
    syms = [s for s in h_d.symbol if s in tr.columns]
    w = h_d.set_index("symbol").weight_pct.reindex(syms).astype(float) / 100
    cov = float(w.sum())
    cash = max(1 - float(h_d.weight_pct.sum()) / 100, 0.0)
    if not syms:
        return None
    X = tr.loc[days, syms].fillna(0).values
    P = pr.loc[days, syms].fillna(0).values
    Y = X - P                                              # بازده سود نقدی روزانه هر سهم
    # TR با نقد
    pos = (w.values[None, :] * np.cumprod(1 + X, axis=0))
    v_tr = pos.sum(axis=1) + cash + (1 - cov - cash)       # سهام ناشناخته/باقیمانده بدون بازده
    # بدون نقد
    wn = w.values / cov
    v_nc = (wn[None, :] * np.cumprod(1 + X, axis=0)).sum(axis=1)
    # قیمت + سود با تأخیر
    pos_p = w.values[None, :] * np.cumprod(1 + P, axis=0)
    div_cash = pos_p * Y                                   # سود روز t (به نسبت ارزش پایان روز؛ تقریب مرتبه اول)
    paid = np.zeros(len(days))
    dts = days.values
    recv = np.zeros(len(days))                             # سود طلب‌شدهٔ هنوز نرسیده
    cum_pay = np.zeros(len(days))
    for t in range(len(days)):
        amt = div_cash[t].sum()
        due = days[t] + pd.Timedelta(days=lag)
        k = np.searchsorted(dts, np.datetime64(due))
        recv[t:k] += amt                                   # تا روز پرداخت طلب است
        if k < len(days):
            cum_pay[k:] += amt                             # از روز پرداخت، نقد (بی‌بازده)
    v_lag = pos_p.sum(axis=1) + cash + (1 - cov - cash) + recv + cum_pay
    return v_tr, v_nc, v_lag, cov


def analyze(sym: str, fund_ret: pd.Series, bench_ret: pd.Series, lag: int = LAG) -> dict | None:
    h = load_holdings(sym)
    if h is None or h.empty:
        return None
    tr, pr = panel()
    dates = sorted(h.date.unique())
    rows = []
    for i, d in enumerate(dates):
        end = dates[i + 1] if i + 1 < len(dates) else d + pd.Timedelta(days=MAXWIN)
        end = min(end, d + pd.Timedelta(days=MAXWIN))
        days = tr.index[(tr.index > d) & (tr.index <= end)]
        days = days.intersection(fund_ret.index).intersection(bench_ret.index)
        if len(days) < 8:
            continue
        hd = h[h.date == d]
        res = _window(hd, tr, pr, days, lag)
        if res is None:
            continue
        v_tr, v_nc, v_lag, cov = res
        f = float((1 + fund_ret.reindex(days)).prod() - 1)
        b = float((1 + bench_ret.reindex(days)).prod() - 1)
        a, c, l = v_nc[-1] - 1, v_tr[-1] - 1, v_lag[-1] - 1
        known = hd[hd.symbol.isin(tr.columns)].weight_pct.sum()
        rows.append({"date": str(d.date()), "days": len(days), "f": f * 100, "b": b * 100, "active": (f - b) * 100,
                     "composition": (a - b) * 100, "cash": (c - a) * 100, "lag": (l - c) * 100, "residual": (f - l) * 100,
                     "coverage": float(known), "cash_pct": float(100 - hd.weight_pct.sum()),
                     "n": int(len(hd)), "hold_tr": c * 100})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    comp = ["composition", "cash", "lag", "residual"]
    ss = {k: float((df[k] ** 2).sum()) for k in comp}
    tot = sum(ss.values()) or 1.0
    return {"lag": lag, "n": len(df), "from": df.date.iloc[0], "to": df.date.iloc[-1],
            "mean": {k: round(float(df[k].mean()), 2) for k in comp + ["active"]},
            "rms": {k: round(float(np.sqrt((df[k] ** 2).mean())), 2) for k in comp + ["active"]},
            "share": {k: round(ss[k] / tot, 3) for k in comp},
            "coverage": round(float(df.coverage.mean()), 1), "cash_pct": round(float(df.cash_pct.mean()), 1),
            "rows": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()} for r in rows]}


def main():
    import build_ui_funds as bf
    bench = {k: ew.official(c) for k, (c, _) in bf.BENCH.items()}
    meta = pd.read_csv(FUNDS / "funds.csv", dtype=str).fillna("").to_dict("records")
    for m in meta:
        nd = bf.load_nav(m["symbol"])
        if nd is None or (FUNDS / f"holdings_{m['symbol']}.csv").exists() is False:
            continue
        x = nd.ret_daily.dropna()
        x = x / 100 if x.abs().median() > 0.05 else x
        b = bench[m["benchmark"]]
        a = (x - b.reindex(x.index)).dropna()
        x = x.copy()
        x[a[a.abs() > bf.EVENT].index] = b.reindex(a[a.abs() > bf.EVENT].index)
        res = analyze(m["symbol"], x, b)
        if res:
            print(f"{m['symbol']}: {res['n']} ماه؛ فعال میانگین {res['mean']['active']}٪؛ سهم مربعات: {res['share']}؛ پوشش {res['coverage']}٪")


if __name__ == "__main__":
    main()
