#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تشخیص ریشهٔ خطای ردیابی صندوق‌های شاخصی (فصل ۳ §۳٫۶): آیا از فاصلهٔ پرداخت سود است یا چیز دیگر؟

مدل (هفتگی، بازده ۵ روزهٔ غیرهم‌پوشان؛ A = بازده فعال = صندوق − مرجع TR):

    A_w = α + c0·(−Rb_w) + c1·(−Rb_w · S_w(L)) + e_w

  Rb_w  بازده هفتگی مرجع
  S_w(L) سهم «سود طلب‌شده و هنوز دریافت‌نشده» از ارزش پرتفو در آغاز هفته = Σ y_s برای روزهای تقویمی (t−L, t]،
         y = بازده سود نقدی روزانهٔ شاخص (r_TR − r_PR). اگر صندوق سود را L روز بعد از استحقاق دریافت کند، طلبش در این مدت
         بازده نمی‌گیرد؛ پس در هفته‌ای که بازار Rb می‌دهد، صندوق به اندازهٔ Rb·S کمتر می‌گیرد (و c1 ≈ ۱ می‌شود).
  c0    کمبود بتای ثابت (نقد نگه‌داشته‌شده، سهام خارج از شاخص، ...): A = −c0·Rb.
  α     اثر ثابت (کارمزد و ...).

L روی شبکه‌ای از ۰ تا ۲۴۰ روز اسکن می‌شود؛ L* با بیشترین R². نتیجه‌ها: c1 (۱ = نظریهٔ تأخیر سود دقیقاً برقرار)، سهم R² که
فقط تأخیر سود توضیح می‌دهد (R² کامل − R² فقط c0)، و TE پس از حذف بخش توضیح‌داده‌شده.
"""
import numpy as np
import pandas as pd

LAGS = (0, 15, 30, 45, 60, 90, 120, 150, 180, 240)


def _ols(X: np.ndarray, y: np.ndarray):
    X1 = np.c_[np.ones(len(y)), X]
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    e = y - X1 @ b
    n, k = X1.shape
    s2 = e @ e / max(n - k, 1)
    cov = s2 * np.linalg.pinv(X1.T @ X1)
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b, np.sqrt(np.diag(cov)), r2, e


def divlag_test(f: pd.Series, b: pd.Series, y: pd.Series) -> dict | None:
    j = pd.concat([f, b], axis=1, join="inner").dropna()
    j.columns = ["f", "b"]
    if len(j) < 150:
        return None
    ycal = y.reindex(pd.date_range(y.index.min(), j.index.max(), freq="D")).fillna(0.0)
    csum = ycal.cumsum()
    blocks = np.arange(len(j)) // 5
    g = j.groupby(blocks)
    A = ((1 + j.f).groupby(blocks).prod() - (1 + j.b).groupby(blocks).prod()).values
    Rb = ((1 + j.b).groupby(blocks).prod() - 1).values
    start = g.apply(lambda d: d.index[0]).values
    scan = []
    for L in LAGS:
        if L == 0:
            S = np.zeros(len(A))
        else:
            hi = csum.reindex(pd.DatetimeIndex(start) - pd.Timedelta(days=1)).values
            lo = csum.reindex(pd.DatetimeIndex(start) - pd.Timedelta(days=1 + L)).values
            S = np.nan_to_num(hi - np.where(np.isnan(lo), 0, lo))
        scan.append((L, S))
    _, _, r2_base, e0 = _ols((-Rb).reshape(-1, 1), A)
    best = None
    rows = []
    for L, S in scan:
        if L == 0:
            continue
        X = np.c_[-Rb, -Rb * S]
        coef, se, r2, e = _ols(X, A)
        rows.append([L, round(float(r2), 4), round(float(coef[2]), 2), round(float(coef[1]), 3), round(float(coef[2] / se[2]), 2)])
        if best is None or r2 > best["r2_full"]:
            best = {"L": L, "r2_full": float(r2), "c1": float(coef[2]), "c0": float(coef[1]), "alpha_wk": float(coef[0]),
                    "t_c1": float(coef[2] / se[2]), "te_resid": float(e.std(ddof=1) * np.sqrt(52) * 100)}
    te_a = float(A.std(ddof=1) * np.sqrt(52) * 100)
    te_a_rob = float(1.4826 * np.median(np.abs(A - np.median(A))) * np.sqrt(52) * 100)
    te_resid_rob = float(1.4826 * np.median(np.abs(e0 - np.median(e0))) * np.sqrt(52) * 100)
    return {"n_weeks": int(len(A)), "te": round(te_a, 2), "te_rob": round(te_a_rob, 2),
            "r2_c0": round(float(r2_base), 4), "te_after_c0": round(float(e0.std(ddof=1) * np.sqrt(52) * 100), 2),
            "best": {k: round(v, 4) if isinstance(v, float) else v for k, v in best.items()},
            "r2_div_only": round(best["r2_full"] - float(r2_base), 4),
            "scan": rows}


def seasonality(f: pd.Series, b: pd.Series, g2j_month) -> dict:
    """میانگین بازده فعال و TE به تفکیک ماه شمسی (برای دیدن تمرکز خطا در فصل سود، خرداد تا مرداد)."""
    j = pd.concat([f, b], axis=1, join="inner").dropna()
    j.columns = ["f", "b"]
    a = j.f - j.b
    jm = np.array([g2j_month(d) for d in j.index])
    jy = np.array([d.year for d in j.index])
    out = {"mean_bp": [], "te": [], "n": []}
    for m in range(1, 13):
        sel = jm == m
        if sel.sum() < 15:
            out["mean_bp"].append(None); out["te"].append(None); out["n"].append(int(sel.sum())); continue
        am = a[sel]
        # بازده فعال ماهانهٔ مرکب، میانگین بین سال‌ها
        per_year = [float((1 + j.f[sel & (jy == y)]).prod() / (1 + j.b[sel & (jy == y)]).prod() - 1) for y in np.unique(jy[sel])]
        out["mean_bp"].append(round(float(np.mean(per_year)) * 1e4, 0))
        out["te"].append(round(float(am.std() * np.sqrt(252) * 100), 2))
        out["n"].append(int(sel.sum()))
    return out
