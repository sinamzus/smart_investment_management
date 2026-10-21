# -*- coding: utf-8 -*-
"""هدف «شاخص كل (هم وزن)» همتاساز (tools/ew_target.ew_path؛ فصل ۳ «همتای هم‌وزن»).

    python -m unittest tests.test_ew_target -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ew_target as et  # noqa: E402


def mk_of(X, start="2025-03-15"):
    return SimpleNamespace(dates=pd.bdate_range(start, periods=len(X)), X=np.asarray(X, float))


class EwTarget(unittest.TestCase):
    def test_equal_then_drift(self):
        X = [[0, 0], [0.10, 0.0], [0.0, 0.0]]                 # ۲۰۲۵-۰۳-۱۷ و ۱۸: درون یک فصل شمسی (اسفند)
        mk = mk_of(X)
        C, B = et.ew_path(mk, np.array([True, True]), keep=[1, 2])
        self.assertAlmostEqual(C[1], 0.05)                    # وزن برابر ⇒ میانگین
        self.assertAlmostEqual(B[1][0], 0.55 / 1.05)          # رانش پس از +۱۰٪
        self.assertAlmostEqual(B[2][0], B[1][0])

    def test_quarter_resets_to_equal(self):
        # ۲۰۲۵-۰۳-۲۰ پایان اسفند، ۲۰۲۵-۰۳-۲۱ آغاز فروردین (فصل تازه)
        mk = SimpleNamespace(dates=pd.DatetimeIndex(["2025-03-18", "2025-03-19", "2025-03-21", "2025-03-22"]),
                             X=np.array([[0, 0], [0.10, 0.0], [0.0, 0.0], [0.0, 0.0]], float))
        C, B = et.ew_path(mk, np.array([True, True]), keep=[1, 2])
        self.assertNotAlmostEqual(B[1][0], 0.5)
        self.assertAlmostEqual(B[2][0], 0.5)                  # آغاز فصل: دوباره برابر

    def test_unavailable_name_gets_zero(self):
        mk = mk_of([[0, 0, 0], [0.03, np.nan, 0.0]])
        C, B = et.ew_path(mk, np.array([True, True, True]), keep=[1])
        self.assertAlmostEqual(C[1], 0.015)                   # دو نماد در دسترس
        self.assertEqual(B[1][1], 0.0)


if __name__ == "__main__":
    unittest.main()
