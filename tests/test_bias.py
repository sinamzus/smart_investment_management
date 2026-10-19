# -*- coding: utf-8 -*-
"""آزمون‌های ممیزی سوگیری ۲۰۲۶-۱۰-۱۹ (فصل ۰۸ §۸٫۱ و §۸٫۶): هر آزمون یک قاعدهٔ سند را روی دادهٔ ساختگی می‌سنجد.

    python -m unittest tests.test_bias -v
"""
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import construction as cn  # noqa: E402
import signals as sg  # noqa: E402


def tiny_market(n=400, k=4, seed=0):
    """بازار ساختگی: k نماد، n روز، بازده تصادفی؛ حجم بعداً دستی تنظیم می‌شود (فایل قیمت ندارند)."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-01-02", periods=n)
    rows = []
    for j in range(k):
        r = rng.normal(0, 0.01, n)
        px = 1000 * np.cumprod(1 + r)
        for i, d in enumerate(dates):
            rows.append({"date": d, "ins_code": f"C{j}", "symbol": f"S{j}", "market": "bourse", "r_tr": r[i], "r_pr": r[i],
                         "pClosing": px[i], "priceYesterday": px[i] / (1 + r[i]), "shares": 1e6})
    Ra = pd.DataFrame(rows)
    info = pd.DataFrame({"ins_code": [f"C{j}" for j in range(k)], "sector_name": ["A", "A", "B", "B"][:k], "sector_code": ["01", "01", "02", "02"][:k]})
    mk = sg.Market(Ra, info)
    mk.vol = np.ones((mk.n, mk.k))
    return mk


class UntradedNames(unittest.TestCase):
    """A2: نماد بی‌معامله (حجم صفر) در روز سیگنال واجد نیست و در روز اجرا قابل‌معامله نیست."""

    def test_eligible_requires_trade_on_signal_day(self):
        mk = tiny_market()
        a = mk.n - 2
        self.assertTrue(mk.eligible(a).all())
        mk.vol[a, 1] = 0.0
        ok = mk.eligible(a)
        self.assertFalse(ok[1]); self.assertTrue(ok[0])

    def test_tradable_uses_execution_day(self):
        mk = tiny_market()
        a = mk.n - 3
        mk.vol[a + 1, 2] = 0.0                      # روز اجرا (delay = 0)
        self.assertFalse(mk.tradable(a)[2]); self.assertTrue(mk.tradable(a)[0])
        self.assertTrue(mk.tradable(a, delay=1)[2])   # با تأخیر یک روز، روز اجرا a+2 است

    def test_freeze_untradable_keeps_held_weight(self):
        prev = np.array([0.5, 0.3, 0.2, 0.0])
        w = np.array([0.4, 0.0, 0.3, 0.3])            # الگوریتم نماد ۱ را فروخته و ۳ را خریده
        tr = np.array([True, False, True, True])      # نماد ۱ در روز اجرا معامله ندارد ⇒ فروختنی نیست
        out = cn.freeze_untradable(w, prev, tr)
        self.assertAlmostEqual(out[1], 0.3)           # وزن رانش‌یافته می‌ماند
        self.assertAlmostEqual(out.sum(), 1.0)
        np.testing.assert_allclose(out[[0, 2, 3]], np.array([0.4, 0.3, 0.3]) * 0.7)   # بقیه در فضای ۷۰٪ بازنرمال

    def test_freeze_noop_when_all_tradable(self):
        prev = np.array([0.5, 0.5]); w = np.array([0.2, 0.8])
        np.testing.assert_array_equal(cn.freeze_untradable(w, prev, np.array([True, True])), w)


class SectorHistory(unittest.TestCase):
    """B4: خنثی‌سازی صنعتی با صنعتِ همان روز، نه عکس امروز."""

    def test_sector_at_applies_history_before_change_date(self):
        mk = tiny_market()
        mk.sector_hist = [(0, pd.Timestamp("2024-03-21"), "B")]      # نماد ۰ پیش از ۱۴۰۳ در صنعت B بود
        early = int(mk.dates.searchsorted(pd.Timestamp("2023-06-01")))
        late = int(mk.dates.searchsorted(pd.Timestamp("2024-06-01")))
        self.assertEqual(mk.sector_at(early)[0], "B")
        self.assertEqual(mk.sector_at(late)[0], "A")
        self.assertEqual(mk.sector[0], "A")                           # عکس امروز دست‌نخورده


class EpsAnnouncementDates(unittest.TestCase):
    """B5: زمان دانستن اعلام سود هرگز پیش از فردای پایان سال مالی نیست."""

    def test_clamp_moves_impossible_dates(self):
        E = pd.DataFrame({"ins_code": ["x", "x"], "fy": pd.to_datetime(["2024-03-19", "2025-03-20"]),
                          "date": pd.to_datetime(["2024-03-19", "2025-06-10"]), "period": [12, 12], "eps": [10, 12]})
        out = sg.clamp_announce(E)
        self.assertEqual(out.date.iloc[0], pd.Timestamp("2024-03-20"))   # ناممکن ⇒ fy + ۱
        self.assertEqual(out.date.iloc[1], pd.Timestamp("2025-06-10"))   # عادی دست‌نخورده


class IsinMarket(unittest.TestCase):
    """A1/B4: بازار از پیشوند ISIN (بازار پذیرش)، نه flow امروز."""

    def test_isin_prefix_map(self):
        import rebuild_ew_index as ew
        self.assertEqual(ew.ISIN_MARKET["IRO1"], "bourse")
        self.assertEqual(ew.ISIN_MARKET["IRO3"], "farabourse")
        self.assertEqual(ew.ISIN_MARKET["IRO7"], "paye")
        self.assertEqual(ew.ISIN_MARKET["IROT"], "bourse")       # کد قدیمی سهام بورس (نماد تنزل‌یافته)
        self.assertNotIn("IRK1", ew.ISIN_MARKET)                 # گواهی کالا سهم نیست


class ThinTail(unittest.TestCase):
    """دریافت ناقص: روز پایانی با چند نماد نباید آخرین روز پانل شود."""

    def test_trim_thin_tail(self):
        import rebuild_ew_index as ew
        dates = pd.bdate_range("2026-09-01", periods=30)
        rows = [{"date": d, "ins_code": f"c{i}"} for d in dates[:-2] for i in range(100)]
        rows += [{"date": d, "ins_code": f"c{i}"} for d in dates[-2:] for i in range(10)]   # دو روز آخر فقط ۱۰ نماد
        out = ew.trim_thin_tail(pd.DataFrame(rows))
        self.assertEqual(out.date.max(), dates[-3])


class MarketClosure(unittest.TestCase):
    """تعطیلی سراسری: اجرا به روز بازگشایی می‌رود، نه انجماد کل سبد."""

    def test_exec_day_rolls_past_closure(self):
        mk = tiny_market()
        a = mk.n - 10
        mk.vol[a + 1: a + 4, :] = 0.0                # سه روز بازار بسته
        self.assertEqual(mk.exec_day(a), a + 4)
        self.assertTrue(mk.tradable(a).all())
        mk.vol[a + 4, 1] = 0.0                       # روز بازگشایی نماد ۱ معامله ندارد
        self.assertFalse(mk.tradable(a)[1])

    def test_signal_day_in_closure_uses_last_open_day(self):
        mk = tiny_market()
        a = mk.n - 5
        mk.vol[a - 1: a + 1, :] = 0.0                # روز سیگنال و روز قبلش تعطیل
        self.assertEqual(mk.last_open(a), a - 2)
        self.assertTrue(mk.eligible(a).all())


if __name__ == "__main__":
    unittest.main()


class FactorAttribution(unittest.TestCase):
    """تفکیک فاکتوری (فصل ۱۴ §۱۴٫۷٫۸): ضریب‌ها بازیابی شوند و سهم‌ها دقیقاً به برتری برسند."""

    def test_recovers_betas_and_contributions_sum(self):
        import attribution as at
        rng = np.random.default_rng(1)
        T = 120
        all_ = rng.normal(0.03, 0.08, T)
        fac = {"MKT": all_}
        for c in ("SIZE", "LOWVOL", "DIV", "MOM"):
            fac[c] = rng.normal(0.005, 0.03, T)
        y = 0.002 + 0.1 * all_ + 0.6 * fac["SIZE"] + 0.3 * fac["DIV"] + rng.normal(0, 0.002, T)
        r = at.attribute(all_ + y, all_, np.full(T, 0.1), np.full(T, 0.05), 100, fac)
        b = {x["code"]: x["beta"] for x in r["factors"]}
        self.assertAlmostEqual(b["SIZE"], 0.6, delta=0.03)
        self.assertAlmostEqual(b["DIV"], 0.3, delta=0.03)
        self.assertAlmostEqual(b["LOWVOL"], 0.0, delta=0.03)
        total = r["alpha_ann"] + sum(x["contrib_ann"] for x in r["factors"])
        self.assertAlmostEqual(total, r["gross_excess_ann"], places=8)
        self.assertAlmostEqual(r["gross_excess_ann"] + r["cost_ann"], r["net_excess_ann"], places=8)
        self.assertAlmostEqual(r["cost_ann"], -12 * 100 * 0.05 * 0.01, places=8)   # (۰٫۱ − ۰٫۰۵) × ۱٪ × ۱۲

    def test_tail_alignment_for_late_start(self):
        import attribution as at
        a, b = at.tail_align(np.arange(10), np.arange(4))
        np.testing.assert_array_equal(a, [6, 7, 8, 9])
