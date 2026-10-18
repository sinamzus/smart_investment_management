# -*- coding: utf-8 -*-
"""آزمون‌های سبک هستهٔ محاسبات (بدون نیاز به دادهٔ مخزن یا cvxpy):  python -m unittest discover -s tests -v

هر آزمون به یک باگ رفع‌شده (ممیزی ۲۰۲۶-۱۰-۱۸) یا یک قرارداد فصل ۸ §۸٫۳ اشاره دارد.
"""
import sys
import types
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import signals as sg  # noqa: E402
import construction as cn  # noqa: E402
import build_quality as bq  # noqa: E402
from rebuild_ew_rebalanced import g2j  # noqa: E402


class JalaliMonthEnd(unittest.TestCase):
    """A1: آخرین روز داده در mk.month_end نیست؛ پایان ماه باید از تقویم تشخیص داده شود."""

    def test_last_trading_day_before_weekend(self):
        # ۱۴۰۵/۰۷/۲۹ = چهارشنبه ۲۰۲۶-۱۰-۲۱؛ ۰۷/۳۰ پنجشنبه است ⇒ ۰۷/۲۹ آخرین روز معاملاتی مهر
        self.assertEqual(g2j(2026, 10, 21), (1405, 7, 29))
        self.assertTrue(sg.is_jalali_month_end(pd.Timestamp("2026-10-21")))
        self.assertFalse(sg.is_jalali_month_end(pd.Timestamp("2026-10-20")))
        self.assertFalse(sg.is_jalali_month_end(pd.Timestamp("2026-10-14")))   # ۰۷/۲۲: پیش‌نویس میان‌ماه

    def test_first_day_of_month_is_not_end(self):
        self.assertEqual(g2j(2026, 10, 23), (1405, 8, 1))
        self.assertFalse(sg.is_jalali_month_end(pd.Timestamp("2026-10-23")))

    def test_calendar_overrides_weekday_rule(self):
        # اگر تقویم بگوید روز بعد (حتی پنجشنبه) معاملاتی است، پایان ماه نیست
        cal = {pd.Timestamp("2026-10-22")}
        self.assertFalse(sg.is_jalali_month_end(pd.Timestamp("2026-10-21"), calendar=cal))
        self.assertTrue(sg.is_jalali_month_end(pd.Timestamp("2026-10-22"), calendar=cal))

    def test_month_end_array_never_contains_last_index(self):
        # قرارداد Market.month_end: اندیس‌های ۰..n−۲ (دلیل باگ A1)
        dates = pd.bdate_range("2026-09-01", "2026-10-21")
        jm = np.array([g2j(d.year, d.month, d.day)[0] * 100 + g2j(d.year, d.month, d.day)[1] for d in dates])
        me = np.where(jm[1:] != jm[:-1])[0]
        self.assertLess(me.max(), len(dates) - 1)


class JalaliCalendar(unittest.TestCase):
    def test_roundtrip_known_dates(self):
        self.assertEqual(g2j(2016, 3, 20), (1395, 1, 1))
        self.assertEqual(g2j(2024, 3, 19), (1402, 12, 29))
        self.assertEqual(g2j(2025, 3, 20), (1403, 12, 30))   # ۱۴۰۳ کبیسه

    def test_is_jdate_accepts_139x(self):
        # B4: تاریخ انتشار کدال برای سال‌های ۱۳۹x نباید رد شود
        self.assertTrue(bq.is_jdate("1398/04/31"))
        self.assertTrue(bq.is_jdate("1400/10/01"))
        self.assertFalse(bq.is_jdate("0000/00/00"))
        self.assertFalse(bq.is_jdate(None))
        self.assertFalse(bq.is_jdate(float("nan")))

    def test_current_jalali_year(self):
        import fetch_dividend_payments as fdp
        self.assertGreaterEqual(fdp.current_jalali_year(), 1405)


class MarketEligibility(unittest.TestCase):
    def test_eligible_before_window_is_all_false(self):
        # C4: اندیس منفی نباید از انتهای آرایه بخواند
        mk = types.SimpleNamespace(k=3, have=np.zeros((10, 3)), nz=np.zeros((10, 3)), X=np.zeros((9, 3)))
        ok = sg.Market.eligible(mk, 5)
        self.assertEqual(ok.dtype, bool)
        self.assertFalse(ok.any())


class CapAndSelection(unittest.TestCase):
    def test_cap_sums_to_one_and_respects_limit(self):
        w = np.array([0.5, 0.3, 0.1, 0.1])
        c = cn._cap(w, 0.3)
        self.assertAlmostEqual(c.sum(), 1.0)
        self.assertLessEqual(c.max(), 0.3 + 1e-9)

    def test_selected_buffer(self):
        s = np.linspace(1, 0, 40)              # نماد ۰ بهترین
        ok = np.ones(40, bool)
        held = np.zeros(40, bool); held[15] = True   # رتبهٔ ۱۶ (درصد ≈ ۰٫۳۹) فقط با بافر می‌ماند
        sel = set(cn._selected({"score": s, "ok": ok, "held": held}, 0.2, 0.4))
        self.assertIn(0, sel); self.assertIn(15, sel); self.assertNotIn(30, sel)


def _has(mod):
    try:
        __import__(mod)
        return True
    except ImportError:
        return False


class CacheSignature(unittest.TestCase):
    @unittest.skipUnless(_has("scipy"), "build_lab به scipy (research_stats) نیاز دارد")
    def test_signature_changes_with_data(self):
        # A2: امضای کش باید با تاریخ یا نمادها عوض شود
        import build_lab as bl
        d1 = pd.DatetimeIndex(["2026-10-01", "2026-10-14"])
        mk1 = types.SimpleNamespace(n=2, k=2, dates=d1, cols=pd.Index(["a", "b"]))
        mk2 = types.SimpleNamespace(n=3, k=2, dates=pd.DatetimeIndex(["2026-10-01", "2026-10-14", "2026-10-15"]), cols=pd.Index(["a", "b"]))
        mk3 = types.SimpleNamespace(n=2, k=2, dates=d1, cols=pd.Index(["a", "c"]))
        s1, s2, s3 = bl.store_signature(mk1), bl.store_signature(mk2), bl.store_signature(mk3)
        self.assertEqual(s1, bl.store_signature(mk1))
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1, s3)


if __name__ == "__main__":
    unittest.main()
