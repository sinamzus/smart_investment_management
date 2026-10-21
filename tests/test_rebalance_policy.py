# -*- coding: utf-8 -*-
"""سیاست ریبالانس همتاساز (فصل ۳ «سیاست ریبالانس»): build_replica_panel.sim_policy و روزهای بررسی build_replica_rebal.

    python -m unittest tests.test_rebalance_policy -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_replica_panel as bp  # noqa: E402
import build_replica_rebal as rr  # noqa: E402

n, k = 300, 2
rng = np.random.default_rng(1)
X = rng.normal(0, 0.02, (n, k)); X[:, 1] += 0.004                  # نماد ۲ تندتر رشد می‌کند ⇒ وزن‌ها از ۵۰/۵۰ دور می‌شوند
mk = SimpleNamespace(tradable=lambda a: np.ones(k, bool))
cx = SimpleNamespace(mk=mk, n=n, k=k, X=X, Y=np.zeros((n, k)), K=pd.Series(X.mean(1)))
me = list(range(260, n - 1, 10))                                   # «ماه» = ۱۰ روز
key = ("top", 2, 0)
TG = {a: {key: (np.array([0, 1]), np.array([0.5, 0.5]), np.ones(2))} for a in range(n)}
days0 = me[0] + 1


def bh(a0):
    """بازده روزانهٔ خرید و نگهداری ۵۰/۵۰ از روز a0"""
    w = np.array([0.5, 0.5]); out = []
    for t in range(a0 + 1, n):
        v0 = w.sum(); w = w * (1 + X[t]); out.append(w.sum() / v0 - 1)
    return np.array(out)


class Policy(unittest.TestCase):
    def test_monthly_rebalances_each_month(self):
        P = bp.sim_policy(cx, key, me, me, TG, {}, days0)
        self.assertEqual(P["rbm"], [1] * len(me))
        self.assertEqual(P["tod"], [])
        self.assertAlmostEqual(P["to"][0], 0.5)                          # خرید اولیه از نقد
        self.assertTrue(all(x > 0 for x in P["to"][1:]))                 # بازگشت به ۵۰/۵۰ گردش دارد

    def test_infinite_threshold_is_buy_and_hold(self):
        P = bp.sim_policy(cx, key, me, list(range(me[0], n - 1)), TG, {}, days0, thr=10.0)
        self.assertEqual(sum(P["rbm"]), 1)                               # فقط خرید اولیه
        self.assertEqual(P["tod"], [])
        np.testing.assert_allclose(P["r"], bh(me[0]), atol=1e-12)
        w = P["sel"][-1][1]
        self.assertGreater(w[1], 0.5)                                    # ترکیب آغاز ماه آخر رانش‌یافته است

    def test_intra_month_checks_go_to_tod(self):
        checks = sorted(set(range(me[0], n - 1, 5)) | {me[0]})
        P = bp.sim_policy(cx, key, me, checks, TG, {}, days0)
        mid = [a + 1 - days0 for a in checks if a not in me]
        self.assertEqual([t for t, _ in P["tod"]], mid)
        self.assertEqual(P["rbm"], [1] * len(me))                         # این روزها پایان ماه هم هستند

    def test_threshold_skips_small_drift(self):
        checks = list(range(me[0], n - 1))
        P0 = bp.sim_policy(cx, key, me, checks, TG, {}, days0)
        P1 = bp.sim_policy(cx, key, me, checks, TG, {}, days0, thr=0.02)
        n0 = sum(P0["rbm"]) + len(P0["tod"]); n1 = sum(P1["rbm"]) + len(P1["tod"])
        self.assertLess(n1, n0)
        self.assertTrue(all(x >= 0.02 for _, x in P1["tod"]))


class Checks(unittest.TestCase):
    def test_calendar_subsets(self):
        dates = pd.bdate_range("2020-01-01", periods=400)
        mev = [i for i in range(1, 399) if dates[i].month != dates[i + 1].month]
        jm = {a: rr.sg.ewr.g2j(dates[a].year, dates[a].month, dates[a].day)[1] for a in mev}
        q = rr.checks_of((3, 6, 9, 12), mev, dates, 400)
        self.assertEqual(q[0], mev[0])
        self.assertTrue(all(jm[a] in (3, 6, 9, 12) for a in q[1:]))
        w1 = rr.checks_of("week", mev, dates, 400)
        w2 = rr.checks_of("week2", mev, dates, 400)
        self.assertTrue(set(w2) <= set(w1))
        self.assertLess(len(w2), len(w1))
        we, _ = rr.week_ends(dates)
        self.assertTrue(all(dates[x + 1] - dates[x] > pd.Timedelta(days=1) or dates[x + 1].weekday() == 5 for x in we[we < 399]))


if __name__ == "__main__":
    unittest.main()
