#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیک فاکتوری برتری (Factor attribution) — فصل ۱۴ §۱۴٫۷٫۸.

برتری ناخالص ماهانهٔ استراتژی نسبت به هم‌وزن واجدان (S − ALL) روی بازدهٔ چند فاکتور رگرس می‌شود:

    S_t − ALL_t = α + Σ_f β_f · F_f,t + e_t

فاکتورها (همه ماهانه، ناخالص، با همان جهان و زمان‌بندی Lab):
  MKT    بازار: بازدهٔ هم‌وزن واجدان (ALL). β_MKT ≠ ۰ یعنی استراتژی نسبت به بازار اهرم/حساسیت متفاوت دارد.
  SIZE   اندازهٔ کوچک: سبد top-fraction معیار `size` منهای ALL.
  LOWVOL کم‌نوسان: سبد top-fraction معیار `vol_252` منهای ALL.
  DIV    بازده نقدی سود: سبد top-fraction معیار `div_yield` منهای ALL.
  MOM    مومنتوم ۱۲−۱: سبد top-fraction معیار `mom_12_1` منهای ALL.
هر فاکتور همان ردیف تک‌معیار کتابخانه (`sig:<معیار>`) است؛ فقط‌خرید و قابل‌ساخت، ولی سهم مشترکشان با استراتژی‌ها زیاد است، پس β تفسیر
«شباهت به سبد آن معیار» دارد نه بار خالص روی یک پریمیوم مستقل. ارزش و کیفیت (۳۹ تا ۵۵ ماه) وارد نمی‌شوند.

سهم هر جزء از میانگین برتری (سالانهٔ حسابی، ×۱۲): α·۱۲ + Σ β_f·mean(F_f)·۱۲ = mean(S − ALL)·۱۲ (دقیق، چون رگرسیون عرض از مبدأ دارد)؛
هزینه جداگانه: −mean(گردش_S·c − گردش_ALL·c)·۱۲ ⇒ جمع = برتری خالص حسابی. خطای معیار ضرایب: نیوی‌وست (HAC) با ۳ وقفه.
"""
from __future__ import annotations

import numpy as np

FACTORS = [("MKT", "بازار (هم‌وزن واجدان)", None), ("SIZE", "اندازهٔ کوچک", "size"), ("LOWVOL", "کم‌نوسان", "vol_252"),
           ("DIV", "بازده نقدی سود", "div_yield"), ("MOM", "مومنتوم ۱۲−۱", "mom_12_1")]
MIN_MONTHS = 24


def ols_hac(y, X, L: int = 3):
    """OLS با خطای معیار نیوی‌وست (وزن بارتلت 1 − l/(L+1)). X ستون ثابت را خودش ندارد؛ اینجا افزوده می‌شود. خروجی: (b، se، r2)."""
    y = np.asarray(y, float)
    X = np.column_stack([np.ones(len(y)), np.asarray(X, float)])
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ y
    e = y - X @ b
    T = len(y)
    u = X * e[:, None]
    S = u.T @ u
    for l in range(1, L + 1):
        G = u[l:].T @ u[:-l]
        S += (1 - l / (L + 1)) * (G + G.T)
    V = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(V), 0))
    sst = ((y - y.mean()) ** 2).sum()
    r2 = 1 - (e @ e) / sst if sst > 0 else np.nan
    return b, se, float(r2)


def tail_align(*arrs):
    """هم‌ترازی از انتها: همهٔ اجراهای Lab تا آخرین ماه پیوسته‌اند و فقط ماه‌های آغازین ممکن است کم باشند (معیار بنیادی، تأخیر اجرا)."""
    n = min(len(a) for a in arrs)
    return [np.asarray(a, float)[len(a) - n:] for a in arrs]


def factor_series(get_run):
    """get_run(signal_name) → (ret_S, ret_ALL) ناخالص ماهانهٔ ردیف تک‌معیار کتابخانه. خروجی: {کد: آرایه} + ALL مرجع."""
    out = {}
    base_all = None
    for code, _, sig in FACTORS:
        if sig is None:
            continue
        s, a = get_run(sig)
        out[code] = np.asarray(s, float) - np.asarray(a, float)
        base_all = np.asarray(a, float) if base_all is None else base_all
    out["MKT"] = base_all
    return out


def attribute(ret_s, ret_all, to_s, to_all, cost_bp, fac: dict):
    """تفکیک برتری یک استراتژی. ret/to آرایه‌های ماهانهٔ همان اجرا؛ fac خروجی factor_series. خروجی قابل JSON."""
    codes = [c for c, _, _ in FACTORS]
    arrs = tail_align(ret_s, ret_all, to_s, to_all, *[fac[c] for c in codes])
    rs, ra, ts, ta, F = arrs[0], arrs[1], arrs[2], arrs[3], np.column_stack(arrs[4:])
    y = rs - ra
    ok = ~np.isnan(y) & ~np.isnan(F).any(axis=1)
    y, F = y[ok], F[ok]
    c = cost_bp / 1e4
    drag = (np.nan_to_num(ts[ok]) - np.nan_to_num(ta[ok])) * c
    T = len(y)
    if T < MIN_MONTHS:
        return None
    b, se, r2 = ols_hac(y, F)
    self_fac = bool(r2 > 0.9999)                     # استراتژی خودش یکی از فاکتورهاست (مثلاً sig:size): t بی‌معناست
    t = np.where((se > 1e-12) & ~self_fac, b / np.where(se > 1e-12, se, 1), np.nan)
    mF = F.mean(axis=0)
    gross = 12 * 100 * y.mean()
    tf = lambda v: None if v != v else float(v)     # noqa: E731
    rows = [{"code": code, "fa": fa, "beta": float(b[i + 1]), "t": tf(t[i + 1]), "factor_ann": float(12 * 100 * mF[i]),
             "contrib_ann": float(12 * 100 * b[i + 1] * mF[i])} for i, (code, fa, _) in enumerate(FACTORS)]
    return {"months": int(T), "alpha_ann": float(12 * 100 * b[0]), "alpha_t": tf(t[0]), "r2": r2, "self_factor": self_fac, "factors": rows,
            "gross_excess_ann": float(gross), "cost_ann": float(-12 * 100 * drag.mean()),
            "net_excess_ann": float(12 * 100 * (y - drag).mean())}
