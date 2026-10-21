# -*- coding: utf-8 -*-
"""سقف ماندن نماد تازه در لایهٔ عرضهٔ اولیه (new_listings.MAX_LAYER؛ ممیزی ۲۰۲۶-۱۰-۲۱: پنج شرکت «وس…» آذر ۱۳۹۹ هنوز در لایه بودند).

    python -m unittest tests.test_new_listing_cap -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import new_listings as nl  # noqa: E402

n, k = 700, 4
val = np.ones((n, k)); val[:100, 2] = 0; val[:100, 3] = 0       # نماد ۲ و ۳ از روز ۱۰۰ معامله می‌شوند
mcap = np.full((n, k), 100.0)
ELIG_3 = 250                                                     # نماد ۳ در روز ۲۵۰ واجد عادی می‌شود؛ نماد ۲ هرگز


def eligible(t, require_trade=False):
    e = np.array([True, True, False, t >= ELIG_3])
    return e


mk = SimpleNamespace(n=n, val=val, mcap=mcap, eligible=eligible)
ok = np.ones(k, bool)


class LayerCap(unittest.TestCase):
    def test_never_eligible_leaves_after_one_year(self):
        ev = {e["i"]: e for e in nl.events(mk, ok, 300)}
        self.assertIn(2, ev)
        self.assertEqual(ev[2]["s"], 101)                               # نخستین معامله روز ۱۰۰؛ خرید از روز بعد
        self.assertEqual(ev[2]["end"], 100 + nl.MAX_LAYER)              # یک سال پس از نخستین معامله، نه پایان داده

    def test_eligible_name_leaves_at_eligibility(self):
        ev = {e["i"]: e for e in nl.events(mk, ok, 300)}
        self.assertEqual(ev[3]["end"], ELIG_3)


if __name__ == "__main__":
    unittest.main()
