# -*- coding: utf-8 -*-
"""قاعدهٔ ۹ و ۹ب (فصل ۰۲): روز بی‌ردیف نماد زنده پر می‌شود و حرکتش از مبنای ردیف بعد بازیافت می‌شود.

    python -m unittest tests.test_gap_moves -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import rebuild_ew_index as ew  # noqa: E402


def panel(rows):
    P = pd.DataFrame(rows, columns=["ins_code", "date", "pClosing", "priceYesterday"])
    P["date"] = pd.to_datetime(P.date)
    P["zTotTran"] = 1.0
    P["dEven"] = P.date.dt.strftime("%Y%m%d").astype(float)
    P["symbol"] = P.ins_code
    return P


# نماد «Z» همهٔ روزها را دارد تا تقویم کامل باشد
FULL = [("Z", d, 100.0, 100.0) for d in ("2023-03-25", "2023-03-26", "2023-03-27", "2023-03-28", "2023-03-29")]


def filled(P, code, day):
    out = ew.fill_gaps(P, start="2023-01-01")
    return out[(out.ins_code == code) & (out.date == pd.Timestamp(day))].iloc[0]


class GapMoves(unittest.TestCase):
    def test_single_missing_day_gets_the_move(self):
        P = panel(FULL + [("A", "2023-03-26", 8140.0, 7900.0), ("A", "2023-03-28", 8040.0, 8120.0)])
        r = filled(P, "A", "2023-03-27")
        self.assertEqual(r.priceYesterday, 8140.0)
        self.assertEqual(r.pClosing, 8120.0)            # مبنای ردیف بعد
        self.assertEqual(r.zTotTran, 0.0)

    def test_no_move_stays_zero(self):
        P = panel(FULL + [("A", "2023-03-26", 8140.0, 7900.0), ("A", "2023-03-28", 8040.0, 8140.0)])
        self.assertEqual(filled(P, "A", "2023-03-27").pClosing, 8140.0)

    def test_large_move_is_left_as_zero(self):
        P = panel(FULL + [("A", "2023-03-26", 8000.0, 8000.0), ("A", "2023-03-28", 4000.0, 4000.0)])   # −۵۰٪: احتمالاً رویداد
        self.assertEqual(filled(P, "A", "2023-03-27").pClosing, 8000.0)

    def test_two_missing_days_move_on_the_last(self):
        P = panel(FULL + [("A", "2023-03-25", 1000.0, 1000.0), ("A", "2023-03-28", 1050.0, 1030.0)])
        self.assertEqual(filled(P, "A", "2023-03-26").pClosing, 1000.0)
        self.assertEqual(filled(P, "A", "2023-03-27").pClosing, 1030.0)


if __name__ == "__main__":
    unittest.main()
