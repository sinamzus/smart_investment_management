#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی «شاخص كل» (ارزش‌وزن، بازده کل) با N سهم، با اهرم/وام اختیاری — فصل ۳ §۳٫۷.

    python tools/sampled_replica.py                         # جدول N × روش انتخاب × اهرم
    python tools/sampled_replica.py --rate 0.30 --cost 125  # نرخ وام سالانه و هزینهٔ رفت‌وبرگشت (bp)

مراحل (هر پایان ماه جلالی، اجرا با بازده از روز بعد):
  ۱ وزن هدف b = ارزش بازار نمادهای واجد بورس ÷ مجموع (همان روش وزن «شاخص كل» رسمی: ارزش بازار کل، نه شناور آزاد).
  ۲ انتخاب N سهم: top (N بزرگ‌ترین)، strat (طبقه‌ای: سهم هر صنعت از N ∝ وزنش؛ در هر صنعت بزرگ‌ترین‌ها)،
    opt (بهینه‌سازی: min (w−b)ᵀΣ(w−b) روی ۳N بزرگ‌ترین، فقط‌خرید؛ سپس N وزن برتر و حل دوباره؛ Σ = Ledoit–Wolf روی ۲۵۲ روز).
  ۳ اهرم L: ۱ (بدون وام) یا «تراز بتا» L = ۱/β (β رگرسیون ۲۵۲ روزهٔ نمونه روی شاخص هدف، بُرش [۰٫۷، ۱٫۵]).
    L > ۱: وام (L−۱)×NAV با نرخ rb؛ L < ۱: بخش نقد بدون بهره. وام و L هر ماه بازتنظیم می‌شود.
  ۴ هزینه: گردش یک‌طرفه × هزینهٔ رفت‌وبرگشت؛ بهرهٔ وام روزانه از NAV کم می‌شود.
  ۵ ارزیابی روی بازده روزانه در برابر «شاخص كل» رسمی (بازده کل) و در برابر همتای ارزش‌وزن کامل خودمان
    (دومی فقط خطای نمونه‌گیری را نشان می‌دهد؛ اولی خطای تفاوت اعضا (شرط واجدیت ۲۵۲ روزه، ماهانه) و داده را هم دارد).
محدودیت: بدون صف/حد نوسان/توقف؛ نرخ وام و دسترسی به وام (مارجین) واقعی نیست **[تأیید لازم]**.
"""
import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore")
import build_ui_extra as bx  # noqa: E402
import investable_replica as ir  # noqa: E402
import construction as cn  # noqa: E402
import signals as sg  # noqa: E402

NS = (10, 20, 30, 50, 80, 120)
METHODS = ("top", "strat", "opt")
START = pd.Timestamp("2018-03-21")


def load():
    _, info, Ra = bx.base_panel(("bourse",))
    Ra = bx.operating_view(Ra)
    # پانل تا آخرین روزی که سری رسمی «شاخص كل» داده دارد بریده می‌شود (۲۰۲۶-۱۰-۲۰): پیش‌تر روزهای پس از آخرین دادهٔ رسمی با بازده
    # شاخص صفر پر می‌شد و همتا در روزهای آخر ناگهان از شاخص فاصله می‌گرفت (مثلاً ۲۶ و ۲۷ مهر ۱۴۰۵: شاخص ۰، سهام −۳٪).
    K0 = ir.load_pair("K").tr
    last = K0.last_valid_index()
    if Ra.date.max() > last:
        print(f"هشدار: سری رسمی «شاخص كل» تا {last.date()} است ولی قیمت‌ها تا {Ra.date.max().date()}؛ پانل همتا تا {last.date()} بریده شد "
              f"(python tools/fetch_official_indices.py --fetch)")
        Ra = Ra[Ra.date <= last]
    mk = sg.Market(Ra, info)
    K = K0.reindex(mk.dates)
    return mk, K


def lw_cov(R):
    from sklearn.covariance import LedoitWolf
    R = np.nan_to_num(R)
    return LedoitWolf().fit(R).covariance_


def pick_top(b, idx, N):
    o = idx[np.argsort(-b[idx])]
    return o[:N]


def pick_strat(b, idx, N, sector):
    sec = pd.Series(sector[idx], index=idx)
    wsec = pd.Series(b[idx], index=idx).groupby(sec).sum().sort_values(ascending=False)
    quota = np.floor(wsec / wsec.sum() * N).astype(int)
    quota[quota.index[:max(1, N - int(quota.sum()))]] += 1             # باقی‌ماندهٔ صندلی‌ها به صنعت‌های بزرگ
    quota = quota.clip(lower=0)
    sel = []
    for s, q in quota.items():
        if q <= 0:
            continue
        members = sec[sec == s].index.values
        sel += list(members[np.argsort(-b[members])][:q])
    return np.array(sel[:N])


def pick_opt(b, idx, N, Sig, pos):
    from cvxpy import Minimize, Problem, Variable, quad_form, psd_wrap
    pool = pick_top(b, idx, 3 * N)

    def solve(sub):
        P = Sig[np.ix_([pos[i] for i in sub], [pos[i] for i in sub])]
        q = -Sig[np.ix_([pos[i] for i in sub], [pos[i] for i in idx])] @ b[idx]
        w = Variable(len(sub))
        Problem(Minimize(0.5 * quad_form(w, psd_wrap(P)) + q @ w), [w >= 0, w.sum() == 1]).solve(solver="CLARABEL")
        return np.maximum(np.asarray(w.value).ravel(), 0)
    w0 = solve(pool)
    sel = pool[np.argsort(-w0)][:N]
    w1 = solve(sel)
    return sel, w1


def run(mk, K, rate, cost_bp, N, method, lev_mode):
    n, k = mk.n, mk.k
    me = [int(a) for a in mk.month_end if mk.dates[a] >= START and a >= 252 and a + 1 < n]
    me.append(None)
    ok_all = np.isin(mk.market, ["bourse"])
    nav, V, D, cash = 1.0, 1.0, 0.0, 0.0
    w_prev = np.zeros(k)
    navs, dates, turn, lev_l = [], [], [], []
    X = np.nan_to_num(mk.X)
    for j, a in enumerate(me[:-1]):
        b_end = me[j + 1] if me[j + 1] is not None else n - 1
        # وزن هدف و انتخاب از همهٔ واجدان (ترکیب شاخص رسمی نماد متوقف را هم دارد)؛ اجرا فقط در نمادهای معامله‌شدهٔ روز اجرا:
        # نماد جدیدِ بی‌معامله خریده نمی‌شود و نماد نگه‌داشتهٔ بی‌معامله با وزن رانش‌یافته می‌ماند (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹، A2)
        idx = np.where(mk.eligible(a, require_trade=False) & ok_all & (np.nan_to_num(mk.mcap[a]) > 0))[0]
        tr = mk.tradable(a)
        if len(idx) < N + 5:
            continue
        b = np.zeros(k)
        mc = np.nan_to_num(mk.mcap[a])
        b[idx] = mc[idx] / mc[idx].sum()
        pos = {i: p for p, i in enumerate(idx)}
        Sig = None
        if method == "opt":
            Sig = lw_cov(mk.X[a - 251: a + 1][:, idx])
            Sfull = np.zeros((k, k))
            Sfull[np.ix_(idx, idx)] = Sig
            pos = {i: i for i in idx}
            sel, wsel = pick_opt(b, idx, N, Sfull, pos)
            w = np.zeros(k)
            w[sel] = wsel
        elif method == "strat":
            sel = pick_strat(b, idx, N, mk.sector)
            w = np.zeros(k); w[sel] = b[sel] / b[sel].sum()
        else:
            sel = pick_top(b, idx, N)
            w = np.zeros(k); w[sel] = b[sel] / b[sel].sum()
        w[~tr & (w_prev <= 0)] = 0.0                                    # نماد جدید بی‌معامله خریدنی نیست
        if w.sum() > 0:
            w = w / w.sum()
        w = cn.freeze_untradable(w, w_prev, tr)
        L = 1.0
        if lev_mode == "beta":
            rs = X[a - 251: a + 1] @ w
            ri = np.nan_to_num(K.values[a - 251: a + 1])
            beta = np.cov(rs, ri)[0, 1] / max(np.var(ri, ddof=1), 1e-12)
            L = float(np.clip(1.0 / beta if beta > 0 else 1.0, 0.7, 1.5))
        # ریبالانس: NAV فعلی، سرمایه‌گذاری L×NAV، بدهی (L−1)×NAV (یا نقد بدون بهره)
        nav = V + cash - D
        drift_w = w_prev
        to = 0.5 * np.abs(w - drift_w).sum() * (L if nav > 0 else 1.0)
        nav -= to * nav * cost_bp / 1e4
        V, D = L * nav, max(L - 1.0, 0.0) * nav
        cash = nav - V if L < 1.0 else 0.0                             # L<1: بقیه نقد بدون بهره
        turn.append(to); lev_l.append(L)
        wv = w * V                                                      # ارزش هر سهم
        prev_d = mk.dates[a]
        for t in range(a + 1, b_end + 1):
            days = (mk.dates[t] - prev_d).days; prev_d = mk.dates[t]
            wv = wv * (1 + X[t])
            D *= 1 + rate * days / 365.0
            V = wv.sum()
            navs.append(V + cash - D); dates.append(mk.dates[t])
        w_prev = wv / wv.sum() if wv.sum() > 0 else w_prev
    s = pd.Series(navs, index=pd.DatetimeIndex(dates))
    return s, np.mean(turn), np.mean(lev_l)


def evaluate(s, K, Cfull):
    r = s.pct_change().dropna()
    k = K.reindex(r.index).fillna(0)
    c = Cfull.reindex(r.index).fillna(0)
    te = float((r - k).std(ddof=1) * np.sqrt(252) * 100)
    te_c = float((r - c).std(ddof=1) * np.sqrt(252) * 100)
    beta = float(np.cov(r, k)[0, 1] / np.var(k, ddof=1))
    corr = float(np.corrcoef(r, k)[0, 1])
    yrs = (s.index[-1] - s.index[0]).days / 365.25            # سال تقویمی (فصل ۷ §۷٫۳)؛ نه ۲۵۲ روز معاملاتی
    ann = (s.iloc[-1] / s.iloc[0]) ** (1 / yrs) - 1
    annk = ((1 + k).prod()) ** (1 / yrs) - 1
    return {"ann_pct": 100 * ann, "ann_index_pct": 100 * annk, "gap_pct": 100 * (ann - annk), "te_vs_official_pct": te, "te_vs_fullreplica_pct": te_c, "beta": beta, "corr": corr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=0.30, help="نرخ وام سالانه")
    ap.add_argument("--cost", type=float, default=125.0, help="هزینهٔ رفت‌وبرگشت (bp؛ پیش‌فرض همهٔ برنامه ۱۲۵)")
    ap.add_argument("--ns", type=str, default=",".join(map(str, NS)))
    a = ap.parse_args()
    mk, K = load()
    K = K.fillna(0)
    ok = np.isin(mk.market, ["bourse"])
    # همتای ارزش‌وزن کامل (همهٔ واجدان) برای جدا کردن خطای نمونه‌گیری
    Cfull = pd.Series(0.0, index=mk.dates)
    X = np.nan_to_num(mk.X)
    mc = np.nan_to_num(mk.mcap)
    rows = []
    # همتای کامل: وزن ارزش بازار روز قبل (ریبالانس روزانه) — تقریب کران پایین خطای وزن
    for t in range(1, mk.n):
        idx = np.where(mk.eligible(t - 1, require_trade=False) & ok & (mc[t - 1] > 0))[0]
        if len(idx):
            w = mc[t - 1, idx] / mc[t - 1, idx].sum()
            Cfull.iloc[t] = float(w @ X[t, idx])
    base = evaluate(pd.Series((1 + Cfull[Cfull.index >= START]).cumprod()), K, Cfull)
    print(f"همتای کامل (وزن بازار، ریبالانس روزانه) در برابر شاخص كل رسمی: TE = {base['te_vs_official_pct']:.2f}٪؛ تفاوت بازده سالانه {base['gap_pct']:+.2f}٪؛ همبستگی {base['corr']:.4f}\n")
    import json
    json.dump({"rate": a.rate, "cost_bp": a.cost, "from": str(START.date()), "to": str(mk.dates[-1].date()), "n_eligible_last": int((mk.eligible(mk.n - 1, require_trade=False) & ok).sum()),
               "full_replica": {k: float(v) for k, v in base.items()}}, open(ROOT / "data" / "research" / "sampled_replica_meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for N in [int(x) for x in a.ns.split(",")]:
        for m in METHODS:
            for lev in ("none", "beta"):
                try:
                    s, to, L = run(mk, K, a.rate, a.cost, N, m, lev)
                except Exception as e:  # noqa: BLE001
                    print("خطا", N, m, lev, type(e).__name__, e); continue
                ev = evaluate(s, K, Cfull)
                rows.append({"N": N, "method": m, "leverage": lev, "mean_L": L, "turnover_oneway_pct": 100 * to, **ev})
                print(f"N={N:3d} {m:5s} L={'1' if lev == 'none' else 'β'} (L̄={L:.2f}) بازده {ev['ann_pct']:6.1f}٪ شاخص {ev['ann_index_pct']:6.1f}٪ فاصله {ev['gap_pct']:+6.1f} TE_رسمی {ev['te_vs_official_pct']:5.2f} TE_همتا {ev['te_vs_fullreplica_pct']:5.2f} β={ev['beta']:.2f} ρ={ev['corr']:.3f} گردش {100 * to:4.0f}٪", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data" / "research" / "sampled_replica.csv", index=False, encoding="utf-8-sig")
    print("\nذخیره شد: data/research/sampled_replica.csv")


if __name__ == "__main__":
    main()
