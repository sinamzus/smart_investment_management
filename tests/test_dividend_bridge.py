# -*- coding: utf-8 -*-
"""مدل سود نقدی با تأخیر و وام پل (فصل ۳ «وام پل»): sampled_replica.step_day، همان ui/builder.js simulate.

    python -m unittest tests.test_dividend_bridge -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sampled_replica as sr  # noqa: E402


class DividendBridge(unittest.TestCase):
    def test_no_loan_receivable_then_reinvest(self):
        sched = {}
        V, D, rcv = sr.step_day(100.0, 0.0, 0.0, 0.0, [(5, 0.04)], 0.0, sched, False, 0.3, 1)
        self.assertAlmostEqual(V, 96.0)          # سود از سهام جدا شد
        self.assertAlmostEqual(rcv, 4.0)
        self.assertEqual(D, 0.0)
        V, D, rcv = sr.step_day(V, D, rcv, 0.0, [], sched.pop(5), sched, False, 0.3, 1)
        self.assertAlmostEqual(V, 100.0)         # روز پرداخت دوباره سرمایه‌گذاری شد
        self.assertAlmostEqual(rcv, 0.0)

    def test_bridge_borrows_exactly_receivable_and_repays(self):
        sched = {}
        V, D, rcv = sr.step_day(100.0, 0.0, 0.0, 0.01, [(9, 0.04)], 0.0, sched, True, 0.3, 1)
        self.assertAlmostEqual(V, 101.0)         # همهٔ سهام سرمایه‌گذاری ماند
        self.assertAlmostEqual(D, 4.0)
        self.assertAlmostEqual(rcv, 4.0)
        V, D, rcv = sr.step_day(V, D, rcv, 0.0, [], 0.0, sched, True, 0.3, 30)   # بهره ۳۰ روز
        self.assertLessEqual(D, rcv + 1e-12)     # سقف روزانه: بدهی ≤ طلب
        self.assertLess(V, 101.0)                # بهرهٔ مازاد از فروش سهام
        V, D, rcv = sr.step_day(V, D, rcv, 0.0, [], sched.pop(9), sched, True, 0.3, 1)
        self.assertAlmostEqual(D, 0.0)
        self.assertAlmostEqual(rcv, 0.0)


if __name__ == "__main__":
    unittest.main()
