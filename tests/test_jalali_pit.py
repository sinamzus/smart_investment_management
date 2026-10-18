# -*- coding: utf-8 -*-
"""آزمون‌های دستهٔ دوم ممیزی: تقویم جلالی مشترک (B9)، زمان دانستن point-in-time (A3)، واجدیت بدون نگاه به آینده (A4)،
سالانه‌سازی تقویمی (B8). اجرا:  python -m unittest discover -s tests -v"""
import datetime as dt
import sys
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import jalali  # noqa: E402
import build_quality as bq  # noqa: E402
import signals as sg  # noqa: E402
import fetch_corporate_actions as fca  # noqa: E402
import fetch_index_funds as fif  # noqa: E402
from rebuild_ew_rebalanced import g2j  # noqa: E402


class Jalali(unittest.TestCase):
    def test_roundtrip_every_day_2009_2030(self):
        d = dt.date(2009, 1, 1)
        while d <= dt.date(2030, 12, 31):
            jy, jm, jd = jalali.g2j(d.year, d.month, d.day)
            self.assertEqual(jalali.j2g(jy, jm, jd), d, d)
            d += dt.timedelta(days=1)

    def test_leap_years(self):
        self.assertTrue(jalali.is_leap(1399)); self.assertTrue(jalali.is_leap(1403)); self.assertTrue(jalali.is_leap(1408))
        for y in (1400, 1401, 1402, 1404, 1405):
            self.assertFalse(jalali.is_leap(y), y)
        self.assertEqual(jalali.month_length(1403, 12), 30); self.assertEqual(jalali.month_length(1402, 12), 29)

    def test_invalid_dates_raise_and_lenient_clamps(self):
        with self.assertRaises(ValueError):
            jalali.j2g(1402, 12, 30)
        with self.assertRaises(ValueError):
            jalali.j2g(1404, 7, 31)
        with self.assertRaises(ValueError):
            jalali.j2g(1404, 13, 1, strict=False)
        self.assertEqual(jalali.j2g(1402, 12, 30, strict=False), dt.date(2024, 3, 19))   # = ۱۴۰۲/۱۲/۲۹
        self.assertEqual(jalali.j2g(1404, 7, 31, strict=False), jalali.j2g(1404, 7, 30))

    def test_known_dates(self):
        self.assertEqual(jalali.j2g(1395, 1, 1), dt.date(2016, 3, 20))
        self.assertEqual(jalali.j2g(1403, 12, 30), dt.date(2025, 3, 20))
        self.assertEqual(jalali.parse_j("۱۴۰۵/۰۷/۲۹"), dt.date(2026, 10, 21))
        self.assertEqual(g2j(2026, 10, 21), (1405, 7, 29))

    def test_wrappers_keep_signatures(self):
        self.assertEqual(fca.j2g(1403, 12, 30), "2025-03-20")
        with self.assertRaises(ValueError):
            fca.j2g(1402, 12, 30)                          # strict: audit_corporate_actions.cv و build_quality.safe_fy_date روی این حساب می‌کنند
        self.assertEqual(fca.jalali_text_to_iso("۱۴۰۲/۱۲/۳۰"), "2024-03-19")   # متن خراش‌شده: بُرش
        self.assertEqual(fif.j2g(1402, 12, 30), dt.date(2024, 3, 19))         # lenient
        self.assertEqual(fif.to_date("1402/12/30"), "2024-03-19")
        self.assertIsNone(fif.to_date("1402/13/01"))
        self.assertEqual(bq.safe_fy_date("1402/12/30"), pd.Timestamp("2024-03-19"))


class PointInTime(unittest.TestCase):
    def test_rahavard_avail_is_never_before_version_date(self):
        first = pd.Timestamp("2023-07-01")                  # نخستین اعلام EPS
        # نسخهٔ تجدیدارائه‌شده ۱۵ ماه بعد: مقدار پیش از تاریخ نسخه دیده نمی‌شود
        self.assertEqual(bq.rahavard_avail(first, "1403/3/13"), pd.Timestamp(jalali.j2g(1403, 3, 13)))
        # نسخهٔ اولیه زودتر از اعلام EPS: اعلام EPS ملاک می‌ماند
        self.assertEqual(bq.rahavard_avail(first, "1402/3/1"), first)
        # چند مؤلفه با تاریخ‌های مختلف: دیرترین (مقایسهٔ تاریخی، نه رشته‌ای: «1403/3/13» < «1403/12/1»)
        self.assertEqual(bq.rahavard_avail(first, "1403/3/13", "1403/12/1"), pd.Timestamp(jalali.j2g(1403, 12, 1)))
        self.assertTrue(pd.isna(bq.rahavard_avail(pd.NaT, "", None)))

    def test_fund_at_hides_value_before_avail(self):
        g = pd.DataFrame({"ins_code": ["a", "a"], "fy_end": pd.to_datetime(["2023-03-20", "2024-03-19"]),
                          "value": [10.0, 20.0], "avail": pd.to_datetime(["2023-07-02", "2025-06-01"])})
        mk = types.SimpleNamespace(fund={"roe": g}, k=1, cols=pd.Index(["a"]), dates=pd.DatetimeIndex(["2023-01-01", "2024-08-01", "2025-07-01"]))
        self.assertTrue(np.isnan(sg._fund_at(mk, "roe", 0)[0]))     # پیش از هر اعلام
        self.assertEqual(sg._fund_at(mk, "roe", 1)[0], 10.0)        # ۱۴۰۳ هنوز اعلام نشده (avail بعد از تاریخ)
        self.assertEqual(sg._fund_at(mk, "roe", 2)[0], 20.0)


class ForwardReturn(unittest.TestCase):
    def test_fwd_needs_only_execution_day(self):
        X = np.array([[0.01, 0.01], [0.02, np.nan], [0.03, 0.03], [np.nan, 0.01]])   # نماد ۱: روز اجرا بی‌داده؛ نماد ۰: پایان دوره بی‌داده
        mk = types.SimpleNamespace(X=X, n=4)
        f = sg.Market.fwd(mk, 0, 3)
        self.assertTrue(np.isnan(f[1]))                              # بدون قیمت روز اجرا ⇒ قابل خرید نیست
        self.assertAlmostEqual(f[0], (1.02 * 1.03) - 1)              # روز بی‌دادهٔ پایان دوره = بازده صفر (منجمد)، نه حذف از جهان


class Annualization(unittest.TestCase):
    def test_sampled_replica_uses_calendar_years(self):
        import sampled_replica as sr
        idx = pd.bdate_range("2020-03-20", periods=3 * 252)             # ≈ ۳ سال معاملاتی، ولی تقویمی ۲٫۸۸ سال
        s = pd.Series(np.linspace(1, 2, len(idx)), index=idx)
        K = pd.Series(0.0, index=idx)
        ev = sr.evaluate(s, K, K)
        yrs = (idx[-1] - idx[0]).days / 365.25
        self.assertAlmostEqual(ev["ann_pct"], 100 * (2 ** (1 / yrs) - 1), places=6)


if __name__ == "__main__":
    unittest.main()
