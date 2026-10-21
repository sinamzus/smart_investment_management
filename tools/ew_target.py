#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""هدف «شاخص كل (هم وزن)» برای همتاساز (فصل ۳ «همتای هم‌وزن»، درخواست مالک ۲۰۲۶-۱۰-۲۱).

همان روش بازسازی هم‌وزن §۳٫۴ (rebuild_ew_rebalanced، TE ۰٫۶۳٪ در برابر سری رسمی): همهٔ سهام بورس با وزن برابر در آغاز هر فصل
شمسی، رانش با بازده تا فصل بعد؛ نماد بی‌داده در آن روز وزن صفر و بقیه بازنرمال؛ روز نخستین معامله کنار است (قاعدهٔ ۳ فصل ۲).
نماد تازه در ریبالانس فصل بعد وارد می‌شود (لایهٔ عرضهٔ اولیه لازم نیست: وزن هر نماد ≈ ۱/۴۰۰).
"""
import numpy as np

import rebuild_ew_rebalanced as ewr

OFFICIAL_TR = "67130298613737946"          # «شاخص كل (هم وزن)» بازده کل (rebuild_ew_index.OFFICIAL["TR"])


def ew_path(mk, ok, keep=()):
    """(C، B): بازده روزانهٔ همتای هم‌وزن کامل و وزن‌های پایان روز برای روزهای keep (برای ریبالانس ماهانهٔ همتا در همان روز)."""
    flags = ewr.rebalance_flags(mk.dates, "jalali-quarter")
    X = mk.X
    n, k = X.shape
    keep = set(int(x) for x in keep)
    w = np.zeros(k)
    C = np.zeros(n)
    B = {}
    for t in range(1, n):
        avail = ok & ~np.isnan(X[t])
        if not avail.any():
            continue
        if flags[t] or w.sum() == 0:
            w = avail.astype(float)
        else:
            w = np.where(avail, w, 0.0)
            if w.sum() == 0:
                w = avail.astype(float)
        w = w / w.sum()
        r = np.where(avail, np.nan_to_num(X[t]), 0.0)
        rp = float(w @ r)
        C[t] = rp
        w = w * (1 + r) / (1 + rp)
        if t in keep:
            B[t] = w.copy()
    return C, B
