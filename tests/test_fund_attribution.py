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

    def test_sort_2x3_dependent_when_signal_tracks_size(self):
        k = 200
        size = np.arange(k, dtype=float)
        sig = size + np.tile(np.arange(10, dtype=float), 20)                # معیار تقریباً همان اندازه (مثل آمیهود)
        P = fa.sort_2x3(size, sig, np.ones(k, bool), np.ones(k))
        self.assertTrue(min(len(v) for v in P.values()) >= 25)              # با برش مستقل، SH و BL خالی می‌شدند
        self.assertIsNone(fa.sort_2x3(size[:50], sig[:50], np.ones(50, bool), np.ones(50)))   # سبد کمتر از MIN_BUCKET


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
        self.assertEqual(W.days.tolist()[1:], [7, 14])                     # یک هفته تعطیلی (مثل نوروز) کنار نمی‌رود

    def test_weekly_drops_closure_and_reopening_weeks(self):
        days = pd.date_range("2025-01-04", periods=70, freq="D")             # ده هفته
        fund, mkt = pd.Series(0.01, index=days), pd.Series(0.0, index=days)
        F = pd.DataFrame({"SMB": 0.0}, index=days)
        open_days = days[(days < days[14]) | (days >= days[35])]             # هفته‌های ۳ تا ۵ بسته (هفتهٔ بازگشایی ۲۸ روزه)
        W = fa.weekly(fund, mkt, F, open_days, skip_days=0)
        self.assertEqual(len(W), 10 - 3 - (1 + fa.POST_CLOSE))              # سه هفتهٔ بسته + هفتهٔ بازگشایی + دو هفتهٔ بعد
        self.assertTrue((W.days == 7).all())

    def test_weekly_no_factor_data_is_nan_not_zero(self):
        days = pd.date_range("2025-01-04", periods=28, freq="D")
        fund, mkt = pd.Series(0.01, index=days), pd.Series(0.0, index=days)
        F = pd.DataFrame({"SMB": 0.001, "HML": np.where(days >= days[14], 0.001, np.nan)}, index=days)
        W = fa.weekly(fund, mkt, F, days, skip_days=0)
        self.assertEqual(len(W), 4)
        self.assertTrue(W.HML.iloc[:2].isna().all())                        # پیش‌تر ۰ بود و هفته وارد رگرسیون می‌شد
        self.assertAlmostEqual(W.HML.iloc[2], 1.001 ** 7 - 1)
        late = pd.DataFrame({"SMB": np.where(days >= days[14], 0.001, np.nan)}, index=days)
        self.assertEqual(len(fa.weekly(fund, mkt, late, days, skip_days=0)), 2)   # هفته‌های پیش از آغاز فاکتورها کنار می‌روند

    def test_market_only_on_same_weeks_and_dimson_lag(self):
        W = self.W.copy()
        W.loc[W.index[100:110], "HML"] = np.nan
        full, mo = fa.regress(W, self.rf), fa.regress(W, self.rf, ["MKT"])
        self.assertEqual(full["weeks"], mo["weeks"])
        self.assertEqual(full["weeks"], len(W) - 10)
        self.assertAlmostEqual(full["dimson_lag"], 0.0, delta=0.05)       # MKT هفتهٔ قبل در دادهٔ مصنوعی اثری ندارد


class FundDaily(unittest.TestCase):
    def test_levels_override_stale_daily_and_splits(self):
        import tempfile
        d = pd.date_range("2025-01-01", periods=40, freq="D").delete(range(20, 30))   # فاصلهٔ ۱۱ روزه
        nav = 1000 * 1.01 ** np.arange(len(d))
        nav[25:] /= 10                                                        # تقسیم واحد در روز ۲۵
        eff = np.full(len(d), 1.0)
        eff[5] = 0.0                                                          # dailyEfficiency کهنه: ۰ در حالی که NAV ۱٪ بالا رفت
        tmp = Path(tempfile.mkdtemp())
        pd.DataFrame({"date": d, "ret_daily": eff, "nav_cancel": nav}).to_csv(tmp / "nav_T.csv", index=False)
        old = fa.ACTIVE
        try:
            fa.ACTIVE = tmp
            r = fa.fund_daily("T")
        finally:
            fa.ACTIVE = old
        self.assertAlmostEqual(r.loc[d[5]], 0.01)                              # از سطح
        self.assertAlmostEqual(r.loc[d[25]], 0.01)                             # روز تقسیم: از dailyEfficiency
        self.assertTrue(np.isnan(r.loc[d[20]]))                                # پس از فاصلهٔ بیش از MAX_GAP


    def test_distribution_day_added_back(self):
        import tempfile
        d = pd.date_range("2025-01-01", periods=40, freq="D")
        nav = 1000 * 1.01 ** np.arange(len(d))
        nav[20:] *= 0.95                                                      # تقسیم سود ۵٪ در روز ۲۰: سطح می‌افتد
        eff = np.full(len(d), 1.0)                                            # بازده روزانهٔ فیپیران (با سود) همان ۱٪
        nav2 = nav.copy()
        nav2[30:] *= 1.37                                                     # جهش ۳۷٪ واقعی (بازگشایی): بماند
        tmp = Path(tempfile.mkdtemp())
        pd.DataFrame({"date": d, "ret_daily": eff, "nav_cancel": nav2}).to_csv(tmp / "nav_T.csv", index=False)
        old = fa.ACTIVE
        try:
            fa.ACTIVE = tmp
            r = fa.fund_daily("T")
        finally:
            fa.ACTIVE = old
        self.assertAlmostEqual(r.loc[d[20]], 0.01)
        self.assertAlmostEqual(r.loc[d[30]], 1.01 * 1.37 - 1)


def panel(alpha_w, n=300, seed=0, start=0):
    """صندوق مصنوعی ۵ فاکتوری با آلفای هفتگی alpha_w؛ شمارهٔ هفته‌ها از start."""
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 0.02, (n, len(fa.C5)))
    y = alpha_w + X @ np.array([0.9, 0.5, 0.1, 0.0, 0.2]) + rng.normal(0, 0.01, n)
    return y, X, np.arange(start, start + n)


class Skill(unittest.TestCase):
    def test_market_timing_detected(self):
        rng = np.random.default_rng(1)
        n = 300
        idx = pd.date_range("2020-01-04", periods=n, freq="7D")
        mkt = rng.normal(0.005, 0.03, n)
        F = pd.DataFrame({c: rng.normal(0, 0.02, n) for c in ["SMB", "HML", "MOM", "LV", "ILQ"]}, index=idx)
        rf = 1.30 ** (7 / 365) - 1
        ex = mkt - rf
        y = rf + 0.8 * ex + 4.0 * ex ** 2 + rng.normal(0, 0.003, n)          # بتای بالاتر در بازار بالا
        W = F.assign(y=y, MKT_raw=mkt, days=7, rf_ann=0.30)
        s = fa.skill(W)
        self.assertTrue(s["eligible"])
        self.assertGreater(s["tm_t"], 3)
        self.assertAlmostEqual(s["tm_gamma"], 4.0, delta=0.6)
        self.assertGreater(s["tm_ann"], 0)

    def test_luck_vs_skill_null_and_skilled(self):
        P = {f"n{i}": panel(0.0, seed=i, start=i * 5) for i in range(20)}  # بی‌مهارت، تاریخچه‌های جابه‌جا
        P["skilled"] = panel(0.004, seed=99)                                  # ≈ ۲۱٪ در سال
        T = fa.luck_vs_skill(P, n_boot=200)
        self.assertLess(T["funds"]["skilled"]["p"], 0.01)
        self.assertGreater(np.median([T["funds"][f"n{i}"]["p"] for i in range(20)]), 0.2)
        self.assertGreaterEqual(T["sig_pos"], 1)
        self.assertTrue(0 <= T["pi_pos"] <= 1 and 0 <= T["pi0"] <= 1)
        self.assertEqual(len(T["t_actual"]), len(T["pct"]))


if __name__ == "__main__":
    unittest.main()
