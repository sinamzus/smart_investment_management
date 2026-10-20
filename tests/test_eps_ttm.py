# -*- coding: utf-8 -*-
"""EPS دوازده ماه اخیر (signals.ttm_parts، معیار ep_ttm؛ فصل ۱۴ §۱۴٫۳٫۴): انباشته، point-in-time، آخرین نسخه.

    python -m unittest tests.test_eps_ttm -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import signals as sg  # noqa: E402

# سال مالی منتهی به ۲۰۲۵-۰۳-۲۰ و ۲۰۲۶-۰۳-۲۰؛ EPS میان‌دوره‌ای انباشته (مثل رهاورد)
ROWS = [("A", "2025-03-20", 3, "2024-07-20", 248), ("A", "2025-03-20", 6, "2024-10-21", 524), ("A", "2025-03-20", 6, "2025-01-25", 502),
        ("A", "2025-03-20", 9, "2025-01-19", 636), ("A", "2025-03-20", 12, "2025-07-31", 664),
        ("A", "2026-03-20", 3, "2025-07-21", 108), ("A", "2026-03-20", 6, "2025-10-22", 201), ("A", "2026-03-20", 9, "2026-01-20", 295),
        ("B", "2026-03-20", 9, "2026-01-20", 50),                     # B: سال قبلش نیست
        ("D", "2025-03-20", 12, "2025-06-01", 80)]                    # D: فقط سالانه


def Q():
    E = pd.DataFrame(ROWS, columns=["ins_code", "fy", "period", "date", "eps"])
    E["fy"], E["date"] = pd.to_datetime(E.fy), pd.to_datetime(E.date)
    return sg.clamp_period(E).sort_values("date")


def ttm(t, code="A"):
    P = sg.ttm_parts(Q(), t)
    P = P[P.ins_code == code]
    return float((P.eps * P.sign).sum()) if len(P) else None


class EpsTTM(unittest.TestCase):
    def test_nine_months(self):
        self.assertEqual(ttm("2026-02-15"), 295 + 664 - 636)

    def test_latest_version_of_prior_period(self):
        # ۶ ماههٔ سال قبل دو نسخه دارد (۵۲۴ اولیه، ۵۰۲ حسابرسی‌شده)؛ در ۲۰۲۵-۱۱-۱۵ هر دو دانسته‌اند ⇒ ۵۰۲
        self.assertEqual(ttm("2025-11-15"), 201 + 664 - 502)

    def test_point_in_time(self):
        # پیش از اعلام ۹ ماهه (۲۰۲۶-۰۱-۲۰) هنوز ۶ ماهه
        self.assertEqual(ttm("2026-01-19"), 201 + 664 - 502)

    def test_three_months_right_after_annual(self):
        # ۳ ماههٔ سال جدید (۲۰۲۵-۰۷-۲۱) پیش از سالانهٔ قبلی (۲۰۲۵-۰۷-۳۱) اعلام شده؛ هر دو دانسته‌اند
        self.assertEqual(ttm("2025-08-01"), 108 + 664 - 248)

    def test_annual_is_used_directly(self):
        self.assertEqual(ttm("2025-08-01", "D"), 80)

    def test_missing_prior_year_has_no_ttm(self):
        self.assertIsNone(ttm("2026-02-15", "B"))   # نه جزء سال قبل، نه EPS سالانه

    def test_clamp_period_end(self):
        E = pd.DataFrame([("C", "2026-03-20", 9, "2025-12-01", 10)], columns=["ins_code", "fy", "period", "date", "eps"])
        E["fy"], E["date"] = pd.to_datetime(E.fy), pd.to_datetime(E.date)
        self.assertEqual(sg.clamp_period(E).date.iloc[0], pd.Timestamp("2025-12-21"))   # پایان دورهٔ ۹ ماهه + ۱ روز


if __name__ == "__main__":
    unittest.main()
