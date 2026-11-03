# -*- coding: utf-8 -*-
"""نرخ بدون ریسک از اخزا (tools/build_rf.py و rf هفتگی در tools/fund_attribution.py؛ فصل ۷ §۷٫۱۰).

    python -m unittest tests.test_build_rf -v
"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_rf as br  # noqa: E402


def frame(rows):
    """rows: (date, symbol, close, value, volume, maturity) → همان ستون‌های load()."""
    D = pd.DataFrame(rows, columns=["date", "symbol", "close", "value", "volume", "maturity"])
    D["date"], D["maturity"] = pd.to_datetime(D.date), pd.to_datetime(D.maturity)
    D["count"] = (D.volume > 0).astype(int)
    D["days"] = (D.maturity - D.date).dt.days
    D["traded"] = (D.volume > 0) & (D["count"] > 0) & (D.close > 0)
    D["ytm"] = np.where(D.traded & (D.days > 0), br.ytm(D.close, D.days.clip(lower=1)), np.nan)
    return D


class Ytm(unittest.TestCase):
    def test_formula(self):
        self.assertAlmostEqual(float(br.ytm(1e6 / 1.3, 365)), 0.30, places=10)
        self.assertAlmostEqual(float(br.ytm(1e6 / 1.3 ** 2, 730)), 0.30, places=10)
        self.assertAlmostEqual(float(br.ytm(1e6 / 1.3 ** 0.5, 182.5)), 0.30, places=10)


class Daily(unittest.TestCase):
    def setUp(self):
        d = "2025-01-01"
        p = lambda r, days: 1e6 / (1 + r) ** (days / 365)  # noqa: E731
        self.D = frame([
            (d, "A", p(0.30, 200), 3e9, 10, "2025-07-20"),     # ۲۰۰ روز، ۳۰٪
            (d, "B", p(0.34, 500), 1e9, 10, "2026-05-16"),     # ۵۰۰ روز، ۳۴٪
            (d, "M", 990_000, 9e9, 10, "2024-12-20"),          # سررسیدشده
            (d, "N", 995_000, 9e9, 10, "2025-01-10"),          # کمتر از MIN_DAYS
            (d, "Z", p(0.50, 300), 9e9, 0, "2025-10-28"),      # بی‌معامله
            (d, "F", 1_000_000, 9e9, 10, "2025-06-01"),        # قیمت = اسمی
            ("2025-01-02", "A", p(0.31, 199), 1e9, 10, "2025-07-20"),
        ])

    def test_only_live_traded(self):
        S = br.daily(self.D)
        r = S.loc["2025-01-01"]
        self.assertEqual(int(r.n), 2)                                      # فقط A و B
        self.assertAlmostEqual(r.vw, (3 * 0.30 + 1 * 0.34) / 4, places=6)  # وزن ارزش معامله
        self.assertAlmostEqual(r.med, 0.32, places=6)
        self.assertAlmostEqual(r.y1, 0.30 + 0.04 * (365 - 200) / 300, places=6)   # درون‌یابی خطی ۲۰۰→۵۰۰ روز
        r2 = S.loc["2025-01-02"]
        self.assertEqual(int(r2.n), 1)
        self.assertTrue(np.isnan(r2.y1))                                   # بدون ورقهٔ بالای یک سال: بدون نرخ یک‌ساله

    def test_ffill_limit(self):
        D = pd.concat([self.D, frame([("2025-02-15", "A", 1e6 / 1.3 ** (155 / 365), 1e9, 10, "2025-07-20")])], ignore_index=True)
        S = br.daily(D)
        self.assertTrue(np.isnan(S.vw.loc["2025-01-10"]))
        self.assertAlmostEqual(S.rf.loc["2025-01-22"], S.vw.loc["2025-01-02"])     # ۲۰ روز پس از آخرین معامله
        self.assertTrue(np.isnan(S.rf.loc["2025-01-23"]))                           # بیش از FFILL_DAYS
        self.assertAlmostEqual(S.rf.loc["2025-02-15"], 0.30, places=6)


class WeeklyRf(unittest.TestCase):
    def test_rate_before_week_start(self):
        import fund_attribution as fa
        tmp = Path(tempfile.mkdtemp()) / "rf_daily.csv"
        old = fa.RF_CSV
        try:
            pd.DataFrame({"date": ["2025-01-01", "2025-01-08"], "rf": [0.30, 0.40]}).to_csv(tmp, index=False)
            fa.RF_CSV = tmp
            W = pd.DataFrame({"days": [7, 7, 14]}, index=pd.to_datetime(["2025-01-09", "2025-01-16", "2025-01-30"]))
            v = fa.rf_weekly(W)                                            # شروع هفته‌ها: ۰۲، ۰۹ و ۱۶ ژانویه
            self.assertTrue(np.allclose(v, [0.30, 0.40, 0.40]))
        finally:
            fa.RF_CSV = old
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
