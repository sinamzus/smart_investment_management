#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الگوریتم‌های انتخاب و وزن‌دهی + بک‌تست عمومی (فصل ۱۴ بخش ب).

یک «استراتژی» با یک spec توصیف می‌شود:
    {
      "signals": [["mom_12_1", 1.0], ["vol_252", 1.0]],        # (معیار، وزن)؛ وزن منفی = معکوس
      "combine": "equal" | "ic" | "icir" | "fm" | "ridge" | "rank",
      "neutral": true,                                         # خنثی‌سازی صنعتی Z
      "algo": "topfrac", "params": {"entry": .2, "exit": .3},  # الگوریتم انتخاب
      "universe": {"markets": ["bourse", "farabourse"], "min_adv": 0},
      "rebalance_every": 1, "partial": 1.0, "max_w": 0.05, "cost_bp": 100, "delay": 0
    }
نتیجه: سری ماهانهٔ بازده، گردش، تعداد نماد، وزن‌های زنده. قیاس‌پذیر با tools/factor_engine.py (همان واجدیت و همان قرارداد گردش).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import signals as sg  # noqa: E402
import factor_engine as fe  # noqa: E402

ALGOS: dict = {}
AUMS = [1e10, 5e10, 1e11, 5e11, 1e12, 5e12]      # سطوح سرمایهٔ سنجش ظرفیت (ریال = ۱۰ تا ۵۰۰۰ میلیارد)
Y_IMPACT = 1.0                                    # ضریب اثر بازار Y در Yσ√(Q/ADV) [تأیید لازم؛ ادبیات ≈ ۰٫۵–۱]


def algo(name, fa, en, desc, ref, params):
    def deco(fn):
        ALGOS[name] = {"name": name, "fa": fa, "en": en, "desc": desc, "ref": ref, "params": params, "fn": fn}
        return fn
    return deco


def quant(z):
    """Zِ کوانتیزه (۱/۴۰)؛ نمایش مشترک پایتون و مرورگر (Int8 در lab.js) تا نتیجه‌ها یکی باشند."""
    return np.where(np.isnan(z), np.nan, np.clip(np.round(z * 40), -127, 127) / 40)


class Lab:
    """بستهٔ داده برای بک‌تست: امتیازهای ماهانه، بازده آینده، واجدیت."""

    def __init__(self, mk: sg.Market, idx, S):
        self.mk, self.idx, self.S = mk, idx, S
        self.me = idx[:-1]
        self.rows = len(self.me)
        self.fw, self.ok, self.use = {}, {}, []
        for r in range(self.rows - 1):
            a, b = self.me[r], self.me[r + 1]
            f = mk.fwd(a, b)
            self.fw[r] = f
            self.ok[r] = mk.eligible(a) & ~np.isnan(f)
            if mk.dates[a + 1] >= sg.EVAL_FROM:
                self.use.append(r)
        self._z, self._ic = {}, {}
        self.sector = mk.sector
        self.mkts = mk.market

    # ── Z و IC ──
    def z(self, name, r):
        key = (name, r)
        if key not in self._z:
            ok = self.ok[r] if r in self.ok else mk_all_true(self.mk)
            self._z[key] = quant(sg.winsor_z(self.S[name][r], ok))
        return self._z[key]

    def ic(self, name, r):
        key = (name, r)
        if key not in self._ic:
            self._ic[key] = sg.spearman_rows(self.z(name, r), self.fw[r]) if r in self.fw else np.nan
        return self._ic[key]

    def hist_ic(self, name, r, L=36):
        v = [self.ic(name, j) for j in range(max(0, r - L), r)]
        v = [x for x in v if x == x]
        return v

    # ── ترکیب معیارها ──
    def score(self, spec, r, live=False):
        sigs = spec["signals"]
        method = spec.get("combine", "equal")
        neutral = spec.get("neutral", True)
        Zs, ws = [], []
        for name, w in sigs:
            if name not in self.S:
                continue
            ok = self.ok[r] if r in self.ok else self.live_ok
            z = quant(sg.winsor_z(self.S[name][r], ok)) if live or r not in self.ok else self.z(name, r)
            if neutral:
                z = sg.neutral(z, self.sector)
            Zs.append(z)
            ws.append(w)
        if not Zs:
            return np.full(self.mk.k, np.nan)
        Z = np.vstack(Zs)
        ws = np.array(ws, float)
        if method in ("ic", "icir"):
            h = [self.hist_ic(n, r) for n, _ in sigs if n in self.S]
            if all(len(x) >= 12 for x in h):
                m = np.array([np.mean(x) for x in h])
                if method == "icir":
                    m = m / np.array([max(np.std(x, ddof=1), 1e-6) for x in h])
                ws = ws * m / (np.abs(m).sum() + 1e-12) * len(m)
        elif method == "topk_icir":
            # انتخاب پویای معیار: k معیار با بیشترین |ICIR| در ۳۶ ماه گذشته (دست‌کم ۲۴ مشاهده)؛ علامت = علامت IC میانگین
            k = int(spec.get("topk", 5))
            names_ = [n for n, _ in sigs if n in self.S]
            sc_ = []
            for n in names_:
                h = self.hist_ic(n, r)
                if len(h) >= 24 and np.std(h, ddof=1) > 0:
                    sc_.append((abs(np.mean(h) / np.std(h, ddof=1)), np.sign(np.mean(h))))
                else:
                    sc_.append((0.0, 0.0))
            order = np.argsort([-x[0] for x in sc_])[:k]
            ws = np.zeros(len(names_))
            for j in order:
                ws[j] = sc_[j][1]
            if not ws.any():
                return np.full(self.mk.k, np.nan)
        elif method in ("fm", "ridge") and r >= 12:
            ws = self._fm_weights(spec, r, [n for n, _ in sigs if n in self.S], ridge=(method == "ridge")) * np.sign(ws + 1e-12)
        if method == "rank":
            Rk = np.vstack([pd.Series(z).rank(pct=True).values for z in Z])
            s = np.nansum(Rk * ws[:, None], axis=0) / np.abs(ws).sum()
            cnt = np.sum(~np.isnan(Rk), axis=0)
            return np.where(cnt >= max(1, int(0.6 * len(Zs))), s, np.nan)
        cntv = np.sum(~np.isnan(Z), axis=0)
        s = np.nansum(Z * ws[:, None], axis=0)
        s = np.where(cntv >= max(1, int(0.6 * len(Zs))), s, np.nan)
        sd = np.nanstd(s)
        return s / sd if sd > 0 else s

    def _fm_weights(self, spec, r, names, ridge=False, L=36):
        """بتاهای مقطعی Fama–MacBeth (میانگین ۳۶ ماه گذشته) به‌عنوان وزن ترکیب؛ ridge با جریمهٔ بیشتر."""
        B = []
        for j in range(max(0, r - L), r):
            if j not in self.fw:
                continue
            Zj = np.column_stack([self.z(n, j) for n in names])
            y = self.fw[j]
            m = ~np.isnan(Zj).any(axis=1) & ~np.isnan(y) & self.ok[j]
            if m.sum() < 50:
                continue
            lam = (5.0 if ridge else 0.1) * m.sum() / 100
            A = Zj[m]
            yy = y[m] - y[m].mean()
            B.append(np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ yy))
        if len(B) < 12:
            return np.ones(len(names))
        b = np.mean(B, axis=0)
        return b / (np.abs(b).sum() + 1e-12) * len(names)

    @property
    def live_ok(self):
        return self.mk.eligible(self.idx[-1])


def mk_all_true(mk):
    return np.ones(mk.k, bool)


# ═══════════════════ الگوریتم‌ها: (امتیاز، زمینه) ← وزن ═══════════════════
def _cap(w, max_w, iters=50):
    w = w.copy()
    if max_w is None or max_w <= 0 or (w > 0).sum() * max_w < 1:
        return w / w.sum() if w.sum() > 0 else w
    for _ in range(iters):
        over = w > max_w
        if not over.any():
            break
        ex = (w[over] - max_w).sum()
        w[over] = max_w
        free = (~over) & (w > 0)
        if not free.any():
            break
        w[free] += ex * w[free] / w[free].sum()
    return w / w.sum()


def _selected(ctx, entry, exit_):
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    idx = np.where(m)[0]
    if len(idx) < 30:
        return np.array([], int)
    order = idx[np.argsort(s[idx], kind="stable")]
    pct = np.full(len(s), np.nan)
    pct[order[::-1]] = (np.arange(len(order)) + 0.5) / len(order)
    held = ctx["held"]
    sel = np.where((held & m & (pct <= exit_)) | (m & (pct <= entry)))[0]
    return sel


@algo("quantile", "گروه کمّی (دهک/پنجک)", "Quantile sort", "اوراق را بر پایهٔ امتیاز به G گروه برابر تقسیم و گروه k را هم‌وزن نگه می‌دارد (k=G قوی‌ترین).",
      "Fama & French (1992)", {"G": 5, "k": 5})
def a_quantile(ctx, G=5, k=5):
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    idx = np.where(m)[0]
    if len(idx) < 30:
        return np.zeros(len(s))
    order = idx[np.argsort(s[idx], kind="stable")]
    g = np.array_split(order, int(G))[int(k) - 1]
    w = np.zeros(len(s))
    w[g] = 1 / len(g)
    return w


@algo("topfrac", "بالاترین سهم با بافر (هم‌وزن)", "Top fraction with buffer", "ورود اگر رتبهٔ درصدی ≤ entry، ماندن تا ≤ exit؛ هم‌وزن. بافر گردش را کم می‌کند.",
      "MSCI Index Methodology (buffer rules)؛ Garleanu & Pedersen (2013)", {"entry": 0.2, "exit": 0.3})
def a_topfrac(ctx, entry=0.2, exit=0.3):
    sel = _selected(ctx, entry, max(exit, entry))
    w = np.zeros(len(ctx["score"]))
    if len(sel):
        w[sel] = 1 / len(sel)
    return w


@algo("topn", "N نماد برتر با بافر (هم‌وزن)", "Top-N with buffer", "N نماد برتر؛ نماد تا رتبهٔ N+buffer نگه داشته می‌شود.", "رویهٔ رایج مدیریت فعال", {"N": 50, "buffer": 25})
def a_topn(ctx, N=50, buffer=25):
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    n = m.sum()
    if n < 30:
        return np.zeros(len(s))
    return a_topfrac(ctx, entry=min(N / n, 1.0), exit=min((N + buffer) / n, 1.0))


@algo("score_tilt", "وزن نمایی امتیاز", "Exponential score tilt", "w ∝ exp(λ·z) روی همهٔ واجدان؛ λ شدت تمایل را تعیین می‌کند (λ=0 هم‌وزن).", "Grinold & Kahn (2000)", {"lam": 1.0})
def a_score_tilt(ctx, lam=1.0):
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    w = np.zeros(len(s))
    if m.sum() < 30:
        return w
    w[m] = np.exp(lam * np.clip(s[m], -3, 3))
    return w / w.sum()


@algo("rank_weight", "وزن رتبه‌ای (فقط بالای میانه)", "Rank weighting (long-only)", "w ∝ max(رتبه − میانه، 0)؛ نسخهٔ فقط‌خرید وزن‌دهی رتبه‌ای.", "Asness, Moskowitz & Pedersen (2013)", {})
def a_rank_weight(ctx):
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    w = np.zeros(len(s))
    if m.sum() < 30:
        return w
    r = pd.Series(s[m]).rank(pct=True).values
    w[m] = np.maximum(r - 0.5, 0)
    return w / w.sum() if w.sum() > 0 else w


@algo("msci_tilt", "تمایل Z به وزن بازار (سبک MSCI)", "Cap-weight × Z-tilt", "w ∝ ارزش بازار × (۱+z برای z>0، ۱/(۱−z) برای z<0)، با سقف وزن. روش شاخص‌های فاکتوری MSCI.", "MSCI Factor Indexes Methodology (2023)", {})
def a_msci_tilt(ctx):
    s, ok, mc = ctx["score"], ctx["ok"], ctx["mcap"]
    m = ok & ~np.isnan(s) & (mc > 0)
    w = np.zeros(len(s))
    if m.sum() < 30:
        return w
    z = np.clip(s[m], -3, 3)
    t = np.where(z > 0, 1 + z, 1 / (1 - z))
    w[m] = mc[m] * t
    return w / w.sum()


def _cov(ctx, sel):
    """کوواریانس ماهانه‌شدهٔ انقباض‌یافته (Ledoit–Wolf) از بازده ۵روزهٔ غیرهم‌پوشان ۵۰۴ روز اخیر (کاهش اثر معاملات ناهمزمان)."""
    from sklearn.covariance import LedoitWolf
    mk, a = ctx["mk"], ctx["a"]
    lo = max(a - 504, 0)
    LR = mk.LR[lo:a + 1][:, sel]
    n = (len(LR) // 5) * 5
    Rw = LR[len(LR) - n:].reshape(-1, 5, LR.shape[1]).sum(axis=1)
    if Rw.shape[0] < 30:
        return None
    lw = LedoitWolf().fit(Rw)
    return lw.covariance_ * (52 / 12)               # ماهانه


def _risk_pool(ctx, entry, exit_):
    sel = _selected(ctx, entry, max(exit_, entry))
    return sel


@algo("inv_vol", "وزن معکوس نوسان", "Inverse-volatility", "در مجموعهٔ برتر (top fraction)، w ∝ 1/σ؛ ساده‌ترین وزن‌دهی مبتنی بر ریسک.", "Qian (2005) Risk Parity", {"entry": 0.3, "exit": 0.4})
def a_inv_vol(ctx, entry=0.3, exit=0.4):
    sel = _risk_pool(ctx, entry, exit)
    w = np.zeros(len(ctx["score"]))
    if len(sel) == 0:
        return w
    sd = ctx["vol"][sel]
    ok = sd > 0
    if ok.sum() == 0:
        w[sel] = 1 / len(sel)
        return w
    w[sel[ok]] = 1 / sd[ok]
    return w / w.sum()


def _solve_qp(C, kind, max_w, prev=None, sig=None):
    import cvxpy as cp
    n = C.shape[0]
    w = cp.Variable(n, nonneg=True)
    L = np.linalg.cholesky(C + 1e-10 * np.eye(n))
    cons = [cp.sum(w) == 1]
    if max_w:
        cons.append(w <= max(max_w, 1.5 / n))
    var = w
    if kind == "minvar":
        prob = cp.Problem(cp.Minimize(cp.sum_squares(L.T @ w)), cons)
    elif kind == "maxdiv":
        # min w'Σw  s.t.  σ'w = 1، سپس بازنرمال‌سازی (Choueifaty & Coignard 2008)
        var = cp.Variable(n, nonneg=True)
        prob = cp.Problem(cp.Minimize(cp.sum_squares(L.T @ var)), [sig @ var == 1])
    else:
        raise ValueError(kind)
    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception:  # noqa: BLE001
        pass
    if var.value is None:                              # حل‌گر شکست خورد ← هم‌وزن (به‌جای TypeError)
        return np.full(n, 1.0 / n)
    v = np.maximum(np.asarray(var.value).ravel(), 0)
    return v / v.sum() if v.sum() > 0 else np.full(n, 1.0 / n)


@algo("min_var", "حداقل واریانس (فقط‌خرید)", "Minimum variance", "در مجموعهٔ برتر، کمینه‌سازی w'Σw با Σ انقباضی Ledoit–Wolf و سقف وزن.", "Clarke, de Silva & Thorley (2006)؛ Ledoit & Wolf (2004)", {"entry": 0.4, "exit": 0.5, "max_w": 0.05})
def a_min_var(ctx, entry=0.4, exit=0.5, max_w=0.05):
    sel = _risk_pool(ctx, entry, exit)
    w = np.zeros(len(ctx["score"]))
    if len(sel) < 20:
        return w
    C = _cov(ctx, sel)
    if C is None:
        w[sel] = 1 / len(sel)
        return w
    w[sel] = _solve_qp(C, "minvar", max_w)
    return w


@algo("max_div", "حداکثر تنوع", "Maximum diversification", "بیشینه‌کردن نسبت میانگین وزنی σ به σ پرتفوی (تنوع‌بخشی)", "Choueifaty & Coignard (2008)", {"entry": 0.4, "exit": 0.5})
def a_max_div(ctx, entry=0.4, exit=0.5):
    sel = _risk_pool(ctx, entry, exit)
    w = np.zeros(len(ctx["score"]))
    if len(sel) < 20:
        return w
    C = _cov(ctx, sel)
    if C is None:
        w[sel] = 1 / len(sel)
        return w
    w[sel] = _solve_qp(C, "maxdiv", None, sig=np.sqrt(np.diag(C)))
    return _cap(w, 0.08)


@algo("erc", "ریسک برابر (ERC)", "Equal risk contribution", "سهم هر نماد از ریسک پرتفوی برابر؛ حل مسئلهٔ لگاریتمی محدب.", "Maillard, Roncalli & Teiletche (2010)", {"entry": 0.4, "exit": 0.5})
def a_erc(ctx, entry=0.4, exit=0.5):
    from scipy.optimize import minimize
    sel = _risk_pool(ctx, entry, exit)
    w = np.zeros(len(ctx["score"]))
    if len(sel) < 20:
        return w
    C = _cov(ctx, sel)
    if C is None:
        w[sel] = 1 / len(sel)
        return w
    n = len(sel)
    f = lambda y: 0.5 * y @ C @ y - np.log(y).sum() / n              # noqa: E731
    g = lambda y: C @ y - 1 / (n * y)                                # noqa: E731
    y0 = 1 / np.sqrt(np.diag(C))
    res = minimize(f, y0 / y0.sum() * 0.5, jac=g, bounds=[(1e-8, None)] * n, method="L-BFGS-B")
    y = np.maximum(res.x, 1e-12)
    w[sel] = y / y.sum()
    return _cap(w, 0.08)


@algo("hrp", "ریسک سلسله‌مراتبی (HRP)", "Hierarchical risk parity", "خوشه‌بندی سلسله‌مراتبی همبستگی + دوبخشی بازگشتی؛ بدون وارونه‌سازی Σ.", "López de Prado (2016)", {"entry": 0.4, "exit": 0.5})
def a_hrp(ctx, entry=0.4, exit=0.5):
    from scipy.cluster.hierarchy import leaves_list, linkage
    from scipy.spatial.distance import squareform
    sel = _risk_pool(ctx, entry, exit)
    w = np.zeros(len(ctx["score"]))
    if len(sel) < 20:
        return w
    C = _cov(ctx, sel)
    if C is None:
        w[sel] = 1 / len(sel)
        return w
    sd = np.sqrt(np.diag(C))
    corr = np.clip(C / np.outer(sd, sd), -1, 1)
    dist = np.sqrt(0.5 * (1 - corr))
    np.fill_diagonal(dist, 0)
    order = leaves_list(linkage(squareform(dist, checks=False), "single"))
    wts = pd.Series(1.0, index=order)
    items = [list(order)]
    while items:
        items = [i[j:k] for i in items for j, k in ((0, len(i) // 2), (len(i) // 2, len(i))) if len(i) > 1]
        for i in range(0, len(items), 2):
            a_, b_ = items[i], items[i + 1]

            def cvar(c):
                sub = C[np.ix_(c, c)]
                iv = 1 / np.diag(sub)
                iv /= iv.sum()
                return iv @ sub @ iv
            va, vb = cvar(a_), cvar(b_)
            al = 1 - va / (va + vb)
            wts[a_] *= al
            wts[b_] *= 1 - al
    w[sel[wts.index.values]] = wts.values
    return _cap(w / w.sum(), 0.08)


@algo("mvo_te", "بهینه‌سازی میانگین–واریانس با قید خطای ردیابی", "TE-constrained MVO", "بیشینه‌کردن α'w − (λ/2)w'Σw − τ‖w−w₀‖₁ با قید خطای ردیابی نسبت به هم‌وزن واجدان، سقف وزن و انحراف صنعتی. α = IC·σ·z.",
      "Grinold & Kahn (2000)؛ Roll (1992)؛ Garleanu & Pedersen (2013)", {"te_max": 0.04, "lam": 8.0, "tau_bp": 20, "max_w": 0.04, "ic": 0.05})
def a_mvo_te(ctx, te_max=0.04, lam=8.0, tau_bp=20, max_w=0.04, ic=0.05):
    import cvxpy as cp
    s, ok = ctx["score"], ctx["ok"]
    m = ok & ~np.isnan(s)
    pool = np.where(m)[0]
    w_out = np.zeros(len(s))
    if len(pool) < 40:
        return w_out
    # محدود به ۳۵۰ نماد نقدشونده‌تر برای سرعت و پایداری
    if len(pool) > 350 and ctx.get("adv") is not None:
        pool = pool[np.argsort(-np.nan_to_num(ctx["adv"][pool]))[:350]]
    C = _cov(ctx, pool)
    if C is None:
        w_out[pool] = 1 / len(pool)
        return w_out
    n = len(pool)
    b = np.full(n, 1 / n)
    sd = np.sqrt(np.diag(C))
    alpha = ic * sd * np.clip(s[pool], -3, 3)
    L = np.linalg.cholesky(C + 1e-10 * np.eye(n))
    w = cp.Variable(n, nonneg=True)
    w0 = ctx["prev"][pool] if ctx.get("prev") is not None else b
    w0 = w0 / w0.sum() if w0.sum() > 0 else b
    cons = [cp.sum(w) == 1, w <= max(max_w, 2.0 / n), cp.norm(L.T @ (w - b), 2) <= te_max / np.sqrt(12)]
    obj = alpha @ w - lam / 2 * cp.sum_squares(L.T @ w) - tau_bp / 1e4 * cp.norm1(w - w0)
    prob = cp.Problem(cp.Maximize(obj), cons)
    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception:  # noqa: BLE001
        prob = cp.Problem(cp.Maximize(obj), cons[:2])
        prob.solve(solver=cp.CLARABEL)
    if w.value is None:
        w_out[pool] = b
        return w_out
    v = np.maximum(w.value, 0)
    w_out[pool] = v / v.sum()
    return w_out


# ═══════════════════ بک‌تست ═══════════════════
def backtest(lab: Lab, spec: dict, keep_weights: int = 0, live: bool = True):
    mk = lab.mk
    algo_ = ALGOS[spec["algo"]]
    params = {**{k: v for k, v in algo_["params"].items()}, **spec.get("params", {})}
    univ = spec.get("universe", {})
    markets = set(univ.get("markets", ["bourse", "farabourse"]))
    min_adv = univ.get("min_adv", 0)
    every = int(spec.get("rebalance_every", 1))
    kappa = float(spec.get("partial", 1.0))
    max_w = spec.get("max_w")
    cost = float(spec.get("cost_bp", 100)) / 1e4
    delay = int(spec.get("delay", 0))
    k = mk.k
    mk_ok = np.isin(mk.market, list(markets))
    adv_all = None
    prev_w = np.zeros(k)               # وزن رانش‌یافتهٔ دورهٔ قبل
    held = np.zeros(k, bool)
    out = {"end": [], "sig_date": [], "S": [], "ALL": [], "CAP": [], "to": [], "n": [], "ic": [], "w": [], "impact": {a_: [] for a_ in AUMS}}
    prev_all = None
    prev_cap = None
    to_all, to_cap = [], []
    def capweights(ok_, a_):
        mc = np.where(ok_, np.nan_to_num(mk.mcap[a_]), 0.0)
        return mc / mc.sum() if mc.sum() > 0 else mc
    first = True
    cnt = 0
    for r in lab.use:
        a, b = lab.me[r], lab.me[r + 1]
        if (cnt % every) != 0 and not first:
            # ماه بدون ریبالانس: وزن‌ها رانش می‌کنند
            f = mk.fwd(a, b, delay)
            ok = lab.ok[r] & mk_ok
            g = np.where(np.isnan(f), 0, f)
            ret = float((prev_w * g).sum())
            out["end"].append(mk.dates[min(b + delay, mk.n - 1)]); out["sig_date"].append(mk.dates[a])
            out["S"].append(ret); out["to"].append(0.0); out["n"].append(int((prev_w > 0).sum()))
            allw = ok / max(ok.sum(), 1)
            out["ALL"].append(float((allw * g).sum()))
            out["ic"].append(np.nan)
            to_all.append(0.0)
            prev_all = allw * (1 + g)
            prev_all = prev_all / prev_all.sum() if prev_all.sum() > 0 else prev_all
            cw = capweights(ok, a)
            out["CAP"].append(float((cw * g).sum())); to_cap.append(0.0)
            prev_cap = cw * (1 + g); prev_cap = prev_cap / prev_cap.sum() if prev_cap.sum() > 0 else prev_cap
            for a_ in AUMS:
                out["impact"][a_].append(0.0)
            prev_w = prev_w * (1 + g)
            prev_w = prev_w / prev_w.sum() if prev_w.sum() > 0 else prev_w
            cnt += 1
            continue
        cnt += 1
        ok = lab.ok[r] & mk_ok
        if min_adv > 0:
            v = sg.W(mk.val, a, 63)
            adv = np.nanmean(v, axis=0) if v is not None else np.full(k, np.nan)
            ok = ok & (np.nan_to_num(adv) >= min_adv)
        else:
            adv = None
        sc = lab.score(spec, r)
        f = mk.fwd(a, b, delay)
        ctx = {"score": sc, "ok": ok, "held": held, "mk": mk, "a": a, "prev": prev_w, "mcap": np.nan_to_num(mk.mcap[a]),
               "vol": (lambda Z: nanstd_safe(Z))(sg.W(mk.X, a, 126)), "adv": adv, "sector": mk.sector}
        w = algo_["fn"](ctx, **params)
        if w.sum() <= 0:
            if first:
                # هنوز هیچ سبدی تشکیل نشده (مثلاً معیار بنیادی پیش از پوشش داده): نمونهٔ این استراتژی از نخستین ماه قابل‌تشکیل
                # شروع می‌شود؛ ثبت نقدِ صفر در برابر مرجع برتری کاذب می‌ساخت
                cnt -= 1
                continue
            # الگوریتم در میانهٔ نمونه پرتفویی نداد (مثلاً کمتر از ۳۰ واجد): سبد قبلی (رانش‌یافته) نگه داشته می‌شود و ماه ثبت می‌شود؛
            # حذف ماه از سری، ردیف‌ها را با lab.use ناهم‌تراز می‌کرد و برنامهٔ rebalance_every را جابه‌جا
            w = prev_w.copy()
        else:
            if max_w:
                w = _cap(w, max_w)
            if kappa < 1.0 and prev_w.sum() > 0:
                w = prev_w + kappa * (w - prev_w)
                w = np.maximum(w, 0)
                w /= w.sum()
        held = w > 0
        to = np.nan if first else 0.5 * np.abs(w - prev_w).sum()
        g = np.where(np.isnan(f), 0, f)
        ret = float((w * g).sum())
        allw = ok / max(ok.sum(), 1)
        out["end"].append(mk.dates[min(b + delay, mk.n - 1)]); out["sig_date"].append(mk.dates[a])
        out["S"].append(ret); out["to"].append(to); out["n"].append(int((w > 0).sum()))
        out["ALL"].append(float((allw * g).sum()))
        to_all.append(np.nan if prev_all is None else 0.5 * np.abs(allw - prev_all).sum())
        prev_all = allw * (1 + g)
        prev_all = prev_all / prev_all.sum() if prev_all.sum() > 0 else prev_all
        cw = capweights(ok, a)
        out["CAP"].append(float((cw * g).sum()))
        to_cap.append(np.nan if prev_cap is None else 0.5 * np.abs(cw - prev_cap).sum())
        prev_cap = cw * (1 + g); prev_cap = prev_cap / prev_cap.sum() if prev_cap.sum() > 0 else prev_cap
        # اثر بازار: هر نماد Δw·AUM را در ADV۶۳ روزه معامله می‌کند؛ هزینهٔ یک‌طرفه Yσ√(مشارکت) (σ روزانه)
        if first:
            for a_ in AUMS:
                out["impact"][a_].append(np.nan)
        else:
            vv = sg.W(mk.val, a, 63)
            advv = np.nan_to_num(np.nanmean(vv, axis=0)) if vv is not None else np.zeros(k)
            sgm = np.nan_to_num(ctx["vol"]) if len(ctx["vol"]) == k else np.zeros(k)
            dw = np.abs(w - prev_w)
            for a_ in AUMS:
                part = np.where(advv > 0, dw * a_ / np.maximum(advv, 1), 0.0)
                out["impact"][a_].append(float((dw * Y_IMPACT * sgm * np.sqrt(np.minimum(part, 1.0))).sum()))
        m = ok & ~np.isnan(sc) & ~np.isnan(f)
        out["ic"].append(sg.spearman_rows(sc, np.where(m, f, np.nan)) if m.sum() > 30 else np.nan)
        if keep_weights:
            out["w"].append((r, w.copy()))
        prev_w = w * (1 + g)
        prev_w = prev_w / prev_w.sum() if prev_w.sum() > 0 else prev_w
        if w.sum() > 0:
            first = False                               # تا نخستین سبد واقعی، گردش ماه بعد «ساخت اولیه» است نه گردش
    res = {"end": out["end"], "sig_date": out["sig_date"],
           "ret": {"S": np.array(out["S"]), "ALL": np.array(out["ALL"]), "CAP": np.array(out["CAP"])},
           "to": {"S": np.array(out["to"], float), "ALL": None, "CAP": np.array(to_cap, float)},
           "impact": {a_: np.array(v, float) for a_, v in out["impact"].items()},
           "n": {"S": float(np.mean(out["n"])) if out["n"] else 0, "ALL": 0.0},
           "ic": np.array(out["ic"], float), "ngroups": 0, "tops": {}, "spec": spec}
    res["to"]["ALL"] = np.array(to_all, float)          # ALL = هم‌وزن واجدان با ریبالانس ماهانه؛ گردش واقعی
    if keep_weights:
        res["weights"] = out["w"]
    if live:
        res["live"] = live_target(lab, spec, algo_, params, prev_w, held, ok_univ=(mk_ok, min_adv))
    return res


def nanstd_safe(Z):
    if Z is None:
        return np.full(1, np.nan)
    return sg.nanstd(Z)


def live_target(lab, spec, algo_, params, prev_w, held, ok_univ):
    """وزن هدف در آخرین روز داده (برای فهرست اقدام): از وزن رانش‌یافتهٔ آخرین ریبالانس تا امروز."""
    mk = lab.mk
    a = mk.n - 1
    r = len(lab.idx) - 1
    # رانش از آخرین پایان ماه (که بک‌تست تا آن رانش داده) تا امروز
    a_last = lab.me[-1]
    seg = mk.X[a_last + 1: a + 1]
    g = np.nanprod(1 + np.nan_to_num(seg), axis=0) - 1 if len(seg) else np.zeros(mk.k)
    drift = prev_w * (1 + g)
    drift = drift / drift.sum() if drift.sum() > 0 else prev_w
    ok = mk.eligible(a) & ok_univ[0]
    if ok_univ[1] > 0:
        v = sg.W(mk.val, a, 63)
        ok = ok & (np.nan_to_num(np.nanmean(v, axis=0)) >= ok_univ[1])
    sc = lab.score(spec, r, live=True)
    ctx = {"score": sc, "ok": ok, "held": held, "mk": mk, "a": a, "prev": drift, "mcap": np.nan_to_num(mk.mcap[a]),
           "vol": nanstd_safe(sg.W(mk.X, a, 126)), "adv": None, "sector": mk.sector}
    w = algo_["fn"](ctx, **params)
    if spec.get("max_w") and w.sum() > 0:
        w = _cap(w, spec["max_w"])
    return {"date": mk.dates[a], "target": w, "current_drift": drift, "score": sc}
