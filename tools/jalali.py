# -*- coding: utf-8 -*-
"""تقویم جلالی ↔ میلادی — تنها پیاده‌سازی مخزن (قبلاً سه نسخهٔ جدا بدون اعتبارسنجی وجود داشت).

    from jalali import j2g, g2j, is_leap, month_length, validate
    j2g(1403, 12, 30)              -> datetime.date(2025, 3, 20)
    j2g(1402, 12, 30)              -> ValueError (۱۴۰۲ کبیسه نیست)
    j2g(1402, 12, 30, strict=False) -> date(2024, 3, 19)   (روز به آخرین روز معتبر ماه بُرش می‌خورد؛ برای دادهٔ خراش‌شده)
    g2j(2026, 10, 21)              -> (1405, 7, 29)

الگوریتم همان الگوریتم ۳۳ سالهٔ رایج (jalaali) است که پیشتر در fetch_corporate_actions.j2g و rebuild_ew_rebalanced.g2j به کار می‌رفت؛
کبیسه‌بودن از همان شمارنده مشتق می‌شود تا دو جهت با هم سازگار بمانند. برای ۱۳۹۰ تا ۱۴۱۰ با تقویم رسمی یکی است [تأیید لازم برای سال‌های دورتر].
"""
from __future__ import annotations

import datetime as _dt

_J_DM = (31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29)
_G_DM = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _days_before_year(jy: int) -> int:
    y = jy - 979
    return 365 * y + (y // 33) * 8 + ((y % 33) + 3) // 4


def is_leap(jy: int) -> bool:
    """سال کبیسهٔ جلالی (۳۶۶ روز) بر پایهٔ همان چرخهٔ ۳۳ ساله."""
    return _days_before_year(jy + 1) - _days_before_year(jy) == 366


def month_length(jy: int, jm: int) -> int:
    if not 1 <= jm <= 12:
        raise ValueError(f"ماه جلالی نامعتبر: {jm}")
    return 30 if (jm == 12 and is_leap(jy)) else _J_DM[jm - 1]


def validate(jy: int, jm: int, jd: int) -> None:
    if not 1 <= jd <= month_length(jy, jm):
        raise ValueError(f"تاریخ جلالی نامعتبر: {jy:04d}/{jm:02d}/{jd:02d}")


def j2g(jy: int, jm: int, jd: int, strict: bool = True) -> _dt.date:
    """جلالی → میلادی. strict=True روی تاریخ نامعتبر ValueError می‌دهد؛ strict=False روز را به آخرین روز معتبر ماه می‌بُرد."""
    jy, jm, jd = int(jy), int(jm), int(jd)
    if strict:
        validate(jy, jm, jd)
    else:
        if not 1 <= jm <= 12:
            raise ValueError(f"ماه جلالی نامعتبر: {jm}")
        jd = min(max(jd, 1), month_length(jy, jm))
    j_day = _days_before_year(jy) + sum(_J_DM[: jm - 1]) + (jd - 1)
    g_day = j_day + 79
    gy = 1600 + 400 * (g_day // 146097)
    g_day %= 146097
    leap = True
    if g_day >= 36525:
        g_day -= 1
        gy += 100 * (g_day // 36524)
        g_day %= 36524
        if g_day >= 365:
            g_day += 1
        else:
            leap = False
    gy += 4 * (g_day // 1461)
    g_day %= 1461
    if g_day >= 366:
        leap = False
        g_day -= 1
        gy += g_day // 365
        g_day %= 365
    i = 0
    while g_day >= _G_DM[i] + (1 if i == 1 and leap else 0):
        g_day -= _G_DM[i] + (1 if i == 1 and leap else 0)
        i += 1
    return _dt.date(gy, i + 1, g_day + 1)


def j2g_str(jy: int, jm: int, jd: int, strict: bool = True) -> str:
    return j2g(jy, jm, jd, strict).isoformat()


def g2j(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """میلادی → جلالی (سال، ماه، روز)."""
    gy, gm, gd = int(gy), int(gm), int(gd)
    g_dm = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 + gd + g_dm[gm - 1]
    jy = -1595 + 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def parse_j(text: str, strict: bool = True) -> _dt.date:
    """«1404/07/22» (یا با ارقام فارسی و جداکنندهٔ -) → date."""
    t = str(text).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")).strip()
    parts = t.replace("-", "/").split("/")
    if len(parts) != 3:
        raise ValueError(f"قالب تاریخ جلالی نامعتبر: {text!r}")
    return j2g(*map(int, parts), strict=strict)
