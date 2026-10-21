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
import ew_target as et  # noqa: E402

NS = (10, 20, 30, 50, 80, 120)
METHODS = ("top", "strat", "opt")
LIQ = {0: (0, 0.0), 1: (50, 0.20), 2: (56, 0.40), 3: (60, 0.60)}          # (حداقل روز معامله از ۶۳، صدک ADV)
PART = 0.10                                                               # سقف مشارکت در ارزش معاملات روزانه
EPOCH = pd.Timestamp("1970-01-01")


# همتاساز: وزن هدف از همهٔ واجدان (ترکیب شاخص رسمی نماد متوقف را هم دارد)؛ اجرا با قاعدهٔ A2 (نخریدن/نفروختن نماد بی‌معامله در روز اجرا).
def f32(a):
    return b64encode(np.asarray(a, dtype="<f4").tobytes()).decode()


def choose(method, N, b, idx, cand, sector, g, rk=None):
    """-> (sel, w) ؛ g = Σ[:, idx] @ b[idx] (فقط برای opt)؛ rk رتبه (پیش‌فرض b؛ هدف هم‌وزن: ارزش معاملات)."""
    rk = b if rk is None else rk
    if len(cand) <= N:
        sel = cand
    elif method == "top":
        sel = cand[np.argsort(-rk[cand])][:N]
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
                sel += list(m[np.argsort(-rk[m])][:q])
        sel = np.array(sel[:N]) if sel else cand[np.argsort(-rk[cand])][:N]
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


def opt_pick(N, b, cand, Sig, g, rk=None):
    rk = b if rk is None else rk
    if len(cand) <= N:
        sel = cand
    else:
        pool = cand[np.argsort(-rk[cand])][:3 * N]
        w0 = solve_opt(pool, Sig, g)
        sel = pool[np.argsort(-w0)][:N]
    w1 = solve_opt(sel, Sig, g)
    w1 = w1 / w1.sum()
    keep = w1 > 1e-6
    return sel[keep], w1[keep] / w1[keep].sum()


def context(mk, K, target, keep):
    """ورودی‌های مشترک ساخت هدف و شبیه‌سازی؛ keep = روزهایی که وزن هدف هم‌وزن آن‌ها لازم است (روزهای بررسی + روز زنده)."""
    from types import SimpleNamespace
    EWT = target == "ew"
    ok_all = np.isin(mk.market, ["bourse"])
    adv, td = cn.liq_windows(mk, ok_all)                         # پنجرهٔ ۶۳ روز باز بازار (تعطیلی سراسری شمرده نمی‌شود)
    cx = SimpleNamespace(mk=mk, K=K, EWT=EWT, n=mk.n, k=mk.k, X=np.nan_to_num(mk.X), Y=np.nan_to_num(mk.Y), mc=np.nan_to_num(mk.mcap),
                         ok_all=ok_all, adv=adv, td=td, Cfull=None, BEW=None)
    if EWT:                                                     # هدف هم‌وزن: همتای کامل و وزن هدف روزها از ew_target (هم‌وزن فصلی همهٔ بورس)
        cx.Cfull, cx.BEW = et.ew_path(mk, cx.ok_all, list(keep))
    return cx


def targets_at(cx, aidx, keys):
    """وزن هدف و انتخاب همهٔ ترکیب‌ها با دادهٔ پایان روز aidx (اجرا از روز بعد) -> ({key: (sel, w, adv)}، idx، b)."""
    mk, k, adv, td = cx.mk, cx.k, cx.adv, cx.td
    idx = np.where(mk.eligible(aidx, require_trade=False) & cx.ok_all & (cx.mc[aidx] > 0))[0]
    b = np.zeros(k)
    rk = None
    if cx.EWT:                                                  # وزن هدف هم‌وزن رانش‌یافته روی واجدان؛ رتبه = ارزش معاملات
        b[idx] = cx.BEW[aidx][idx]
        if b.sum() <= 0:
            b[idx] = 1.0
        b /= b.sum()
        rk = np.nan_to_num(adv[aidx])
    else:
        b[idx] = cx.mc[aidx, idx] / cx.mc[aidx, idx].sum()
    Sig = g = None
    if any(m == "opt" for m, _, _ in keys):
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
    store = {}
    for key in keys:
        m, N, q = key
        cand = cands[q] if len(cands[q]) >= 3 else idx
        if m == "opt":
            sel, w = opt_pick(N, b, cand, Sig, g, rk)
        else:
            sel, w = choose(m, N, b, idx, cand, mk.sector, g, rk)
        store[key] = (sel, w, adv[aidx, sel])
    return store, idx, b


def sim_policy(cx, key, me, checks, TG, pays, days0, thr=None):
    """بازده روزانهٔ ناخالص سبد سهام یک ترکیب زیر یک سیاست ریبالانس (فصل ۳ «سیاست ریبالانس»).
    checks: روزهای بررسی (پایان روز a؛ اجرا a+1)؛ هدف همان روز از TG[a][key]. thr: None = همیشه ریبالانس؛ عدد = فقط اگر گردش
    یک‌طرفهٔ لازم ½Σ|w − w_رانش| ≥ thr (ریبالانس آستانه‌ای). روز اول (me[0]) همیشه خرید است.
    خروجی: r، dv، و برای هر ماه: to (گردش اجراشده در آغاز ماه؛ ۰ اگر ریبالانس نشد)، beta و sel (ترکیب واقعی آغاز ماه)، rbm (۱ = ریبالانس)؛
    tod = [(روز اجرا نسبی به days0، گردش)] برای ریبالانس‌های میان‌ماه."""
    mk, n, k, X, Y, K = cx.mk, cx.n, cx.k, cx.X, cx.Y, cx.K
    r = np.zeros(n - days0)
    dv = {}                                                             # (روز استحقاق، روز پرداخت) ⇒ سهم سود از ارزش دیروز سبد
    chk, mj = set(int(x) for x in checks), {a_: j for j, a_ in enumerate(me)}
    nm = len(me)
    to, beta, sel_m, rbm, tod = [0.0] * nm, [0.0] * nm, [None] * nm, [0] * nm, []
    w_prev = np.zeros(k)
    wv = np.zeros(k)
    for a_ in range(me[0], n - 1):
        if a_ in chk:
            sel, w, _ = TG[a_][key]
            wf = np.zeros(k); wf[sel] = w
            # قاعدهٔ A2 (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹؛ همان tools/sampled_replica.py): نماد جدیدِ بی‌معامله در روز اجرا خریده نمی‌شود و
            # نماد نگه‌داشتهٔ بی‌معامله با وزن رانش‌یافته می‌ماند. وزن نسبی سهام مستقل از اهرم/نقد است، پس مرورگر همین وزن را بازپخش می‌کند.
            tr = mk.tradable(a_)
            wf[~tr & (w_prev <= 0)] = 0.0
            if wf.sum() > 0:
                wf = wf / wf.sum()
            wf = cn.freeze_untradable(wf, w_prev, tr)
            need = 0.5 * float(np.abs(wf - w_prev).sum())
            if a_ == me[0] or thr is None or need >= thr:
                wv = wf.copy()
                if a_ in mj:
                    to[mj[a_]] = need; rbm[mj[a_]] = 1
                else:
                    tod.append((a_ + 1 - days0, need))
        if a_ in mj:                                                    # ترکیب واقعی آغاز ماه (پس از ریبالانس یا رانش‌یافته)
            j = mj[a_]
            cur = wv / wv.sum()
            s_ = np.where(cur > 0)[0]
            sel_m[j] = (s_, cur[s_])
            rs = X[a_ - 251: a_ + 1] @ cur
            ri = np.nan_to_num(K.values[a_ - 251: a_ + 1])
            beta[j] = float(np.cov(rs, ri)[0, 1] / max(np.var(ri, ddof=1), 1e-12))
        t = a_ + 1
        v0 = wv.sum()
        for i in np.nonzero((Y[t] > 0) & (wv > 0))[0]:
            kk = (t - days0, pays.get((t, int(i)), n) - days0)
            dv[kk] = dv.get(kk, 0.0) + float(wv[i] * Y[t, i] / v0)
        wv = wv * (1 + X[t])
        r[t - days0] = wv.sum() / v0 - 1
        w_prev = wv / wv.sum()
    return {"r": r, "dv": dv, "to": to, "beta": beta, "sel": sel_m, "rbm": rbm, "tod": tod}


def pack_dv(dv):
    dvk = sorted(dv)
    return [[a_ for a_, _ in dvk], [b_ for _, b_ in dvk], f32([dv[x] for x in dvk])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--target", choices=["k", "ew"], default="k", help="k = «شاخص كل» (ui/data/replica.js)؛ ew = «شاخص كل (هم وزن)» (ui/data/replica_ew.js)")
    a = ap.parse_args()
    ns = (30, 50) if a.quick else NS
    EWT = a.target == "ew"
    mk, K = sr.load(a.target)
    K = K.fillna(0)
    n, k = mk.n, mk.k
    pays = dp.pay_days(mk)                                                  # روز پرداخت واقعی هر سود (فصل ۳ §۳٫۵)
    print("سود نقدی:", dp.lag_summary(mk, pays))
    me = [int(x) for x in mk.month_end if mk.dates[x] >= sr.START and x >= 252 and x + 1 < n]
    live_a = n - 1
    days0 = me[0] + 1
    dates = mk.dates[days0:]
    cx = context(mk, K, a.target, me + [live_a])
    X, mc, ok_all, adv = cx.X, cx.mc, cx.ok_all, cx.adv
    BEW = cx.BEW
    # همتای کامل (هدف): واجدان عادی ∪ نمادهای تازه از روز پس از نخستین معامله (new_listings، همان sampled_replica)
    first = nl.first_trade(mk)
    if EWT:
        Cfull = cx.Cfull
    else:
        Cfull = np.zeros(n)
        for t in range(1, n):
            i, w_ = nl.full_target(mk, t, ok_all, first)
            if len(i):
                Cfull[t] = float(w_ @ X[t, i])
    # لایهٔ عرضهٔ اولیه: نماد تازهٔ بزرگ با وزن شاخص بیرون از انتخاب؛ مرورگر خرید روزانه (φ × ارزش معاملات ÷ اندازهٔ صندوق) را حساب می‌کند
    EV = [] if EWT else nl.events(mk, ok_all, me[0])
    WIPO = nl.weights(mk, EV, ok_all, first)
    VAL = np.nan_to_num(mk.val)
    print(f"لایهٔ عرضهٔ اولیه: {len(EV)} نماد تازهٔ بزرگ")
    keys = [(m, N, q) for q in LIQ for N in ns for m in METHODS]
    W = {}                                                                 # ماه به ماه: (sel, w, adv) ترکیب واقعی آغاز ماه
    B_month, nelig, sigdate = [], [], []

    TG = {}
    for j, aidx in enumerate(me):
        TG[aidx], idx, b = targets_at(cx, aidx, keys)
        B_month.append((idx, b[idx])); nelig.append(len(idx)); sigdate.append(int((mk.dates[aidx] - EPOCH).days))
        print(f"ماه {j + 1}/{len(me)} {mk.dates[aidx].date()}", flush=True) if j % 10 == 0 else None
    LIVE = targets_at(cx, live_a, keys)[0]
    # شبیه‌سازی روزانهٔ ناخالص هر ترکیب با ریبالانس ماهانه (سیاست پایه؛ سیاست‌های دیگر: tools/build_replica_rebal.py)
    cfg = {}
    for key in keys:
        cap = []
        for aidx in me:
            sel, w, ad = TG[aidx][key]
            cap.append(float(np.min(PART * np.nan_to_num(ad) / np.maximum(w, 1e-9))) if len(sel) else 0.0)   # ظرفیت ساخت هدف از نقد (پیش از انجماد)
        P = sim_policy(cx, key, me, me, TG, pays, days0)
        W[key] = [(s_, w_, adv[aidx, s_]) for (s_, w_), aidx in zip(P["sel"], me)]
        cfg["|".join(map(str, key))] = {"r": f32(P["r"]), "dv": pack_dv(P["dv"]), "to": [round(x, 4) for x in P["to"]], "beta": [round(x, 3) for x in P["beta"]], "cap": [round(x / 1e9, 2) for x in cap],
                                       "sel": [[[int(i) for i in s_], [int(round(x * 1e5)) for x in w_]] for s_, w_, _ in W[key]],
                                       "live": [[int(i) for i in LIVE[key][0]], [int(round(x * 1e5)) for x in LIVE[key][1]], round(float(np.min(PART * np.nan_to_num(LIVE[key][2]) / np.maximum(LIVE[key][1], 1e-9))) / 1e9, 2)]}
    el_live = mk.eligible(live_a, require_trade=False) & ok_all & (mc[live_a] > 0)
    idx_live = np.where(el_live | (ok_all & (first >= 0) & (first < live_a) & (mc[live_a] > 0)))[0]   # هدف زنده با نمادهای تازه
    ev_live = [e for e in EV if e["s"] <= live_a and e["end"] > live_a]
    used = sorted({int(i) for i in idx_live} | ({int(i) for i in np.where(BEW[live_a] > 0)[0]} if EWT else set()) | {e["i"] for e in EV} | {int(i) for key in keys for s, _, _ in W[key] for i in s} | {int(i) for key in keys for i in LIVE[key][0]} | {int(i) for idx, _ in B_month for i in idx})
    pos = {i: p for p, i in enumerate(used)}
    names = [{"c": str(mk.cols[i]), "s": str(mk.sym[i]), "sec": str(mk.sector[i])} for i in used]
    # شاخص وزن هدف: برای هر ماه فقط نمادهای واجد (ایندکس فشرده)
    for key, c in cfg.items():
        c["sel"] = [[[pos[i] for i in s], w] for s, w in c["sel"]]
        c["live"][0] = [pos[i] for i in c["live"][0]]
    # وزن هدف زنده
    idx = idx_live
    if EWT:                                                     # هدف هم‌وزن زنده
        idx = np.where(BEW[live_a] > 0)[0]
        bl = BEW[live_a][idx] / BEW[live_a][idx].sum()
    else:
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
           "part": PART, "configs": cfg, "ipo": ipo, "target": a.target}
    path = ROOT / "ui" / "data" / ("replica_ew.js" if EWT else "replica.js")
    path.write_text(("window.SIM_REP_EW = " if EWT else "window.SIM_REP = ") + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {path} ({path.stat().st_size / 1e6:.1f} MB)؛ {len(cfg)} ترکیب، {len(me)} ماه، {len(used)} نماد")


if __name__ == "__main__":
    main()
