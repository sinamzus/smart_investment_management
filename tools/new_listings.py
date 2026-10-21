#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نمادهای تازه‌پذیرش بزرگ در همتای «شاخص كل» (فصل ۳ «تأخیر ورود عرضهٔ اولیه»، تصمیم مالک ۲۰۲۶-۱۰-۲۱).

«شاخص كل» رسمی نماد تازه را از روز پس از نخستین معامله با وزن ارزش بازار می‌شمارد، ولی واجدیت همتا سابقهٔ ۲۵۲ روزه
می‌خواهد؛ پس رشد روزهای صف خرید پس از عرضهٔ اولیه (مثلاً «تابان» ۱۴۰۵: ۱۵ روز +۳٪) در همتا نبود. قواعد:
  • هدف و همتای کامل: نماد تازه از روز پس از نخستین معامله با وزن ارزش بازار در هدف است (new_in).
  • همتای N سهمی: نماد تازهٔ «بزرگ» (وزن روز دوم ≥ THRESH) بیرون از بهینه‌ساز با وزن شاخص نگه داشته می‌شود
    (لایهٔ عرضهٔ اولیه)؛ خرید هر روز حداکثر φ × ارزش معاملات همان روز (در روزهای صف خرید هم، چون بخشی از صف پر می‌شود)
    نسبت به اندازهٔ صندوق؛ تا ماهی که نماد طبق قاعدهٔ عادی واجد شود، سپس به انتخاب عادی سپرده می‌شود.
سود نقدی نماد تازه در سال اول نادیده گرفته می‌شود (معمولاً نیست).
"""
import numpy as np

THRESH = 0.003          # وزن روز دوم در «شاخص كل» برای «بزرگ» [انتخاب طراحی]
PHI = 0.02              # سهم پیش‌فرض صندوق از ارزش معاملات روزانهٔ نماد [تأیید لازم: جای صندوق در صف نامعلوم است]
AUM_BN = 1000.0         # اندازهٔ مرجع صندوق در جدول پایتون (میلیارد ریال)
HOLD = 40              # روزهای پس از واجدیت عادی که وزن هدف لایه هنوز ساخته می‌شود (تا ریبالانس ماهانهٔ بعد رها شود)


def first_trade(mk) -> np.ndarray:
    traded = np.nan_to_num(mk.val) > 0
    return np.where(traded.any(0), traded.argmax(0), -1)


def new_in(mk, t, ok, first=None) -> np.ndarray:
    """نمادهای بورسی که پیش از روز t−1 معامله شده‌اند ولی هنوز طبق قاعدهٔ عادی واجد نیستند (برای وزن هدف روز t)."""
    first = first_trade(mk) if first is None else first
    mc = np.nan_to_num(mk.mcap[t - 1])
    return ok & (first >= 0) & (first < t - 1) & (mc > 0) & ~mk.eligible(t - 1, require_trade=False)


def full_target(mk, t, ok, first=None):
    """(اندیس‌ها، وزن) هدف کامل روز t: واجدان عادی ∪ نمادهای تازه، وزن ارزش بازار روز قبل."""
    mc = np.nan_to_num(mk.mcap[t - 1])
    m = (mk.eligible(t - 1, require_trade=False) & ok & (mc > 0)) | new_in(mk, t, ok, first)
    idx = np.where(m)[0]
    return idx, (mc[idx] / mc[idx].sum() if len(idx) else np.zeros(0))


def events(mk, ok, start_idx: int, thresh: float = THRESH):
    """رویدادهای نماد تازهٔ بزرگ: [{i, s (نخستین روز خرید = روز پس از نخستین معامله), end (نخستین روز واجدیت عادی یا n)}]."""
    first = first_trade(mk)
    out = []
    for i in np.where(ok & (first >= start_idx - 260))[0]:
        t1 = int(first[i])
        if t1 + 2 >= mk.n:
            continue
        idx, w = full_target(mk, t1 + 2, ok, first)
        pos = np.where(idx == i)[0]
        if not len(pos) or w[pos[0]] < thresh:
            continue
        end = next((t for t in range(t1, mk.n) if mk.eligible(t, require_trade=False)[i]), mk.n)
        out.append({"i": int(i), "s": t1 + 1, "end": int(end)})
    return out


def weights(mk, ev, ok, first=None) -> dict:
    """وزن هدف روزانهٔ هر رویداد در «شاخص كل» (هدف کامل): {i: آرایهٔ n}."""
    first = first_trade(mk) if first is None else first
    W = {e["i"]: np.zeros(mk.n) for e in ev}
    for t in range(1, mk.n):
        act = [e["i"] for e in ev if e["s"] <= t < e["end"] + HOLD]
        if not act:
            continue
        idx, w = full_target(mk, t, ok, first)
        d = dict(zip(idx.tolist(), w))
        for i in act:
            W[i][t] = d.get(i, 0.0)
    return W
