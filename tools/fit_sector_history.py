#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""برازش تاریخچهٔ عضویت صنعتی: سهامی که در گذشته در صنعت دیگری بوده‌اند.

    python tools/fit_sector_history.py            # گزارش
    python tools/fit_sector_history.py --save     # data/derived/sector_history_adjustments.csv

`instrument_info.sector_code` فقط صنعت «فعلی» است؛ شرکتی که صنعتش عوض شده (مثل «ونیکی»: ۵۶ ← ۳۹) در شاخص
صنعت رسمی گذشته جای دیگری بوده. برای هر شاخص صنعت با خطای بزرگ:
  ۱. نامزدها = سهامی که بازده‌شان با باقیماندهٔ (رسمی − من) همبستگی بالا دارد (افزودن) + اعضای فعلی (حذف دوره‌ای)؛
  ۲. برای هر نامزد بهترین بازهٔ [from, to) با مرزهای سال شمسی (۱ فروردین) که TE را کم کند؛
  ۳. حریصانه تا وقتی TE دست‌کم ۱۰٪ نسبی بهتر می‌شود.
نتیجه فقط تشخیصی/اصلاح تحلیل صنعت است و روی «شاخص كل» و هم‌وزن اثری ندارد.
"""
import argparse
import itertools

import numpy as np
import pandas as pd

import check_sector_indices as cs
import rebuild_cw_index as cw
import rebuild_ew_index as ew

ROOT = ew.ROOT
BOUNDS = [pd.Timestamp(f"{y}-03-21") for y in range(2014, 2027)]


def build_R():
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    R = cw.classify_events(ew.daily_returns(ew.load_panel()), sc)
    R["shares"] = cw.shares_timeline(R, sc, info)
    R = R.dropna(subset=["shares"]).merge(info[["ins_code", "symbol", "sector_code"]].rename(columns={"symbol": "sym"}), on="ins_code", how="left")
    R["sec"] = R.sector_code.astype(str).str.strip().str.lstrip("0")
    R["w"] = R.priceYesterday * R.shares
    return R


def te(S, off):
    if S.empty:
        return np.inf
    x = (S.r_tr * S.w).groupby(S.date).sum() / S.groupby("date").w.sum()
    j = pd.concat([x, off], axis=1, join="inner").dropna()
    j.columns = ["m", "o"]
    j = j[j.index >= "2014-03-20"]
    return (j.m - j.o).std() * np.sqrt(252) * 100 if len(j) > 200 else np.inf


def fit_sector(R, sec, code, max_iter=3, min_gain=0.25, n_cand=12):
    off = ew.official(code)
    base = R[R.sec == sec.lstrip("0")]
    others = R[R.sec != sec.lstrip("0")]
    cur = te(base, off)
    start = cur
    adds = []          # (sym, from, to, mode)
    for _ in range(max_iter):
        S = base
        for sym, a, b, mode in adds:
            C = R[(R.sym == sym) & (R.date >= a) & (R.date < b)]
            S = pd.concat([S[~((S.sym == sym) & (S.date >= a) & (S.date < b))], C]) if mode == "in" else S[~((S.sym == sym) & (S.date >= a) & (S.date < b))]
        x = (S.r_tr * S.w).groupby(S.date).sum() / S.groupby("date").w.sum()
        res = (off - x).dropna()
        res = res[res.index >= "2014-03-20"]
        Xo = others.pivot_table(index="date", columns="sym", values="r_tr").reindex(res.index)
        cand = {}
        for sym in Xo.columns:
            v = Xo[sym]
            ok = v.notna() & (v.abs() > 0)
            if ok.sum() >= 150 and v[ok].std() > 0:
                cand[sym] = res[ok].corr(v[ok])
        cand = pd.Series(cand).dropna().sort_values(ascending=False).head(n_cand).index.tolist()
        # نامزد حذف: اعضای فعلی که بازده‌شان با باقیماندهٔ (رسمی − من) همبستگی منفی دارد (در گذشته عضو نبوده‌اند)
        Xi = S.pivot_table(index="date", columns="sym", values="r_tr").reindex(res.index)
        neg = {}
        for sym in Xi.columns:
            v = Xi[sym]
            ok = v.notna() & (v.abs() > 0)
            if ok.sum() >= 150 and v[ok].std() > 0:
                neg[sym] = res[ok].corr(v[ok])
        neg = pd.Series(neg).dropna().sort_values().head(n_cand // 2).index.tolist()
        grid = list(itertools.combinations([pd.Timestamp("2000-01-01")] + BOUNDS + [pd.Timestamp("2100-01-01")], 2))
        best = None
        for sym in cand:
            C = others[others.sym == sym]
            for a, b in grid:
                t = te(pd.concat([S, C[(C.date >= a) & (C.date < b)]]), off)
                if best is None or t < best[0]:
                    best = (t, sym, a, b, "in")
        for sym in neg:
            for a, b in grid:
                t = te(S[~((S.sym == sym) & (S.date >= a) & (S.date < b))], off)
                if t < best[0]:
                    best = (t, sym, a, b, "out")
        if best is None or best[0] > cur * (1 - min_gain):
            break
        cur = best[0]
        adds.append((best[1], best[2], best[3], best[4]))
    return start, cur, adds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--min-te", type=float, default=1.5, help="فقط صنایعی که TE اولیه‌شان بیشتر از این است")
    ap.add_argument("--only", help="کد صنعت، مثلاً 56,34")
    a = ap.parse_args()
    R = build_R()
    only = set(a.only.split(",")) if a.only else None
    rows = []
    for code, sec in cs.SECTORS.items():
        if only and sec not in only:
            continue
        if not (ROOT / f"data/indices/index_{code}.csv").exists():
            continue
        off = ew.official(code)
        t0 = te(R[R.sec == sec.lstrip("0")], off)
        if not np.isfinite(t0) or (t0 < a.min_te and not only):
            continue
        start, end, adds = fit_sector(R, sec, code)
        print(f"صنعت {sec}: TE {start:.2f}% ← {end:.2f}%  ", [(s, m, str(x.date()), str(y.date())) for s, x, y, m in adds])
        for s, x, y, m in adds:
            rows.append((sec, s, x.date(), y.date(), m, round(start, 3), round(end, 3)))
    if a.save and rows:
        out = ROOT / "data/derived/sector_history_adjustments.csv"
        pd.DataFrame(rows, columns=["sector", "symbol", "from", "to", "mode", "te_before", "te_after"]).to_csv(out, index=False)
        print("ذخیره شد:", out)


if __name__ == "__main__":
    main()
