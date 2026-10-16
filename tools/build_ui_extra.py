#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ بخش‌های دوم UI (ui/data/extra.js = window.SIM_EXTRA): Dividend Lab، Data QA، Rebalance، Factor Lab، Reports.

    python tools/build_ui_extra.py

همهٔ اعداد از همان محاسبه‌های tools/ می‌آیند؛ هیچ عدد ساختگی نیست.
Factor Lab فقط «پیش‌نمایش پژوهشی» است (مومنتوم ۱۲−۱، بدون هزینه، با سوگیری بقای باقی‌مانده) و در UI همین‌طور برچسب می‌خورد.
"""
import json
import re
from datetime import datetime

import numpy as np
import pandas as pd

import check_sector_indices as cs
import investable_replica as ir
import rebuild_cw_index as cw
import rebuild_ew_index as ew
import rebuild_ew_rebalanced as ewr

ROOT = ew.ROOT
OUT = ROOT / "ui" / "data" / "extra.js"


def r(x, n=4):
    return None if pd.isna(x) else round(float(x), n)


# ── Dividend Lab ─────────────────────────────────────────────────────────
def divlab():
    out = {}
    for name in ir.PAIRS:
        j = ir.load_pair(name)
        yrs = len(j) / 252
        month = j.y.groupby(j.index.map(lambda d: ewr.g2j(d.year, d.month, d.day)[1])).sum()
        scen = []
        for L in (0, 30, 60, 90, 120, 180, 240):
            row = {"lag": L}
            a = ir.stats(ir.simulate(j, L), j.tr)
            row["A"] = {k: r(v, 4) for k, v in a.items()}
            for rb in (0.25, 0.35):
                b = ir.stats(ir.simulate(j, L, rb), j.tr)
                row[f"B{int(rb*100)}"] = {k: r(v, 4) for k, v in b.items()}
            scen.append(row)
        out[name] = {"dates": [str(d.date()) for d in j.index], "tr": [round(float(v), 7) for v in j.tr],
                     "pr": [round(float(v), 7) for v in j.pr], "y_ann_pct": r(j.y.sum() / yrs * 100, 2),
                     "month_share": [r(month.get(m, 0) / j.y.sum() * 100, 1) for m in range(1, 13)],
                     "scenarios": scen, "from": str(j.index[0].date()), "to": str(j.index[-1].date())}
    ca = ROOT / "data/corporate_actions"
    n = lambda f: int(len(pd.read_csv(ca / f))) if (ca / f).exists() else 0   # noqa: E731
    out["payment_data"] = {"available": n("codal_payment_schedule_raw.csv") > 0, "rows": n("codal_payment_schedule_raw.csv"),
                           "agm_rows": n("codal_agm.csv")}
    return out


# ── پایهٔ مشترک: ماتریس بازده و وزن ──────────────────────────────────────
def base_panel():
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    panel = ew.load_panel()
    R = cw.classify_events(ew.daily_returns(panel), sc)
    R["shares"] = cw.shares_timeline(R, sc, info)
    R = R.dropna(subset=["shares"]).copy()
    R["w"] = R.priceYesterday * R.shares
    R["wt"] = R.w / R.groupby("date").w.transform("sum")
    return panel, info, R


# ── Rebalance ────────────────────────────────────────────────────────────
def rebalance(R):
    M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M = M[M.index >= "2014-03-19"]
    sym = R.drop_duplicates("ins_code").set_index("ins_code").symbol
    out = {"policies": [], "last": []}
    for pol in ("jalali-month", "jalali-quarter", "jalali-halfyear", "jalali-year"):
        flags = ewr.rebalance_flags(M.index, pol)
        X = M.values
        n, k = X.shape
        w = np.zeros(k)
        turns, rows = [], []
        for t in range(n):
            avail = ~np.isnan(X[t])
            if flags[t] or w.sum() == 0:
                tgt = np.where(avail, 1.0, 0.0)
                tgt /= tgt.sum()
                if t > 0 and w.sum() > 0:
                    cur = np.where(avail, w, 0.0)
                    cur = cur / cur.sum() if cur.sum() else cur
                    turn = 0.5 * np.abs(tgt - cur).sum()
                    turns.append(turn)
                    rows.append((M.index[t], int(avail.sum()), turn, int(((tgt > 0) & (cur == 0)).sum()), int(((tgt == 0) & (cur > 0)).sum())))
                w = tgt
            else:
                w = np.where(avail, w, 0.0)
                if w.sum() == 0:
                    w = np.where(avail, 1.0, 0.0)
                w = w / w.sum()
            rr = np.where(avail, X[t], 0.0)
            rp = (w * rr).sum()
            w = w * (1 + rr) / (1 + rp)
        yrs = len(M) / 252
        sr = ewr.portfolio_returns(M, flags)
        jj = pd.concat([sr, ew.official(ew.OFFICIAL["TR"])], axis=1, join="inner").dropna()
        jj.columns = ["m", "o"]
        jj = jj[jj.index >= "2014-03-20"]
        dd = jj.m - jj.o
        out["policies"].append({"policy": pol, "n_rebal": len(turns), "avg_turn_pct": r(np.mean(turns) * 100, 1),
                                "annual_turn_pct": r(sum(turns) / yrs * 100, 1), "te": r(dd.std() * np.sqrt(252) * 100, 2),
                                "corr": r(jj.m.corr(jj.o), 4), "cum_ratio": r((1 + jj.m).prod() / (1 + jj.o).prod(), 3)})
        if pol == "jalali-quarter":
            out["last"] = [{"date": str(d.date()), "n": a, "turn_pct": r(t * 100, 1), "in": i, "out": o} for d, a, t, i, o in rows[-12:]]
    # ارزش‌وزن: ریبالانس ماهانه/فصلی به وزن‌های ارزش بازار؛ گردش = نیمِ مجموع |وزن هدف − وزن رانش‌یافتهٔ دورهٔ قبل|
    W = R.pivot_table(index="date", columns="ins_code", values="wt", aggfunc="last")
    Rt = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last").reindex(W.index)
    W, Rt = W[W.index >= "2014-03-19"], Rt[Rt.index >= "2014-03-19"]
    cap = {}
    for pol in ("jalali-month", "jalali-quarter"):
        fl = ewr.rebalance_flags(W.index, pol)
        idx = np.where(fl)[0]
        turns = []
        for a, b in zip(idx[:-1], idx[1:]):
            w0 = W.iloc[a].fillna(0).values
            w0 = w0 / w0.sum()
            g = np.nan_to_num(np.nancumprod(1 + np.nan_to_num(Rt.iloc[a + 1:b + 1].values), axis=0)[-1] if b > a else np.ones(len(w0)), nan=1.0)
            drift = w0 * g
            drift = drift / drift.sum()
            w1 = W.iloc[b].fillna(0).values
            tot = w1.sum()
            if tot == 0:
                continue
            w1 = w1 / tot
            turns.append(0.5 * np.abs(w1 - drift).sum())
        yrs = len(W) / 252
        cap[pol] = {"n": len(turns), "avg_turn_pct": r(np.mean(turns) * 100, 1), "annual_turn_pct": r(sum(turns) / yrs * 100, 1)}
    out["cap"] = cap
    return out


# ── Factor Lab: مومنتوم ۱۲−۱ (پیش‌نمایش پژوهشی) ────────────────────────────
def factor(R):
    M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M = M[M.index >= "2012-01-01"]
    dates = M.index
    jm = np.array([ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1] for d in dates])
    month_end = np.where(jm[1:] != jm[:-1])[0]            # آخرین روز هر ماه شمسی
    X = M.values
    lr = np.log1p(np.where(np.isnan(X), 0, X))
    cum = np.vstack([np.zeros(X.shape[1]), np.cumsum(lr, axis=0)])
    nz = np.vstack([np.zeros(X.shape[1]), np.cumsum((np.nan_to_num(X) != 0), axis=0)])
    have = np.vstack([np.zeros(X.shape[1]), np.cumsum(~np.isnan(X), axis=0)])
    # سیگنال از ۲۰۱۵-۰۳ (پیش از آن ردیف‌های ۲۰۱۲–۲۰۱۴ هنوز تعدیل‌نشده‌های پراکنده دارند) ← ارزیابی از ۲۰۱۶-۰۳-۲۱
    start = int(np.searchsorted(dates, pd.Timestamp("2016-03-20")))
    port = {q: np.full(len(dates), np.nan) for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "ALL")}
    names = {q: [] for q in port}
    holds = {}
    for a, b in zip(month_end[:-1], month_end[1:]):
        if a < 252 + 21 or a < start - 1:
            continue
        i1, i0 = a + 1 - 21, a + 1 - 252                # [t−252, t−21) → سیگنال 12−1
        ok = ((have[i1] - have[i0]) >= 0.8 * (i1 - i0)) & ((nz[i1] - nz[i0]) >= 0.5 * (i1 - i0)) & ~np.isnan(X[a + 1]) & ~np.isnan(X[min(b, len(dates) - 1)])
        ok &= ~np.isnan(X[a])
        score = cum[i1] - cum[i0]
        idx = np.where(ok)[0]
        if len(idx) < 50:
            continue
        order = idx[np.argsort(score[idx])]
        groups = np.array_split(order, 5)
        holds[a] = {f"Q{k+1}": g for k, g in enumerate(groups)}
        holds[a]["ALL"] = idx
        for q, g in holds[a].items():
            seg = X[a + 1:b + 1][:, g]
            port[q][a + 1:b + 1] = np.nanmean(seg, axis=1)
            names[q].append(len(g))
    S = pd.DataFrame(port, index=dates).dropna(how="all")
    S = S[S.index >= "2016-03-21"]
    yrs = len(S) / 252
    res = {"ann": {}, "curve": {}}
    for q in S.columns:
        c = (1 + S[q].fillna(0)).prod()
        res["ann"][q] = r((c ** (1 / yrs) - 1) * 100, 1)
    ls = S.Q5 - S.Q1
    res["ls_ann_pct"] = r(((1 + ls.fillna(0)).prod() ** (1 / yrs) - 1) * 100, 1)
    res["q5_minus_all_te"] = r((S.Q5 - S.ALL).std() * np.sqrt(252) * 100, 1)
    res["ls_vol_pct"] = r(ls.std() * np.sqrt(252) * 100, 1)
    res["q5_excess_ann_pct"] = r(res["ann"]["Q5"] - res["ann"]["ALL"], 1)
    res["n_months"] = len(holds)
    res["avg_names"] = {q: int(np.mean(v)) for q, v in names.items()}
    yearly = []
    for y, g in S.groupby(S.index.map(lambda d: ewr.g2j(d.year, d.month, d.day)[0])):
        yr = {q: r(((1 + g[q].fillna(0)).prod() - 1) * 100, 1) for q in ("Q1", "Q5", "ALL")}
        yearly.append({"jy": int(y), **yr, "ls": r(yr["Q5"] - yr["Q1"], 1), "days": len(g)})
    res["yearly"] = yearly
    me = S.index[[i for i in range(len(S)) if i % 21 == 0 or i == len(S) - 1]]
    for q in ("Q1", "Q3", "Q5", "ALL"):
        res["curve"][q] = [round(float(v), 2) for v in ((1 + S[q].fillna(0)).cumprod() * 100).reindex(me)]
    res["curve"]["dates"] = [str(d.date()) for d in me]
    # گردش سبد Q5 (سهم اعضای عوض‌شده در هر ماه)
    keys = sorted(holds)
    ch = [1 - len(set(holds[b]["Q5"]) & set(holds[a]["Q5"])) / max(len(holds[b]["Q5"]), 1) for a, b in zip(keys[:-1], keys[1:])]
    res["q5_monthly_turnover_pct"] = r(np.mean(ch) * 100, 1)
    res["from"], res["to"] = str(S.index[0].date()), str(S.index[-1].date())
    return res


# ── Data QA ──────────────────────────────────────────────────────────────
def qa(panel, info, R):
    sec = cs.compute()
    nm = info.dropna(subset=["sector_name"]).assign(sec=lambda d: d.sector_code.astype(str).str.strip().str.lstrip("0")).drop_duplicates("sec").set_index("sec").sector_name
    sectors = [{"sector": s, "name": str(nm.get(s.lstrip("0"), "")).strip(), "n_last": int(a), "n_miss": int(b), "corr": r(c, 4), "te": r(d, 2), "cum": r(e, 3),
                "n_all": int(f), "corr_all": r(g, 4), "te_all": r(h, 2)}
               for s, a, b, c, d, e, _, f, g, h in sec.itertuples(index=False)]
    glitches = []
    for f in sorted((ROOT / "data/indices").glob("index_*.csv")):
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date").close
        _, ev = ew.clean_level(d)
        if ev:
            code = f.stem.split("_")[1]
            name = {"32097828799138957": "شاخص كل", "67130298613737946": "كل (هم وزن)", "30655480864841493": "TEDPIX",
                    "49579049405614711": "آزاد شناور"}.get(code) or (("صنعت " + cs.SECTORS[code]) if code in cs.SECTORS else f"شاخص {code[:6]}…")
            kinds = {}
            for _, k, _ in ev:
                kinds[k] = kinds.get(k, 0) + 1
            glitches.append({"code": code, "name": name, "n": len(ev), "kinds": kinds, "first": str(ev[0][0].date()), "last": str(ev[-1][0].date())})
    cons = pd.read_csv(ROOT / "data/index_constituents.csv", dtype=str)
    kmem = set(cons[cons.index_code == "32097828799138957"].ins_code)
    have = {p.name.split(".")[0] for p in (ROOT / "data/prices").glob("*.csv.gz")}
    lastd = panel.groupby("ins_code").date.max()
    live = lastd[lastd >= lastd.max() - pd.Timedelta(days=30)].index
    ex = pd.read_csv(ROOT / "data/instruments_extra.csv", dtype=str)
    rules = {"rule7": int(R.get("capital_fixed", pd.Series(dtype=bool)).sum()),
             "rule8": int(panel.shape[0] and R.adjA.notna().sum()) if "adjA" in R else 0,
             "dividend_events": int(R.is_dividend.sum()), "rows_used": int(len(R))}
    return {"sectors": sectors, "glitches": glitches,
            "universe": {"k_members": len(kmem), "k_with_prices": len(kmem & have), "extras": int(len(ex)),
                         "instruments_with_prices": len(have), "live_instruments": int(len(live)),
                         "stocks_bourse_in_returns": int(R.ins_code.nunique())},
            "rules": rules,
            "sector_summary": {"comparable": int(sum(1 for s in sectors if s["te"] is not None)),
                               "median_te": r(np.nanmedian([min(x for x in (s["te"], s["te_all"]) if x is not None) for s in sectors if s["te"] is not None]), 2),
                               "n_corr99": int(sum(1 for s in sectors if s["te"] is not None and max(s["corr"] or 0, s["corr_all"] or 0) >= 0.99))}}


# ── Reports ──────────────────────────────────────────────────────────────
def reports():
    txt = (ROOT / "docs/CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    rows = []
    for ln in txt:
        if not ln.startswith("| ۲۰"):
            continue
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) < 3:
            continue
        m = re.search(r"\*\*(.+?)\*\*", c[1])
        rows.append({"date": c[0], "title": (m.group(1) if m else c[1][:80]), "text": c[1], "chapters": c[-1]})
    docs = []
    for p in sorted((ROOT / "docs").glob("[0-9][0-9]-*.md")):
        t = next((ln.lstrip("# ").strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.startswith("# ")), p.name)
        docs.append({"file": p.name, "title": t, "kb": round(p.stat().st_size / 1e3)})
    tools = [{"file": p.name, "doc": (re.search(r'"""(.+?)(?:\n|""")', p.read_text(encoding="utf-8"), re.S) or [None, ""])[1].strip()[:110]}
             for p in sorted((ROOT / "tools").glob("*.py"))]
    return {"changelog": rows, "docs": docs, "tools": tools}


def main():
    panel, info, R = base_panel()
    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "divlab": divlab(), "rebalance": rebalance(R),
            "factor": factor(R), "qa": qa(panel, info, R), "reports": reports()}
    OUT.write_text("window.SIM_EXTRA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} ({OUT.stat().st_size/1e3:.0f} KB)")
    print("factor:", json.dumps({k: v for k, v in data["factor"].items() if k not in ("curve", "yearly")}, ensure_ascii=False))
    print("rebalance:", json.dumps({"policies": data["rebalance"]["policies"], "cap": data["rebalance"]["cap"]}, ensure_ascii=False)[:900])
    print("qa:", json.dumps({k: data["qa"][k] for k in ("universe", "rules", "sector_summary")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
