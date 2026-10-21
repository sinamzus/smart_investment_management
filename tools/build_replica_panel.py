#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ «همتاساز» (بازسازی شاخص با نمونهٔ کوچک، فیلتر نقدشوندگی، نقد/وام، گذشته) → ui/data/replica.js (window.SIM_REP) — فصل ۳ §۳٫۷.

    python tools/build_replica_panel.py            # ≈ ۱۰ تا ۲۰ دقیقه (بهینه‌سازی ماهانه)
    python tools/build_replica_panel.py --quick    # فقط N=30 و ۵۰ برای آزمون

طراحی: انتخاب سهام (روش × N × سطح نقدشوندگی) را در پایتون انجام می‌دهد و برای هر ترکیب
  • بازده روزانهٔ ناخالص پرتفوی بدون اهرم (ریبالانس ماهانه به وزن هدف، رانش وزن‌ها بین ریبالانس‌ها)،
  • گردش یک‌طرفهٔ هر ماه و بتای ۲۵۲ روزهٔ نمونه روی «شاخص كل» رسمی،
  • وزن‌های هر ماه و ظرفیت (AUM قابل ساخت در یک روز با مشارکت ۱۰٪)
را می‌نویسد. نقد/وام/اهرم/نرخ/هزینه/بازه در مرورگر دقیقاً روی همین سری‌ها اعمال می‌شود (خطی است:
NAV_t = L·nav₀·G_t − (L−1)·nav₀·A_t درون هر ماه)، پس اعداد قابل‌تنظیم‌اند و نیازی به اجرای دوبارهٔ پایتون نیست.
سطح نقدشوندگی فقط فهرست «نامزد نگهداری» را محدود می‌کند؛ وزن هدف b همیشه از کل واجدان بورس است.
  سطح ۰: بدون فیلتر · ۱: روزهای معامله ≥ ۵۰ از ۶۳ و میانهٔ ارزش معاملات ≥ صدک ۲۰ · ۲: ≥ ۵۶ و صدک ۴۰ · ۳: ≥ ۶۰ و صدک ۶۰.
"""
import argparse
import json
import sys
from base64 import b64encode
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import construction as cn  # noqa: E402
import sampled_replica as sr  # noqa: E402
import dividend_pay as dp  # noqa: E402
import new_listings as nl  # noqa: E402

NS = (10, 20, 30, 50, 80, 120)
METHODS = ("top", "strat", "opt")
LIQ = {0: (0, 0.0), 1: (50, 0.20), 2: (56, 0.40), 3: (60, 0.60)}          # (حداقل روز معامله از ۶۳، صدک ADV)
PART = 0.10                                                               # سقف مشارکت در ارزش معاملات روزانه
EPOCH = pd.Timestamp("1970-01-01")


# همتاساز: وزن هدف از همهٔ واجدان (ترکیب شاخص رسمی نماد متوقف را هم دارد)؛ اجرا با قاعدهٔ A2 (نخریدن/نفروختن نماد بی‌معامله در روز اجرا).
def f32(a):
    return b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()


def choose(method, N, b, idx, cand, sector, g):
    """-> (sel, w) ؛ g = Σ[:, idx] @ b[idx] (فقط برای opt)."""
    if len(cand) <= N:
        sel = cand
    elif method == "top":
        sel = cand[np.argsort(-b[cand])][:N]
    elif method == "strat":
        sec = pd.Series(sector[idx], index=idx)
        wsec = pd.Series(b[idx], index=idx).groupby(sec).sum().sort_values(ascending=False)
        quota = np.floor(wsec / wsec.sum() * N).astype(int)
        quota[quota.index[:max(1, N - int(quota.sum()))]] += 1
        cs = pd.Series(sector[cand], index=cand)
        sel = []
        for s, q in quota.items():
            if q > 0:
                m = cs[cs == s].index.values
                sel += list(m[np.argsort(-b[m])][:q])
        sel = np.array(sel[:N]) if sel else cand[np.argsort(-b[cand])][:N]
    else:
        return None
    sel = np.asarray(sel)
    return sel, b[sel] / b[sel].sum()


def solve_opt(sub, Sig, g):
    from cvxpy import Minimize, Problem, Variable, quad_form, psd_wrap
    if len(sub) <= 1:
        return np.ones(len(sub))
    P = Sig[np.ix_(sub, sub)]
    w = Variable(len(sub))
    Problem(Minimize(0.5 * quad_form(w, psd_wrap(P)) - g[sub] @ w), [w >= 0, w.sum() == 1]).solve(solver="CLARABEL")
    return np.maximum(np.asarray(w.value).ravel(), 0)


def opt_pick(N, b, cand, Sig, g):
    if len(cand) <= N:
        sel = cand
    else:
        pool = cand[np.argsort(-b[cand])][:3 * N]
        w0 = solve_opt(pool, Sig, g)
        sel = pool[np.argsort(-w0)][:N]
    w1 = solve_opt(sel, Sig, g)
    w1 = w1 / w1.sum()
    keep = w1 > 1e-6
    return sel[keep], w1[keep] / w1[keep].sum()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    ns = (30, 50) if a.quick else NS
    mk, K = sr.load()
    K = K.fillna(0)
    n, k = mk.n, mk.k
    X = np.nan_to_num(mk.X)
    Y = np.nan_to_num(mk.Y)                                                 # بازده سود نقدی روز استحقاق
    pays = dp.pay_days(mk)                                                  # روز پرداخت واقعی هر سود (فصل ۳ §۳٫۵)
    print("سود نقدی:", dp.lag_summary(mk, pays))
    mc = np.nan_to_num(mk.mcap)
    ok_all = np.isin(mk.market, ["bourse"])
    val = pd.DataFrame(mk.val)
    adv = val.rolling(63, min_periods=30).median().values
    td = (val.fillna(0) > 0).astype(float).rolling(63, min_periods=30).sum().values
    me = [int(x) for x in mk.month_end if mk.dates[x] >= sr.START and x >= 252 and x + 1 < n]
    ends = me[1:] + [n - 1]
    live_a = n - 1
    days0 = me[0] + 1
    dates = mk.dates[days0:]
    # همتای کامل (هدف): واجدان عادی ∪ نمادهای تازه از روز پس از نخستین معامله (new_listings، همان sampled_replica)
    first = nl.first_trade(mk)
    Cfull = np.zeros(n)
    for t in range(1, n):
        i, w_ = nl.full_target(mk, t, ok_all, first)
        if len(i):
            Cfull[t] = float(w_ @ X[t, i])
    # لایهٔ عرضهٔ اولیه: نماد تازهٔ بزرگ با وزن شاخص بیرون از انتخاب؛ مرورگر خرید روزانه (φ × ارزش معاملات ÷ اندازهٔ صندوق) را حساب می‌کند
    EV = nl.events(mk, ok_all, me[0])
    WIPO = nl.weights(mk, EV, ok_all, first)
    VAL = np.nan_to_num(mk.val)
    print(f"لایهٔ عرضهٔ اولیه: {len(EV)} نماد تازهٔ بزرگ")
    keys = [(m, N, q) for q in LIQ for N in ns for m in METHODS]
    W = {key: [] for key in keys}                                          # ماه به ماه: (sel, w)
    LIVE = {}
    B_month, nelig, sigdate = [], [], []

    def month(aidx, store, record):
        idx = np.where(mk.eligible(aidx, require_trade=False) & ok_all & (mc[aidx] > 0))[0]
        b = np.zeros(k)
        b[idx] = mc[aidx, idx] / mc[aidx, idx].sum()
        Sig = g = None
        Sig_needed = any(m == "opt" for m, _, _ in keys)
        if Sig_needed:
            S = sr.lw_cov(mk.X[aidx - 251: aidx + 1][:, idx])
            Sig = np.zeros((k, k))
            Sig[np.ix_(idx, idx)] = S
            g = Sig[:, idx] @ b[idx]
        cands = {}
        for q, (dmin, pct) in LIQ.items():
            c = idx
            if q > 0:
                thr = np.nanpercentile(adv[aidx, idx], pct * 100)
                c = idx[(td[aidx, idx] >= dmin) & (adv[aidx, idx] >= thr)]
            cands[q] = c
        for key in keys:
            m, N, q = key
            cand = cands[q] if len(cands[q]) >= 3 else idx
            if m == "opt":
                sel, w = opt_pick(N, b, cand, Sig, g)
            else:
                sel, w = choose(m, N, b, idx, cand, mk.sector, g)
            store[key] = (sel, w, adv[aidx, sel])
        if record:
            B_month.append((idx, b[idx])); nelig.append(len(idx)); sigdate.append(int((mk.dates[aidx] - EPOCH).days))

    for j, aidx in enumerate(me):
        st = {}
        month(aidx, st, True)
        for key in keys:
            W[key].append(st[key])
        print(f"ماه {j + 1}/{len(me)} {mk.dates[aidx].date()}", flush=True) if j % 10 == 0 else None
    st = {}
    month(live_a, st, False)
    LIVE = st
    # شبیه‌سازی روزانهٔ ناخالص هر ترکیب
    cfg = {}
    for key in keys:
        r = np.zeros(len(dates)); to, beta, cap = [], [], []
        dv = {}                                                             # (روز استحقاق، روز پرداخت) ⇒ سهم سود از ارزش دیروز سبد
        w_prev = np.zeros(k)
        for j, aidx in enumerate(me):
            sel, w, ad = W[key][j]
            cap_t = float(np.min(PART * np.nan_to_num(ad) / np.maximum(w, 1e-9))) if len(sel) else 0.0   # ظرفیت ساخت هدف از نقد (پیش از انجماد)
            wf = np.zeros(k); wf[sel] = w
            # قاعدهٔ A2 (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹؛ همان tools/sampled_replica.py): نماد جدیدِ بی‌معامله در روز اجرا خریده نمی‌شود و
            # نماد نگه‌داشتهٔ بی‌معامله با وزن رانش‌یافته می‌ماند. وزن نسبی سهام مستقل از اهرم/نقد است، پس مرورگر همین وزن را بازپخش می‌کند.
            tr = mk.tradable(aidx)
            wf[~tr & (w_prev <= 0)] = 0.0
            if wf.sum() > 0:
                wf = wf / wf.sum()
            wf = cn.freeze_untradable(wf, w_prev, tr)
            sel = np.where(wf > 0)[0]; w = wf[sel]; ad = adv[aidx, sel]
            W[key][j] = (sel, w, ad)
            to.append(0.5 * float(np.abs(wf - w_prev).sum()))
            rs = X[aidx - 251: aidx + 1] @ wf
            ri = np.nan_to_num(K.values[aidx - 251: aidx + 1])
            beta.append(float(np.cov(rs, ri)[0, 1] / max(np.var(ri, ddof=1), 1e-12)))
            cap.append(cap_t)
            wv = wf.copy()
            for t in range(aidx + 1, ends[j] + 1):
                v0 = wv.sum()
                for i in np.nonzero((Y[t] > 0) & (wv > 0))[0]:
                    kk = (t - days0, pays.get((t, int(i)), n) - days0)
                    dv[kk] = dv.get(kk, 0.0) + float(wv[i] * Y[t, i] / v0)
                wv = wv * (1 + X[t])
                r[t - days0] = wv.sum() / v0 - 1
            w_prev = wv / wv.sum()
        dvk = sorted(dv)
        cfg["|".join(map(str, key))] = {"r": f32(r), "dv": [[a_ for a_, _ in dvk], [b_ for _, b_ in dvk], f32([dv[x] for x in dvk])], "to": [round(x, 4) for x in to], "beta": [round(x, 3) for x in beta], "cap": [round(x / 1e9, 2) for x in cap],
                                       "sel": [[[int(i) for i in s], [int(round(x * 1e5)) for x in w]] for s, w, _ in W[key]],
                                       "live": [[int(i) for i in LIVE[key][0]], [int(round(x * 1e5)) for x in LIVE[key][1]], round(float(np.min(PART * np.nan_to_num(LIVE[key][2]) / np.maximum(LIVE[key][1], 1e-9))) / 1e9, 2)]}
    el_live = mk.eligible(live_a, require_trade=False) & ok_all & (mc[live_a] > 0)
    idx_live = np.where(el_live | (ok_all & (first >= 0) & (first < live_a) & (mc[live_a] > 0)))[0]   # هدف زنده با نمادهای تازه
    ev_live = [e for e in EV if e["s"] <= live_a and e["end"] > live_a]
    used = sorted({int(i) for i in idx_live} | {e["i"] for e in EV} | {int(i) for key in keys for s, _, _ in W[key] for i in s} | {int(i) for key in keys for i in LIVE[key][0]} | {int(i) for idx, _ in B_month for i in idx})
    pos = {i: p for p, i in enumerate(used)}
    names = [{"c": str(mk.cols[i]), "s": str(mk.sym[i]), "sec": str(mk.sector[i])} for i in used]
    # شاخص وزن هدف: برای هر ماه فقط نمادهای واجد (ایندکس فشرده)
    for key, c in cfg.items():
        c["sel"] = [[[pos[i] for i in s], w] for s, w in c["sel"]]
        c["live"][0] = [pos[i] for i in c["live"][0]]
    # وزن هدف زنده
    idx = idx_live
    bl = mc[live_a, idx] / mc[live_a, idx].sum()
    # رویدادهای لایهٔ عرضهٔ اولیه برای مرورگر (روزها نسبی به days0؛ پنجره تا end + HOLD یا پایان داده)
    def evx(e):
        a0, a1 = max(e["s"], days0), min(e["end"] + nl.HOLD, n)
        jr = next((j for j, a_ in enumerate(me) if a_ >= e["end"]), len(me))
        return {"p": pos[e["i"]], "s": e["s"] - days0, "a": a0 - days0, "end": e["end"] - days0, "j": jr,
                "r": f32(X[a0:a1, e["i"]]), "w": f32(WIPO[e["i"]][a0:a1]), "v": f32(VAL[a0:a1, e["i"]] / 1e9)}
    ipo = {"thresh": nl.THRESH, "phi": nl.PHI, "aum": nl.AUM_BN, "hold": nl.HOLD, "ev": [evx(e) for e in EV if min(e["end"] + nl.HOLD, n) > days0],
           "live": [[pos[e["i"]], round(float(mc[live_a, e["i"]] / mc[live_a, idx_live].sum()), 5)] for e in ev_live]}
    # ADV آخرین روز برای نمایش
    advl = {pos[i]: round(float(adv[live_a, i]) / 1e9, 3) for i in idx if i in pos}
    out = {"built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "asof": str(mk.dates[live_a].date()), "start": str(dates[0].date()),
           "dates": [int((d - EPOCH).days) for d in dates], "K": f32(K.values[days0:]), "C": f32(Cfull[days0:]),
           "sig": sigdate, "mstart": [int(a_ + 1 - days0) for a_ in me], "n_elig": nelig,
           "b": [[[pos[i] for i in idx_], [int(round(x * 1e5)) for x in b_]] for idx_, b_ in B_month],
           "live_b": [[pos[i] for i in idx], [int(round(x * 1e5)) for x in bl]], "adv_live": advl,
           "names": names, "Ns": list(ns), "methods": list(METHODS), "liq": {str(q): {"min_days": v[0], "adv_pct": v[1]} for q, v in LIQ.items()},
           "part": PART, "configs": cfg, "ipo": ipo}
    path = ROOT / "ui" / "data" / "replica.js"
    path.write_text("window.SIM_REP = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {path} ({path.stat().st_size / 1e6:.1f} MB)؛ {len(cfg)} ترکیب، {len(me)} ماه، {len(used)} نماد")


if __name__ == "__main__":
    main()
