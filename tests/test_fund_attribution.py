# -*- coding: utf-8 -*-
"""تفکیک فاکتوری صندوق (tools/fund_attribution.py؛ فصل ۷ §۷٫۹).

    python -m unittest tests.test_fund_attribution -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import fund_attribution as fa  # noqa: E402


class BuyHold(unittest.TestCase):
    def test_bh_weights_drift(self):
        X = np.array([[0.10, 0.0], [0.0, 0.10]])
        r = fa.bh_returns(X, np.array([1.0, 1.0]))
        self.assertAlmostEqual(r[0], 0.05)
        self.assertAlmostEqual(r[1], 0.05 / 1.05)                        # وزن نماد ۲ پس از روز اول 1/2.1
        self.assertTrue(np.allclose(fa.bh_returns(np.array([[np.nan, 0.02]]), np.array([1.0, 1.0])), [0.01]))   # بی‌داده = منجمد

    def test_sort_2x3_buckets(self):
        k = 120
        size = np.arange(k, dtype=float)
        sig = np.tile(np.arange(10, dtype=float), 12)
        P = fa.sort_2x3(size, sig, np.ones(k, bool), np.ones(k))
        self.assertEqual(sorted(P), ["BH", "BL", "BM", "SH", "SL", "SM"])
        self.assertTrue(all(size[P["S" + g]].max() < size[P["B" + g]].min() for g in "LMH"))
        self.assertTrue(sig[P["SH"]].min() >= sig[P["SM"]].max())
        self.assertEqual(sum(len(v) for v in P.values()), k)


class Regression(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        n = 260
        idx = pd.date_range("2024-01-06", periods=n, freq="7D")
        F = pd.DataFrame({c: rng.normal(0, 0.02, n) for c in ["SMB", "HML", "MOM", "LV", "ILQ"]}, index=idx)
        mkt = rng.normal(0.005, 0.03, n)
        self.rf = 0.30
        rf = (1 + self.rf) ** (7 / 365) - 1
        self.beta = {"MKT": 0.9, "SMB": 0.8, "HML": 0.2, "MOM": 0.0, "LV": -0.1, "ILQ": 0.1}
        y = rf + 0.001 + self.beta["MKT"] * (mkt - rf) + sum(self.beta[c] * F[c].values for c in F) + rng.normal(0, 0.003, n)
        self.W = F.assign(y=y, MKT_raw=mkt, days=7)

    def test_recovers_betas_and_contributions_add_up(self):
        r = fa.regress(self.W, self.rf)
        for f in r["factors"]:
            self.assertAlmostEqual(f["beta"], self.beta[f["code"]], delta=0.03)
        self.assertAlmostEqual(r["alpha_ann"], 5.2, delta=0.8)
        self.assertAlmostEqual(r["alpha_ann"] + sum(f["contrib_ann"] for f in r["factors"]), r["excess_ann"], places=9)
        self.assertGreater(r["r2"], 0.9)

    def test_weekly_alignment_drops_closed_weeks(self):
        days = pd.date_range("2025-01-04", periods=28, freq="D")             # چهار هفتهٔ کامل از شنبه
        fund = pd.Series(0.01, index=days)
        mkt = pd.Series(0.0, index=days)
        F = pd.DataFrame({"SMB": 0.0}, index=days)
        open_days = days[(days < days[14]) | (days >= days[21])]             # هفتهٔ سوم بازار بسته
        W = fa.weekly(fund, mkt, F, open_days, skip_days=0)
        self.assertEqual(len(W), 3)
        self.assertAlmostEqual(W.y.iloc[0], 1.01 ** 7 - 1)
        self.assertEqual(W.days.tolist()[1:], [7, 14])


if __name__ == "__main__":
    unittest.main()
