#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ بخش‌های دوم UI (ui/data/extra.js = window.SIM_EXTRA): Dividend Lab، Data QA، Rebalance، Factor Lab، Reports.

    python tools/build_ui_extra.py

همهٔ اعداد از همان محاسبه‌های tools/ می‌آیند؛ هیچ عدد ساختگی نیست.
Factor Lab: بک‌تست ماهانهٔ پنج‌گانه‌ها با سری ماهانهٔ ناخالص و گردش واقعی وزن هر پنجک؛ هزینه و آزمون‌های آماری
(t نیوی‌وست، IR، نرخ برد) در UI روی همین سری‌ها حساب می‌شوند تا هزینه قابل‌تنظیم باشد.
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
def pay_events() -> pd.DataFrame:
    """رویدادهای دارای تاریخ پرداخت و روز استحقاق (tools/merge_dividend_payments.py: کدال ن-۱۳ + فارابی)، با تأخیر ≥ ۰."""
    f = ROOT / "data/corporate_actions/dividend_payment_events.csv"
    if not f.exists():
        return pd.DataFrame()
    E = pd.read_csv(f, dtype={"ex_date": str}).fillna({"ex_date": ""})
    E = E[E.ex_date != ""].copy()
    E["lag"] = pd.to_numeric(E.lag_ex, errors="coerce").clip(lower=0)
    return E.dropna(subset=["lag"])


def pay_mix(E: pd.DataFrame, w: str) -> list:
    """[(تأخیر روز، وزن نرمال)] برای simulate؛ وزن = سهم رویداد از جریان سود شاخص (wK یا wEW)."""
    if E.empty or E[w].fillna(0).sum() <= 0:
        return []
    g_ = E.assign(L=E.lag.round().astype(int)).groupby("L")[w].sum()
    g_ = g_[g_ > 0]
    return [(int(L), float(v / g_.sum())) for L, v in g_.items()]


def pay_lags() -> pd.Series:
    """تأخیر هر رویداد (بدون وزن) — برای آمار توصیفی و سازگاری با build_ui_funds."""
    E = pay_events()
    return E.lag if len(E) else pd.Series(dtype=float)


def wstat(E: pd.DataFrame, w: str) -> dict:
    ww = E[w].fillna(0)
    o = np.argsort(E.lag.values)
    cw_ = np.cumsum(ww.values[o]) / ww.sum()
    return {"mean": int(round(float((E.lag * ww).sum() / ww.sum()))), "median": int(E.lag.values[o][np.searchsorted(cw_, 0.5)])}


def divlab():
    out = {}
    E_all = pay_events()
    mixes = {"K": pay_mix(E_all, "wK"), "EW": pay_mix(E_all, "wEW")}
    for name in ir.PAIRS:
        j = ir.load_pair(name)
        yrs = (j.index[-1] - j.index[0]).days / 365.25       # سال تقویمی
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
        mix, emp = mixes.get(name) or [], None
        if mix:      # توزیع تجربی تأخیر؛ وزن هر رویداد = سهمش از جریان سود همان شاخص
            emp = {"A": {k: r(v, 4) for k, v in ir.stats(ir.simulate(j, mix), j.tr).items()}}
            for rb in (0.25, 0.35):
                emp[f"B{int(rb*100)}"] = {k: r(v, 4) for k, v in ir.stats(ir.simulate(j, mix, rb), j.tr).items()}
        out[name] = {"empirical": emp, "empirical_mix": [[L, round(w_, 5)] for L, w_ in mix] or None,
                     "dates": [str(d.date()) for d in j.index], "tr": [round(float(v), 7) for v in j.tr],
                     "pr": [round(float(v), 7) for v in j.pr], "y_ann_pct": r(j.y.sum() / yrs * 100, 2),
                     "month_share": [r(month.get(m, 0) / j.y.sum() * 100, 1) for m in range(1, 13)],
                     "scenarios": scen, "from": str(j.index[0].date()), "to": str(j.index[-1].date())}
    ca = ROOT / "data/corporate_actions"
    n = lambda f: int(len(pd.read_csv(ca / f))) if (ca / f).exists() else 0   # noqa: E731
    out["payment_data"] = {"available": n("codal_payment_schedule_raw.csv") > 0, "rows": n("codal_payment_schedule_raw.csv"),
                           "agm_rows": n("codal_agm.csv")}
    if len(E_all):
        ev = pd.read_csv(ca / "dividend_payment_events.csv", dtype=str).fillna("")
        lags = E_all.lag
        bins = [0, 15, 30, 60, 90, 120, 180, 10000]
        lab = [f"{a_}–{b_ if b_ < 10000 else '+'}" for a_, b_ in zip(bins[:-1], bins[1:])]
        cut = pd.cut(lags, bins, right=False, labels=lab)
        h = cut.value_counts(sort=False)
        hK = (E_all.wK.fillna(0).groupby(cut, observed=False).sum() / E_all.wK.sum()).reindex(lab).fillna(0)
        by_year = {y: {"n": int(len(x)), "median": int(x.median())} for y, x in lags.groupby(E_all.agm_j.str[:4])}
        P = pd.read_csv(ca / "codal_payment_dates.csv", dtype=str).fillna("")
        cov = pd.read_csv(ca / "dividend_payment_coverage.csv") if (ca / "dividend_payment_coverage.csv").exists() else pd.DataFrame()
        out["payment_data"].update({
            "events": int(len(ev)), "with_date": int(len(ev)), "with_ex": int(len(E_all)), "symbols": int(ev.symbol.nunique()),
            "sources": ev.source.value_counts().to_dict(), "letters_text": int((P.chars.astype(int) > 200).sum()), "letters": int(len(P)),
            "median": int(lags.median()), "mean": int(round(lags.mean())), "q25": int(lags.quantile(.25)), "q75": int(lags.quantile(.75)),
            "k": wstat(E_all, "wK"), "ew": wstat(E_all, "wEW"),
            "hist": [[l_, int(h.get(l_, 0)), round(float(hK.get(l_, 0)) * 100, 1)] for l_ in lab], "by_year": by_year,
            "coverage": cov.to_dict("records")})
    return out


# ── پایهٔ مشترک: ماتریس بازده و وزن ──────────────────────────────────────
# ابزارهای غیرشرکتی که TSETMC «سهام» ثبت کرده: صندوق‌ها (ص.س.، ص.ج.، ص.خ.)، امتیاز تسهیلات مسکن، گواهی اعتبار مولد، مرابحه، تامین مالی جمعی، سلف، اختیار…
# توجه: «ص.» به‌تنهایی مخفف «صنایع/صنعتی» است (ص.چاپ، ص.معدنی…)، پس فقط ص.س / ص.ج / ص.خ حذف می‌شود.
NONOP = re.compile(r"^\s*ص\.\s?(?:س|ج|خ)[\. ]|^\s*صندوق|^\s*امتیاز|^\s*گواهی|^\s*مراحبه|^\s*مرابحه|^\s*تامین مالی جمعی|^\s*اختیار|^\s*سلف|^\s*اوراق|^\s*اجاره|^\s*صکوک|^\s*ETF")
ALL_MARKETS = ("bourse", "farabourse")      # جهان فاکتورها/نماد/تطبیق پرتفوی؛ بازسازی شاخص‌های رسمی (K, EW) فقط بورس است


def base_panel(markets=("bourse",)):
    """markets=("bourse",): جهان شاخص‌های رسمی «كل»؛ ALL_MARKETS: همهٔ سهام بورس+فرابورس (وزن wt نسبت به همان جهان است)."""
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    panel = ew.load_panel()
    R = cw.classify_events(ew.daily_returns(panel, markets), sc)
    R["shares"] = cw.shares_timeline(R, sc, info)
    R = R.dropna(subset=["shares"]).copy()
    R["w"] = R.priceYesterday * R.shares
    R["wt"] = R.w / R.groupby("date").w.transform("sum")
    R["operating"] = ~R["name"].fillna("").str.contains(NONOP)
    return panel, info, R


def operating_view(Ra):
    """فقط شرکت‌های عملیاتی (بدون صندوق/گواهی/امتیاز…) برای فاکتورها، Lab و Plan؛ وزن‌های K/EW از bourse_view(Ra) (بدون فیلتر) می‌آید تا بازسازی رسمی دست نخورد."""
    return Ra[Ra.operating].copy()


def bourse_view(Ra):
    """زیرمجموعهٔ بورس از پانل همهٔ بازارها؛ وزن ارزش بازاری (wt) نسبت به جهان بورس بازنرمال می‌شود (بازسازی شاخص‌های رسمی «كل» فقط بورس است)."""
    R = Ra[Ra.market == "bourse"].copy()
    R["wt"] = R.w / R.groupby("date").w.transform("sum")
    return R


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
        yrs = (M.index[-1] - M.index[0]).days / 365.25
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
        yrs = (W.index[-1] - W.index[0]).days / 365.25
        cap[pol] = {"n": len(turns), "avg_turn_pct": r(np.mean(turns) * 100, 1), "annual_turn_pct": r(sum(turns) / yrs * 100, 1)}
    out["cap"] = cap
    return out


# ── Factor Lab: بک‌تست پنج‌گانه‌ها (مومنتوم ۱۲−۱، کم‌نوسان) ────────────────────────────
def factor(R, signal: str = "mom", qscore: "pd.DataFrame | None" = None):
    """signal: mom = مومنتوم ۱۲−۱ (پنجک ۵ = قوی‌ترین)، lowvol = نوسان ۲۵۲ روزه (پنجک ۵ = کم‌نوسان‌ترین)،
    quality = امتیاز کیفیت رهاورد (tools/build_quality.py؛ پنجک ۵ = باکیفیت‌ترین)؛ qscore: DataFrame[تاریخ ریبالانس × ins_code]."""
    M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M = M[M.index >= "2012-01-01"]
    dates = M.index
    jm = np.array([ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1] for d in dates])
    month_end = np.where(jm[1:] != jm[:-1])[0]            # آخرین روز هر ماه شمسی
    X = M.values
    lr = np.log1p(np.where(np.isnan(X), 0, X))
    cum = np.vstack([np.zeros(X.shape[1]), np.cumsum(lr, axis=0)])
    nz = np.vstack([np.zeros(X.shape[1]), np.cumsum((np.nan_to_num(X) != 0), axis=0)])
    x0 = np.where(np.isnan(X), 0, X)
    c1 = np.vstack([np.zeros(X.shape[1]), np.cumsum(x0, axis=0)])
    c2 = np.vstack([np.zeros(X.shape[1]), np.cumsum(x0 ** 2, axis=0)])
    have = np.vstack([np.zeros(X.shape[1]), np.cumsum(~np.isnan(X), axis=0)])
    V = np.nan_to_num(R.pivot_table(index="date", columns="ins_code", values="zTotTran", aggfunc="last").reindex(index=dates, columns=M.columns).values)
    mopen = (V > 0).sum(axis=1) >= 0.2 * np.maximum((~np.isnan(X)).sum(axis=1), 1)   # بازار باز (همان signals.Market.market_open)

    def last_open(a_):
        d_ = a_
        while d_ > 0 and not mopen[d_] and a_ - d_ < 90:
            d_ -= 1
        return d_

    def exec_day(a_):
        e_ = a_ + 1
        while e_ < len(dates) - 1 and not mopen[e_] and e_ - a_ < 90:
            e_ += 1
        return e_
    # سیگنال از ۲۰۱۵-۰۳ (پیش از آن ردیف‌های ۲۰۱۲–۲۰۱۴ هنوز تعدیل‌نشده‌های پراکنده دارند) ← ارزیابی از ۲۰۱۶-۰۳-۲۱
    start = int(np.searchsorted(dates, pd.Timestamp("2016-03-20")))
    port = {q: np.full(len(dates), np.nan) for q in ("Q1", "Q2", "Q3", "Q4", "Q5", "ALL")}
    names = {q: [] for q in port}
    holds = {}
    prev, tov = {}, {q: [] for q in port}
    mret, mret_end, mret_start = {q: [] for q in port}, [], []
    for a, b in zip(month_end[:-1], month_end[1:]):
        if a < 252 + 21 or a < start - 1:
            continue
        i1, i0 = (a + 1 - 21, a + 1 - 252) if signal in ("mom", "quality") else (a + 1, a + 1 - 252)   # mom: [t−252, t−21)؛ lowvol: [t−252, t)؛ quality: همان پنجرهٔ قیمتی برای واجدیت
        ok = ((have[i1] - have[i0]) >= 0.8 * (i1 - i0)) & ((nz[i1] - nz[i0]) >= 0.5 * (i1 - i0)) & ~np.isnan(X[a + 1])   # بدون شرط پایان دوره (فصل ۱۴ §۱۴٫۲٫۱)
        ok &= ~np.isnan(X[a]) & (V[last_open(a)] > 0) & (V[exec_day(a)] > 0)   # معامله در روز سیگنال و روز اجرا؛ تعطیلی سراسری ⇒ روز بازگشایی (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹، A2)
        if signal == "quality":
            if dates[a] not in qscore.index:
                continue
            score = qscore.loc[dates[a]].reindex(M.columns).values.astype(float)
            ok &= ~np.isnan(score)
        elif signal == "mom":
            score = cum[i1] - cum[i0]
        else:
            nn = np.maximum(have[i1] - have[i0], 1)
            mu = (c1[i1] - c1[i0]) / nn
            score = -np.sqrt(np.maximum((c2[i1] - c2[i0]) / nn - mu ** 2, 0))      # بالاتر = کم‌نوسان‌تر
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
            # گردش یک‌طرفهٔ واقعی: ½ Σ|وزن هدف − وزن رانش‌یافتهٔ دورهٔ قبل|
            w_new = np.zeros(X.shape[1]); w_new[g] = 1 / len(g)
            to = None
            if q in prev:
                w_old = prev[q]
                to = 0.5 * np.abs(w_new - w_old).sum()
            tov[q].append(to)
            grow = np.nanprod(1 + np.nan_to_num(seg), axis=0)
            wd = np.zeros(X.shape[1]); wd[g] = w_new[g] * grow
            prev[q] = wd / wd.sum() if wd.sum() > 0 else w_new
            mret[q].append(float(grow.mean() - 1))          # خرید و نگهداری در ماه (وزن‌ها رانش می‌کنند)
        mret_end.append(dates[min(b, len(dates) - 1)]); mret_start.append(dates[a + 1])
    S = pd.DataFrame(port, index=dates).dropna(how="all")
    S = S[S.index >= "2016-03-21"]
    res = {"ann": {}, "curve": {}}                 # آمار سالانه از سری ماهانه (پایین‌تر، ×۱۲/n) می‌آید؛ نسخهٔ روزانهٔ ÷۲۵۲ حذف شد (فصل ۷ §۷٫۳)
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
    res["signal"] = signal
    if signal == "quality":
        cnt = qscore.reindex(columns=M.columns).notna().sum(axis=1)
        cnt = cnt[cnt > 0]
        res["coverage"] = {"first": str(cnt.index[0].date()), "min": int(cnt.min()), "median": int(cnt.median()), "max": int(cnt.max())}
    # سری ماهانه (از ۱۳۹۵/۰۱) برای هزینه و آزمون آماری در UI
    keep = [i for i, d in enumerate(mret_start) if d >= pd.Timestamp("2016-03-20")]
    res["monthly"] = {"end": [str(mret_end[i].date()) for i in keep],
                      **{q: [round(mret[q][i] * 100, 4) for i in keep] for q in port},
                      "to": {q: [None if tov[q][i] is None else round(tov[q][i] * 100, 2) for i in keep] for q in port}}
    if keep:
        for q in port:
            res["monthly"]["to"][q][0] = None          # ساخت اولیه جزو گردش جاری نیست
    # خلاصه از سری ماهانهٔ خرید‌ونگهداری (همان که UI نشان می‌دهد؛ ناخالص از هزینه)
    Mq = {q: np.array([mret[q][i] for i in keep]) for q in port}
    n = len(keep)
    ann = lambda x: ((1 + x).prod() ** (12 / n) - 1) * 100
    res["ann"] = {q: r(ann(Mq[q]), 1) for q in port}
    res["vol_ann"] = {q: r(Mq[q].std(ddof=1) * np.sqrt(12) * 100, 1) for q in port}
    res["ls_ann_pct"] = r(ann(Mq["Q5"] - Mq["Q1"]), 1)
    res["q5_excess_ann_pct"] = r(res["ann"]["Q5"] - res["ann"]["ALL"], 1)
    res["q5_minus_all_te"] = r((Mq["Q5"] - Mq["ALL"]).std(ddof=1) * np.sqrt(12) * 100, 1)
    res["ls_vol_pct"] = r((Mq["Q5"] - Mq["Q1"]).std(ddof=1) * np.sqrt(12) * 100, 1)

    def nw_t(x, L=3):
        e = x - x.mean(); T = len(x)
        v = e @ e / T + 2 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T for l in range(1, L + 1))
        return r(x.mean() / np.sqrt(v / T), 2)
    res["t_nw_gross"] = {"Q5_ALL": nw_t(Mq["Q5"] - Mq["ALL"]), "Q5_Q1": nw_t(Mq["Q5"] - Mq["Q1"])}
    res["n_months"] = n
    return res


def factor_quality(R, info):
    """فاکتور کیفیت از صورت‌های مالی رهاورد؛ بدون data/fundamentals/rahavard_long.csv چیزی برنمی‌گرداند (UI حالت «دادهٔ بنیادی لازم است»)."""
    import build_quality as bq
    if not bq.available():
        print("factor_quality: دادهٔ رهاورد نیست؛ رد شد")
        return None
    M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
    M = M[M.index >= "2012-01-01"]
    dts = M.index
    jm = np.array([ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1] for d in dts])
    me = dts[np.where(jm[1:] != jm[:-1])[0]]
    sector = info.drop_duplicates("ins_code").set_index("ins_code").sector_name.astype(str).str.strip()
    S = bq.scores(me, M.columns, sector)
    print("quality coverage:", bq.coverage(S))
    if not S.notna().any().any():
        return None
    return factor(R, "quality", S)


# ── Risk ─────────────────────────────────────────────────────────────────
def risk(R, info):
    out = {}
    for k, code in (("K", "32097828799138957"), ("EW", ew.OFFICIAL["TR"])):
        r_ = ew.official(code)
        r_ = r_[r_.index >= "2014-03-20"]
        lvl = (1 + r_).cumprod()
        dd = lvl / lvl.cummax() - 1
        vol = r_.rolling(63).std() * np.sqrt(252) * 100
        trough = dd.idxmin()
        peak = lvl[:trough].idxmax()
        rec = lvl[trough:][lvl[trough:] >= lvl[peak]]
        idx = list(range(0, len(r_), 5)) + [len(r_) - 1]
        yrs = []
        for y, g in r_.groupby(r_.index.map(lambda d: ewr.g2j(d.year, d.month, d.day)[0])):
            gl = (1 + g).cumprod()
            yrs.append({"jy": int(y), "ret": r(((1 + g).prod() - 1) * 100, 1), "vol": r(g.std() * np.sqrt(252) * 100, 1),
                        "mdd": r((gl / gl.cummax() - 1).min() * 100, 1), "days": len(g)})
        out[k] = {"dates": [str(r_.index[i].date()) for i in idx], "dd": [r(dd.iloc[i] * 100, 2) for i in idx],
                  "vol": [r(vol.iloc[i], 2) for i in idx], "max_dd": r(dd.min() * 100, 1), "peak": str(peak.date()),
                  "trough": str(trough.date()), "recovered": str(rec.index[0].date()) if len(rec) else None,
                  "vol_all": r(r_.std() * np.sqrt(252) * 100, 1), "vol_1y": r(r_[-252:].std() * np.sqrt(252) * 100, 1),
                  "ann": r(((1 + r_).prod() ** (365.25 / (r_.index[-1] - r_.index[0]).days) - 1) * 100, 1), "yearly": yrs}
    # همبستگی ماهانهٔ ۱۲ صنعت بزرگ (بازسازی ارزش‌وزن)، از ۱۳۹۸
    Rs = R.merge(info[["ins_code", "sector_code", "sector_name"]], on="ins_code", how="left")
    Rs = Rs[Rs.date >= "2019-03-21"]
    last = Rs[Rs.date == Rs.date.max()].groupby("sector_name").w.sum().sort_values(ascending=False)
    top = list(last.head(12).index)
    Rs = Rs[Rs.sector_name.isin(top)]
    sec = (Rs.r_tr * Rs.w).groupby([Rs.date, Rs.sector_name]).sum() / Rs.groupby(["date", "sector_name"]).w.sum()
    sec = sec.unstack()
    jm = sec.index.map(lambda d: ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1])
    mon = (1 + sec.fillna(0)).groupby(jm).prod() - 1
    C = mon[top].corr()
    out["sector_corr"] = {"names": [str(n).strip() for n in top], "m": [[r(v, 2) for v in row] for row in C.values],
                          "months": int(len(mon)), "w": [r(last[n] / last.sum() * 100, 1) for n in top]}
    return out


# ── Fund (پرتفوی صندوق شاخصی) ─────────────────────────────────────────────
def fund(R, info):
    import gzip
    last = R.date.max()
    L = R[R.date == last][["ins_code", "symbol", "wt", "pClosing", "shares"]].copy()
    L = L.merge(info[["ins_code", "sector_name"]], on="ins_code", how="left")
    adv = {}
    for code in L.ins_code:
        f = ROOT / "data/prices" / f"{code}.csv.gz"
        try:
            d = pd.read_csv(f, usecols=["dEven", "qTotCap", "zTotTran"]).sort_values("dEven").tail(60)
        except Exception:  # noqa: BLE001
            continue
        adv[code] = (d.qTotCap.tail(20).mean(), d.qTotCap.mean(), float((d.zTotTran > 0).mean()), d.qTotCap.median())
    rows = []
    for x in L.sort_values("wt", ascending=False).itertuples():
        a20, a60, tf, med = adv.get(x.ins_code, (np.nan, np.nan, np.nan, np.nan))
        rows.append([x.symbol, (x.sector_name if isinstance(x.sector_name, str) else "").strip(), r(x.wt, 7), r(x.pClosing, 0), r(a20, 0), r(a60, 0), r(tf, 2), r(med, 0)])
    return {"asof": str(last.date()), "n": len(rows), "cols": ["sym", "sector", "w_k", "price", "adv20", "adv60", "traded_frac60", "med60"], "rows": rows}


# ── Data QA ──────────────────────────────────────────────────────────────
def qa(panel, info, R, Ra=None):
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
                         "stocks_bourse_in_returns": int(R.ins_code.nunique()),
                         **({"stocks_farabourse_in_returns": int(Ra[Ra.market == "farabourse"].ins_code.nunique()),
                             "stocks_all_in_returns": int(Ra.ins_code.nunique()),
                             "factor_universe_last": int(Ra[Ra.date == Ra.date.max()].ins_code.nunique())} if Ra is not None else {})},
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
    panel, info, Ra0 = base_panel(ALL_MARKETS)      # جهان فاکتورها: بورس + فرابورس (فقط شرکت‌های عملیاتی)
    R = bourse_view(Ra0)                             # جهان شاخص‌های رسمی «كل» (بدون فیلتر؛ بازسازی رسمی)
    Ra = operating_view(Ra0)
    Rb = bourse_view(Ra)                             # فاکتورهای «فقط بورس»
    data = {"built": datetime.now().strftime("%Y-%m-%d %H:%M"), "divlab": divlab(), "rebalance": rebalance(R),
            "factor": factor(Ra), "factor_lowvol": factor(Ra, "lowvol"), "risk": risk(R, info), "fund": fund(R, info),
            "factor_b": factor(Rb), "factor_lowvol_b": factor(Rb, "lowvol"),
            "qa": qa(panel, info, R, Ra), "reports": reports()}
    fq = factor_quality(Ra, info)
    if fq:
        data["factor_quality"] = fq
        data["factor_quality_b"] = factor_quality(Rb, info)
    OUT.write_text("window.SIM_EXTRA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} ({OUT.stat().st_size/1e3:.0f} KB)")
    print("factor:", json.dumps({k: v for k, v in data["factor"].items() if k not in ("curve", "yearly", "monthly")}, ensure_ascii=False))
    print("rebalance:", json.dumps({"policies": data["rebalance"]["policies"], "cap": data["rebalance"]["cap"]}, ensure_ascii=False)[:900])
    print("qa:", json.dumps({k: data["qa"][k] for k in ("universe", "rules", "sector_summary")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
