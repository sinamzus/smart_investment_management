#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ نمای «نماد» در UI (ui/data/symbols.js = window.SIM_SYMBOLS): هر سهم بورسیِ جهان بازسازی.

    python tools/build_ui_symbols.py

برای هر نماد: سطح بازده کل (TR) و قیمت تعدیل‌شده (PR) هفتگی از ۲۰۱۴، رویدادهای تعدیل (سود/سرمایه با قاعدهٔ ±۷ روز)،
تغییرهای سرمایه، سود مصوب مجمع از کدال (اگر جمع‌آوری شده)، و آمار: بازده ۱/۳ سال، نوسان، افت از اوج، بتا به «شاخص كل»، وزن.
"""
import json
from datetime import datetime

import numpy as np
import pandas as pd

import build_ui_extra as bx
import rebuild_ew_index as ew

ROOT = ew.ROOT
OUT = ROOT / "ui" / "data" / "symbols.js"
START = "2014-03-20"


def r(x, n=4):
    return None if x is None or pd.isna(x) else round(float(x), n)


def main():
    panel, info, R = bx.base_panel()
    R = R[R.date >= START]
    kret = ew.official("32097828799138957")
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    pa = pd.read_csv(ROOT / "data/corporate_actions/price_adjust.csv", dtype={"ins_code": str})
    pa["date"] = pd.to_datetime(pa.dEven.astype(str), format="%Y%m%d", errors="coerce")
    agm_p = ROOT / "data/corporate_actions/codal_agm.csv"
    agm = pd.read_csv(agm_p, dtype=str) if agm_p.exists() else pd.DataFrame(columns=["symbol"])
    if len(agm):
        agm = agm.sort_values("tracing").drop_duplicates(["symbol", "period_end_j"], keep="last")
    nm = info.set_index("ins_code")
    last_day = R.date.max()
    alive = set(R[R.date == last_day].ins_code)
    n_alive = len(alive)
    out = {}
    for code, g in R.groupby("ins_code"):
        g = g.sort_values("date")
        if len(g) < 60:
            continue
        tr = (1 + g.r_tr).cumprod()
        pr = (1 + g.r_pr).cumprod()
        idx = list(range(0, len(g), 5)) + ([len(g) - 1] if (len(g) - 1) % 5 else [])
        rr = g.set_index("date").r_tr
        y1 = rr[rr.index > last_day - pd.Timedelta(days=365)]
        y3 = rr[rr.index > last_day - pd.Timedelta(days=3 * 365)]
        j = pd.concat([y1, kret], axis=1, join="inner").dropna()
        beta = j.iloc[:, 0].cov(j.iloc[:, 1]) / j.iloc[:, 1].var() if len(j) > 60 else None
        dd = (tr / tr.cummax() - 1).min()
        s_sc = {c for c in sc[sc.ins_code == code].date}
        ev = []
        for x in pa[pa.ins_code == code].itertuples():
            if pd.isna(x.date) or x.date < pd.Timestamp(START):
                continue
            cap = any(abs((x.date - d).days) <= 7 for d in s_sc)
            ev.append([str(x.date.date()), "cap" if cap else "div", r(x.pClosing, 0), r(x.pClosingNotAdjusted, 0)])
        caps = [[str(x.date.date()), r(x.shares_old, 0), r(x.shares_new, 0)] for x in sc[sc.ins_code == code].itertuples() if x.date >= pd.Timestamp(START)]
        sym = g.symbol.iloc[-1]
        ag = [[a.period_end_j, a.session_date_j, int(float(a.dps_rial)) if isinstance(a.dps_rial, str) and a.dps_rial.strip() else None] for a in agm[agm.symbol == sym].itertuples()] if len(agm) else []
        lg = g.iloc[-1]
        out[sym] = {
            "name": str(g.name.iloc[-1] if "name" in g else ""), "sector": str(nm.sector_name.get(code, "") or "").strip(),
            "code": code, "alive": code in alive, "first": str(g.date.iloc[0].date()), "last": str(g.date.iloc[-1].date()),
            "d": [str(g.date.iloc[i].date()) for i in idx], "tr": [r(tr.iloc[i], 4) for i in idx], "pr": [r(pr.iloc[i], 4) for i in idx],
            "price": r(lg.pClosing, 0), "mcap": r(lg.pClosing * lg.shares, 0), "w_k": r(lg.wt * 100, 4) if code in alive else None,
            "w_ew": r(100 / n_alive, 4) if code in alive else None,
            "ret1y": r(((1 + y1).prod() - 1) * 100, 1), "ret3y_ann": r(((1 + y3).prod() ** (365 / max((y3.index[-1] - y3.index[0]).days, 1)) - 1) * 100, 1) if len(y3) > 200 else None,
            "vol1y": r(y1.std() * np.sqrt(252) * 100, 1), "mdd": r(dd * 100, 1), "beta1y": r(beta, 2),
            "nontraded1y": r((g[g.date > last_day - pd.Timedelta(days=365)].zTotTran == 0).mean() * 100, 1) if "zTotTran" in g else None,
            "events": ev, "capchg": caps, "agm": ag,
        }
    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "asof": str(last_day.date()), "n": len(out), "symbols": out}
    OUT.write_text("window.SIM_SYMBOLS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} ({OUT.stat().st_size/1e6:.1f} MB) — {len(out)} نماد")


if __name__ == "__main__":
    main()
