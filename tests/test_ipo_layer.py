# -*- coding: utf-8 -*-
"""لایهٔ عرضهٔ اولیه در همتا (فصل ۳ «تأخیر ورود عرضهٔ اولیه»): sampled_replica.ipo_day و ipo_rebalance، همان ui/builder.js simulate.

    python -m unittest tests.test_ipo_layer -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import sampled_replica as sr  # noqa: E402

EV = [{"i": 0, "s": 1, "end": 50}]
W = {0: np.full(100, 0.03)}                       # وزن شاخص ۳٪
X = np.zeros((100, 1)); X[:, 0] = 0.03          # +۳٪ هر روز (صف خرید)


class IpoLayer(unittest.TestCase):
    def test_fill_capped_by_traded_value(self):
        VAL = np.full((100, 1), 1e9)              # ۱ میلیارد ریال معامله در روز
        V, H = sr.ipo_day(1.0, {}, EV, W, X, VAL, 1, 0.02, 1000.0, 0.0)
        self.assertAlmostEqual(H[0], 0.02 * 1e9 / 1e12)                   # φ × ارزش ÷ اندازهٔ صندوق
        self.assertAlmostEqual(V + H[0], 1.0)

    def test_fills_to_index_weight_when_liquid(self):
        VAL = np.full((100, 1), 1e15)
        V, H = sr.ipo_day(1.0, {}, EV, W, X, VAL, 1, 0.02, 1000.0, 0.0)
        self.assertAlmostEqual(H[0] / (V + H[0]), 0.03)

    def test_no_buy_before_listing_and_cost(self):
        VAL = np.full((100, 1), 1e15)
        V, H = sr.ipo_day(1.0, {}, EV, W, X, VAL, 0, 0.02, 1000.0, 125.0)
        self.assertEqual(H, {})                                            # پیش از s خرید نیست
        V, H = sr.ipo_day(1.0, {}, EV, W, X, VAL, 1, 0.02, 1000.0, 125.0)
        self.assertAlmostEqual(V, 1.0 - 0.03 - 0.03 * 0.0125)              # هزینه = حجم × c

    def test_release_after_eligibility(self):
        V, H = sr.ipo_rebalance(0.97, {0: 0.03}, EV, W, 60, 0.0)          # end = 50 ≤ ۶۰ ⇒ رها
        self.assertEqual(H, {})
        self.assertAlmostEqual(V, 1.0)

    def test_trim_above_index_weight(self):
        V, H = sr.ipo_rebalance(0.9, {0: 0.1}, EV, W, 20, 0.0)            # ۱۰٪ در برابر وزن ۳٪
        self.assertAlmostEqual(H[0], 0.03)
        self.assertAlmostEqual(V, 0.97)


if __name__ == "__main__":
    unittest.main()
