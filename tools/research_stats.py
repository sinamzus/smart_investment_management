#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""آزمون‌های آماری پژوهش فاکتور (فصل ۱۴ بخش ج): Fama–MacBeth، آستانهٔ t چندگانه، Deflated Sharpe، PBO (CSCV)، White Reality Check و Hansen SPA.

همه روی سری‌های ماهانه‌اند؛ هیچ آزمونی t ساده نمی‌دهد (همیشه نیوی‌وست یا بوت‌استرپ ایستا).
"""
import itertools
import math

import numpy as np
import pandas as pd
from scipy.stats import norm


def nw_t(x, L=3):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 12:
        return np.nan
    e = x - x.mean()
    v = e @ e / T + 2 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T for l in range(1, L + 1))
    return float(x.mean() / np.sqrt(v / T)) if v > 0 else np.nan


# ── Fama–MacBeth ─────────────────────────────────────────────────────────────
def fama_macbeth(lab, name, controls=(), rows=None, use_neutral=False):
    """رگرسیون مقطعی ماهانهٔ بازده ماه بعد بر Zِ معیار (و کنترل‌ها)؛ برمی‌گرداند میانگین شیب، t نیوی‌وست، تعداد ماه.
    شیب = بازده ماهانهٔ پورتفوی «واحد Z» (پریمیوم)؛ کنترل‌ها مثل Fama–French (اندازه، بتا) اثر هم‌خطی را حذف می‌کنند."""
    rows = rows if rows is not None else lab.use
    from signals import neutral as _neu
    betas = []
    for r in rows:
        zs = [lab.z(n, r) for n in (name, *controls)]
        if use_neutral:
            zs = [_neu(np.nan_to_num(z), lab.sector) * np.where(np.isnan(z), np.nan, 1.0) for z in zs]
        y = lab.fw[r]
        A = np.column_stack(zs)
        m = ~np.isnan(A).any(axis=1) & ~np.isnan(y) & lab.ok[r]
        if m.sum() < 60:
            continue
        X = np.column_stack([np.ones(m.sum()), A[m]])
        c, *_ = np.linalg.lstsq(X, y[m], rcond=None)
        betas.append(c[1])
    betas = np.array(betas)
    if len(betas) < 12:
        return {}
    return {"premium_ann": float(betas.mean() * 1200), "t": nw_t(betas), "n": int(len(betas)), "hit": float((betas > 0).mean() * 100)}


# ── آستانهٔ t چندگانه ────────────────────────────────────────────────────────
def bonferroni_t(n_trials, alpha=0.05):
    """آستانهٔ |t| دوطرفه برای سطح خانواده‌ای alpha با n آزمون (تقریب نرمال)."""
    return float(norm.ppf(1 - alpha / (2 * max(n_trials, 1))))


def bhy_pvals(pvals, q=0.05):
    """Benjamini–Hochberg–Yekutieli (وابستگی دلخواه): True برای فرضیه‌های ردشده در FDR=q."""
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    c = np.sum(1 / np.arange(1, n + 1))
    thr = q * np.arange(1, n + 1) / (n * c)
    ok = p[order] <= thr
    k = np.max(np.where(ok)[0]) + 1 if ok.any() else 0
    rej = np.zeros(n, bool)
    rej[order[:k]] = True
    return rej


def t_to_p(t):
    return float(2 * (1 - norm.cdf(abs(t))))


# ── Deflated Sharpe ──────────────────────────────────────────────────────────
def sharpe_stats(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    mu, sd = x.mean(), x.std(ddof=1)
    z = (x - mu) / sd if sd > 0 else x * 0
    return {"sr": float(mu / sd) if sd > 0 else np.nan, "skew": float((z ** 3).mean()), "kurt": float((z ** 4).mean()), "T": len(x)}


def deflated_sharpe(x, trial_sharpes):
    """Bailey & López de Prado (2014): احتمال اینکه Sharpe واقعی > ۰ پس از اصلاح برای انتخاب بهترین از N آزمایش (SR ماهانه)."""
    s = sharpe_stats(x)
    sr, T = s["sr"], s["T"]
    trial_sharpes = np.asarray([t for t in trial_sharpes if t == t], float)
    N = max(len(trial_sharpes), 2)
    v = float(trial_sharpes.var(ddof=1)) if len(trial_sharpes) > 2 else 0.0
    g = 0.5772156649
    sr0 = math.sqrt(v) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))
    den = math.sqrt(max(1 - s["skew"] * sr + (s["kurt"] - 1) / 4 * sr ** 2, 1e-9))
    dsr = float(norm.cdf((sr - sr0) * math.sqrt(T - 1) / den))
    return {"sr_monthly": sr, "sr_annual": sr * math.sqrt(12), "sr0_monthly": sr0, "dsr": dsr, "N": N, "T": T}


# ── PBO (CSCV) ───────────────────────────────────────────────────────────────
def pbo_cscv(Ret, S=16, max_comb=3000, seed=11):
    """Probability of Backtest Overfitting (Bailey, Borwein, López de Prado & Zhu 2017). Ret: T×N بازده فعال ماهانه."""
    T, N = Ret.shape
    S = min(S, (T // 4) * 2)
    edges = np.linspace(0, T, S + 1).astype(int)
    blocks = [Ret[edges[i]:edges[i + 1]] for i in range(S)]
    n_b = np.array([len(b) for b in blocks])
    s1 = np.array([b.sum(axis=0) for b in blocks])
    s2 = np.array([(b ** 2).sum(axis=0) for b in blocks])
    combos = list(itertools.combinations(range(S), S // 2))
    rng = np.random.default_rng(seed)
    if len(combos) > max_comb:
        combos = [combos[i] for i in rng.choice(len(combos), max_comb, replace=False)]

    def sharpe(ix):
        n = n_b[list(ix)].sum()
        a, b = s1[list(ix)].sum(axis=0), s2[list(ix)].sum(axis=0)
        mu = a / n
        sd = np.sqrt(np.maximum(b / n - mu ** 2, 1e-18) * n / (n - 1))
        return mu / sd
    logits, oos_best, deg = [], [], []
    for c in combos:
        rest = [i for i in range(S) if i not in c]
        is_, oos = sharpe(c), sharpe(rest)
        k = int(np.argmax(is_))
        rank = (oos < oos[k]).sum() + 0.5 * ((oos == oos[k]).sum() - 1)
        w = (rank + 1) / (N + 1)
        logits.append(math.log(w / (1 - w)))
        oos_best.append(oos[k])
        deg.append((is_[k], oos[k]))
    logits = np.array(logits)
    deg = np.array(deg)
    slope = float(np.polyfit(deg[:, 0], deg[:, 1], 1)[0]) if len(deg) > 10 else np.nan
    return {"pbo": float((logits <= 0).mean()), "n_comb": len(combos), "oos_best_mean": float(np.mean(oos_best) * math.sqrt(12)),
            "is_oos_slope": slope, "N": N, "T": T, "S": S}


# ── White Reality Check و Hansen SPA ───────────────────────────────────────────
def _stationary_idx(T, B, block, rng):
    out = np.empty((B, T), int)
    p = 1 / block
    for b in range(B):
        i = rng.integers(0, T)
        for t in range(T):
            out[b, t] = i
            i = rng.integers(0, T) if rng.random() < p else (i + 1) % T
    return out


def reality_check(D, B=1000, block=3, seed=3):
    """D: T×N بازده فعال هر استراتژی نسبت به مرجع (ماهانه). p-value آزمون «هیچ استراتژی از مرجع بهتر نیست» (White 2000) و SPA (Hansen 2005)."""
    T, N = D.shape
    rng = np.random.default_rng(seed)
    dbar = D.mean(axis=0)
    idx = _stationary_idx(T, B, block, rng)
    boot = np.stack([D[i].mean(axis=0) for i in idx])                 # B×N
    om = np.sqrt(((boot - dbar) ** 2).mean(axis=0) * T) + 1e-12          # انحراف معیار بوت‌استرپ √T d̄
    v_rc = float(np.sqrt(T) * dbar.max())
    rc = float(((np.sqrt(T) * (boot - dbar)).max(axis=1) >= v_rc).mean())
    # SPA: استیودنت‌شده با میانگین بازنشانده‌شده برای مدل‌های ضعیف
    t_spa = float(max(0.0, (np.sqrt(T) * dbar / om).max()))
    mu_c = np.where(np.sqrt(T) * dbar / om >= -np.sqrt(2 * math.log(math.log(T))), dbar, 0.0)
    stat = np.maximum(0.0, (np.sqrt(T) * (boot - mu_c) / om).max(axis=1))     # Hansen (2005): بازمرکزی با g(d̄)، مدل‌های ضعیف صفر
    spa = float((stat >= t_spa).mean())
    return {"rc_p": rc, "spa_p": spa, "best_idx": int(np.argmax(dbar)), "best_mean_ann": float(dbar.max() * 1200), "N": N, "T": T}
