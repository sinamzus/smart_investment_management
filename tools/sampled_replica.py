#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی «شاخص كل» (ارزش‌وزن، بازده کل) با N سهم؛ سود نقدی با تأخیر واقعی پرداخت و وام فقط برای تأخیر سود — فصل ۳ §۳٫۷.

    python tools/sampled_replica.py                         # جدول N × روش انتخاب × حالت (بدون وام / وام سود نقدی / تراز بتا)
    python tools/sampled_replica.py --rate 0.30 --cost 125  # نرخ وام سود سالانه و هزینهٔ رفت‌وبرگشت (bp)

مراحل (هر پایان ماه جلالی، اجرا با بازده از روز بعد):
  ۱ وزن هدف b = ارزش بازار نمادهای واجد بورس ÷ مجموع (همان روش وزن «شاخص كل» رسمی: ارزش بازار کل، نه شناور آزاد).
  ۲ انتخاب N سهم: top (N بزرگ‌ترین)، strat (طبقه‌ای: سهم هر صنعت از N ∝ وزنش؛ در هر صنعت بزرگ‌ترین‌ها)،
    opt (بهینه‌سازی: min (w−b)ᵀΣ(w−b) روی ۳N بزرگ‌ترین، فقط‌خرید؛ سپس N وزن برتر و حل دوباره؛ Σ = Ledoit–Wolf روی ۲۵۲ روز).
  ۳ سود نقدی (تصمیم مالک ۲۰۲۶-۱۰-۲۰): در روز استحقاق، سود y_t·V از بخش سرمایه‌گذاری‌شده جدا و «طلب» می‌شود و تا روز پرداخت
    واقعی (dividend_pay.pay_days: فارابی، fundai، وگرنه +۹۶ روز) بی‌بازده می‌ماند؛ در روز پرداخت دوباره سرمایه‌گذاری می‌شود.
  ۴ حالت‌ها: none = تمام سرمایه‌گذاری، سود با تأخیر؛ bridge = «وام سود نقدی»: در روز استحقاق دقیقاً به اندازهٔ طلب وام گرفته و
    سرمایه‌گذاری می‌شود، پرداخت سود وام را تسویه می‌کند، بهره با نرخ rb انباشته و بدهی هرگز از طلب بیشتر نمی‌شود (مازاد بهره از
    فروش سهام پرداخت می‌شود)؛ beta = «تراز بتا» فقط نقد: L = clip(1/β, ۰٫۷, ۱) — وام برای اهرم مجاز نیست.
  ۵ هزینه: گردش یک‌طرفه × L × هزینهٔ رفت‌وبرگشت.
  ۶ ارزیابی روی بازده روزانه در برابر «شاخص كل» رسمی (بازده کل) و در برابر همتای ارزش‌وزن کامل خودمان
    (دومی فقط خطای نمونه‌گیری را نشان می‌دهد؛ اولی خطای تفاوت اعضا (شرط واجدیت ۲۵۲ روزه، ماهانه) و داده را هم دارد).
همان به‌روزرسانی روزانهٔ مقیاس‌دار (step_day) در موتور مرورگر (ui/builder.js simulate) هست؛ node tools/replica_selftest.js هم‌ارزی را می‌سنجد.
محدودیت: بدون صف/حد نوسان/توقف؛ نرخ و دسترسی به وام سود واقعی نیست **[تأیید لازم]**.
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
import new_listings as nl  # noqa: E402
import ew_target as et  # noqa: E402

NS = (10, 20, 30, 50, 80, 120)
METHODS = ("top", "strat", "opt")
START = pd.Timestamp("2018-03-21")


def load(target="k"):
    """(Market، سری رسمی هدف): target = k («شاخص كل») یا ew («شاخص كل (هم وزن)»)؛ پانل تا آخرین روز سری رسمی «شاخص كل» بریده می‌شود."""
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
    K = (ir.load_pair("EW").tr if target == "ew" else K0).reindex(mk.dates)
    return mk, K


def lw_cov(R):
    from sklearn.covariance import LedoitWolf
    R = np.nan_to_num(R)
    return LedoitWolf().fit(R).covariance_


def pick_top(b, idx, N, rk=None):
    """N نامزد برتر بر پایهٔ rk (پیش‌فرض وزن هدف b؛ برای هدف هم‌وزن ارزش معاملات، «N نقدشونده‌ترین»)."""
    rk = b if rk is None else rk
    o = idx[np.argsort(-rk[idx])]
    return o[:N]


def pick_strat(b, idx, N, sector, rk=None):
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
        sel += list(members[np.argsort(-(b if rk is None else rk)[members])][:q])
    return np.array(sel[:N])


def pick_opt(b, idx, N, Sig, pos, rk=None):
    from cvxpy import Minimize, Problem, Variable, quad_form, psd_wrap
    pool = pick_top(b, idx, 3 * N, rk)

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


def ipo_rebalance(V, H, EV, W, a, cost_bp):
    """ریبالانس ماهانهٔ لایهٔ عرضهٔ اولیه (همان ui/builder.js simulate): نمادی که تا روز a واجد عادی شده رها و به سهام عادی
    فروخته می‌شود؛ بقیه اگر بالای وزن شاخص روز a+1 باشند تا همان وزن کم می‌شوند. هزینه = حجم معامله × c."""
    tot = V + sum(H.values())
    for e in EV:
        i = e["i"]
        if i not in H:
            continue
        if e["end"] <= a:
            x = H.pop(i)
        else:
            x = max(H[i] - W[i][a + 1] * tot, 0.0)
            H[i] -= x
        V += x - x * cost_bp / 1e4
    return V, H


def ipo_day(V, H, EV, W, X, VAL, t, phi, aum_bn, cost_bp):
    """یک روز لایهٔ عرضهٔ اولیه: بازده روز، سپس خرید در پایانی تا وزن شاخص، حداکثر φ × ارزش معاملات امروز ÷ اندازهٔ صندوق
    (صف خرید هم: بخشی از صف پر می‌شود). خرید از فروش سهام عادی؛ هزینه = حجم × c."""
    for i in H:
        H[i] *= 1 + X[t, i]
    tot = V + sum(H.values())
    for e in EV:
        i = e["i"]
        if not (e["s"] <= t < e["end"] + nl.HOLD) or (i not in H and t >= e["end"]):
            continue
        need = W[i][t] * tot - H.get(i, 0.0)
        if need <= 0:
            continue
        amt = min(need, phi * VAL[t, i] / (aum_bn * 1e9), max(V, 0.0))
        if amt > 0:
            H[i] = H.get(i, 0.0) + amt
            V -= amt + amt * cost_bp / 1e4
    return V, H


def step_day(V, D, rcv, g, divs, paid, sched, bridge, rate, days):
    """یک روز مدل سود نقدی و وام سود (همان ui/builder.js simulate). V سهام، D وام سود، rcv طلب سود؛ g بازده کل روز سبد؛
    divs = [(روز پرداخت، سهم سود از V دیروز)]؛ paid = پرداخت‌های رسیدهٔ امروز (پیش از ثبت سودهای امروز برداشته شده)."""
    if D > 0:
        D *= 1 + rate * days / 365.0
    ytot = 0.0
    for p, y in divs:
        A = y * V
        sched[p] = sched.get(p, 0.0) + A
        rcv += A
        ytot += y
        if bridge:
            D += A
    V *= 1 + g - (0.0 if bridge else ytot)                             # بدون وام: سود از سهام جدا و طلب می‌شود
    if paid:
        rcv -= paid
        if bridge:
            D -= paid
        else:
            V += paid                                                   # سرمایه‌گذاری دوبارهٔ سود دریافتی
    if D > rcv:                                                         # سقف روزانه: وام سود ≤ طلب سود؛ بهرهٔ مازاد از فروش سهام
        V -= D - rcv
        D = rcv
    return V, D, rcv


def run(mk, K, rate, cost_bp, N, method, lev_mode, pays=None, ipo=None, tgt=None):
    """lev_mode: none | bridge | beta. pays: dividend_pay.pay_days(mk) (برای سرعت یک بار ساخته و دوباره استفاده شود).
    ipo: (رویدادها، وزن‌ها، φ، اندازهٔ صندوق میلیارد ریال) از new_listings — لایهٔ نماد تازهٔ بزرگ؛ None یعنی بدون لایه.
    tgt: None = «شاخص كل» (وزن هدف ارزش بازار، رتبه = وزن)؛ {"B": وزن‌های هم‌وزن پایان روز a، "adv": ارزش معاملات} = هدف هم‌وزن
    (وزن هدف = وزن رانش‌یافتهٔ هم‌وزن روی واجدان، بازنرمال؛ رتبه = میانهٔ ۶۳ روزهٔ ارزش معاملات)."""
    if pays is None:
        import dividend_pay
        pays = dividend_pay.pay_days(mk)
    bridge = lev_mode == "bridge"
    Y = np.nan_to_num(mk.Y)
    n, k = mk.n, mk.k
    me = [int(a) for a in mk.month_end if mk.dates[a] >= START and a >= 252 and a + 1 < n]
    me.append(None)
    ok_all = np.isin(mk.market, ["bourse"])
    V, D, cash, rcv = 1.0, 0.0, 0.0, 0.0
    H = {}                                                              # لایهٔ عرضهٔ اولیه: نماد ⇒ ارزش
    EV, WIPO, PHI, AUM = ipo if ipo else ([], {}, 0.0, 1.0)
    VAL = np.nan_to_num(mk.val)
    sched = {}                                                          # روز پرداخت ⇒ مبلغ طلب سود
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
        rk = None
        if tgt is not None:
            bw = tgt["B"][a]
            b[idx] = bw[idx]
            if b.sum() <= 0:
                b[idx] = 1.0
            b /= b.sum()
            rk = np.nan_to_num(tgt["adv"][a])
        else:
            b[idx] = mc[idx] / mc[idx].sum()
        pos = {i: p for p, i in enumerate(idx)}
        Sig = None
        if method == "opt":
            Sig = lw_cov(mk.X[a - 251: a + 1][:, idx])
            Sfull = np.zeros((k, k))
            Sfull[np.ix_(idx, idx)] = Sig
            pos = {i: i for i in idx}
            sel, wsel = pick_opt(b, idx, N, Sfull, pos, rk)
            w = np.zeros(k)
            w[sel] = wsel
        elif method == "strat":
            sel = pick_strat(b, idx, N, mk.sector, rk)
            w = np.zeros(k); w[sel] = b[sel] / b[sel].sum()
        else:
            sel = pick_top(b, idx, N, rk)
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
            L = float(np.clip(1.0 / beta if beta > 0 else 1.0, 0.7, 1.0))   # فقط نقد؛ وام برای اهرم نه
        V, H = ipo_rebalance(V, H, EV, WIPO, a, cost_bp)
        # ریبالانس: وام سود هرگز بیش از طلب سود نیست (مازاد بهره از دارایی پرداخت می‌شود)؛ سرمایهٔ قابل‌سرمایه‌گذاری = دارایی منهای طلب
        if D > rcv:
            V -= D - rcv
            D = rcv
        E = V + cash
        drift_w = w_prev
        to = 0.5 * np.abs(w - drift_w).sum() * L
        E -= to * E * cost_bp / 1e4
        V, cash = L * E, (1.0 - L) * E                                  # L<1: بقیه نقد بدون بهره
        turn.append(to); lev_l.append(L)
        wv = w.copy()                                                   # فقط برای وزن و بازده روزانهٔ سبد (رانش TR)
        prev_d = mk.dates[a]
        for t in range(a + 1, b_end + 1):
            days = (mk.dates[t] - prev_d).days; prev_d = mk.dates[t]
            v0 = wv.sum()
            yv = wv * Y[t] / v0 if v0 > 0 else np.zeros(k)              # سهم سود هر نماد از ارزش دیروز سبد
            wv = wv * (1 + X[t])
            g = wv.sum() / v0 - 1 if v0 > 0 else 0.0
            V, D, rcv = step_day(V, D, rcv, g, [(pays.get((t, int(i)), mk.n), float(yv[i])) for i in np.nonzero(yv > 0)[0]],
                                 sched.pop(t, 0.0), sched, bridge, rate, days)
            V, H = ipo_day(V, H, EV, WIPO, X, VAL, t, PHI, AUM, cost_bp)
            navs.append(V + cash + rcv - D + sum(H.values())); dates.append(mk.dates[t])
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
    ap.add_argument("--phi", type=float, default=nl.PHI, help="سهم صندوق از ارزش معاملات روزانهٔ نماد تازه (لایهٔ عرضهٔ اولیه)")
    ap.add_argument("--aum", type=float, default=nl.AUM_BN, help="اندازهٔ صندوق برای سقف خرید نماد تازه (میلیارد ریال)")
    ap.add_argument("--target", choices=["k", "ew"], default="k", help="k = «شاخص كل»؛ ew = «شاخص كل (هم وزن)» (خروجی با پسوند _ew)")
    a = ap.parse_args()
    mk, K = load(a.target)
    sfx = "_ew" if a.target == "ew" else ""
    K = K.fillna(0)
    ok = np.isin(mk.market, ["bourse"])
    # همتای کامل (هدف): واجدان عادی ∪ نمادهای تازه از روز پس از نخستین معامله (new_listings.full_target)، وزن ارزش بازار روز قبل،
    # ریبالانس روزانه با اجرای کامل — کران پایین خطای وزن. نسخهٔ پیشین (فقط واجدان عادی، سابقهٔ ۲۵۲ روزه) برای مقایسه چاپ و ذخیره می‌شود.
    Cfull, Cold = pd.Series(0.0, index=mk.dates), pd.Series(0.0, index=mk.dates)
    X = np.nan_to_num(mk.X)
    mc = np.nan_to_num(mk.mcap)
    first = nl.first_trade(mk)
    rows = []
    for t in range(1, mk.n):
        idx, w = nl.full_target(mk, t, ok, first)
        if len(idx):
            Cfull.iloc[t] = float(w @ X[t, idx])
        io = np.where(mk.eligible(t - 1, require_trade=False) & ok & (mc[t - 1] > 0))[0]
        if len(io):
            Cold.iloc[t] = float((mc[t - 1, io] / mc[t - 1, io].sum()) @ X[t, io])
    tgt = None
    if a.target == "ew":                                           # هدف هم‌وزن: همتای کامل = هم‌وزن فصلی همهٔ بورس (ew_target)
        me_all = [int(x) for x in mk.month_end if mk.dates[x] >= START and x >= 252 and x + 1 < mk.n]
        Cew, Bew = et.ew_path(mk, ok, me_all)
        Cfull = pd.Series(Cew, index=mk.dates)
        tgt = {"B": Bew, "adv": cn.liq_windows(mk, ok)[0]}       # رتبهٔ «نقدشونده‌ترین»: ۶۳ روز باز بازار
    base = evaluate(pd.Series((1 + Cfull[Cfull.index >= START]).cumprod()), K, Cfull)
    old = evaluate(pd.Series((1 + Cold[Cold.index >= START]).cumprod()), K, Cfull)
    if a.target == "ew":
        old = base                                                  # «بدون نمادهای تازه» فقط برای هدف ارزش‌وزن معنا دارد
    print(f"[{'هم‌وزن' if a.target == 'ew' else 'ارزش‌وزن'}] همتای کامل (با نمادهای تازه) در برابر شاخص رسمی: TE = {base['te_vs_official_pct']:.2f}٪؛ تفاوت بازده سالانه {base['gap_pct']:+.2f}٪؛ همبستگی {base['corr']:.4f}")
    print(f"  (بدون نمادهای تازه، قاعدهٔ پیشین: TE = {old['te_vs_official_pct']:.2f}٪؛ تفاوت {old['gap_pct']:+.2f}٪)\n")
    EV = nl.events(mk, ok, int(np.searchsorted(mk.dates, START))) if a.target == "k" else []
    WIPO = nl.weights(mk, EV, ok, first)
    print(f"لایهٔ عرضهٔ اولیه: {len(EV)} نماد تازهٔ بزرگ (وزن روز دوم ≥ {100 * nl.THRESH:.1f}٪)؛ φ = {100 * a.phi:.0f}٪، اندازهٔ صندوق {a.aum:,.0f} میلیارد ریال")
    import json
    json.dump({"target": a.target, "rate": a.rate, "cost_bp": a.cost, "from": str(START.date()), "to": str(mk.dates[-1].date()), "n_eligible_last": int((mk.eligible(mk.n - 1, require_trade=False) & ok).sum()),
               "full_replica": {k: float(v) for k, v in base.items()}, "full_replica_without_new": {k: float(v) for k, v in old.items()},
               "ipo": {"n_events": len(EV), "thresh": nl.THRESH, "phi": a.phi, "aum_bn": a.aum}}, open(ROOT / "data" / "research" / f"sampled_replica_meta{sfx}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for N in [int(x) for x in a.ns.split(",")]:
        for m in METHODS:
            for lev in ("none", "bridge", "beta"):
                try:
                    s, to, L = run(mk, K, a.rate, a.cost, N, m, lev, ipo=(EV, WIPO, a.phi, a.aum), tgt=tgt)
                except Exception as e:  # noqa: BLE001
                    print("خطا", N, m, lev, type(e).__name__, e); continue
                ev = evaluate(s, K, Cfull)
                rows.append({"N": N, "method": m, "leverage": lev, "mean_L": L, "turnover_oneway_pct": 100 * to, **ev})
                print(f"N={N:3d} {m:5s} L={ {'none': '1', 'bridge': 'وام سود'}.get(lev, 'β') } (L̄={L:.2f}) بازده {ev['ann_pct']:6.1f}٪ شاخص {ev['ann_index_pct']:6.1f}٪ فاصله {ev['gap_pct']:+6.1f} TE_رسمی {ev['te_vs_official_pct']:5.2f} TE_همتا {ev['te_vs_fullreplica_pct']:5.2f} β={ev['beta']:.2f} ρ={ev['corr']:.3f} گردش {100 * to:4.0f}٪", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "data" / "research" / f"sampled_replica{sfx}.csv", index=False, encoding="utf-8-sig")
    print(f"\nذخیره شد: data/research/sampled_replica{sfx}.csv")


if __name__ == "__main__":
    main()
