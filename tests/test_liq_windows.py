# -*- coding: utf-8 -*-
"""پنجرهٔ نقدشوندگی همتاساز روی روزهای باز بازار (construction.liq_windows؛ ممیزی ۲۰۲۶-۱۰-۲۱، تعطیلی ۵۰ روزهٔ ۱۴۰۵).

    python -m unittest tests.test_liq_windows -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import construction as cn  # noqa: E402

n, k = 200, 4
vol = np.ones((n, k)); val = np.full((n, k), 10.0)
vol[:, 3] = 0; val[:, 3] = 0; vol[::2, 3] = 1; val[::2, 3] = 1.0   # نماد ۳: یک روز در میان
vol[100:150] = 0; val[100:150] = 0                     # تعطیلی سراسری ۵۰ روزه
mk = SimpleNamespace(vol=vol, val=val)
ok = np.ones(k, bool)


class LiqWindows(unittest.TestCase):
    def test_closure_not_open(self):
        op = cn.open_days(mk, ok)
        self.assertFalse(op[100:150].any())
        self.assertTrue(op[:100].all() and op[150:].all())

    def test_closure_does_not_empty_trading_days(self):
        adv, td = cn.liq_windows(mk, ok)
        self.assertEqual(td[160, 0], 63)                  # پس از تعطیلی هنوز ۶۳ از ۶۳ روز باز معامله
        self.assertEqual(td[120, 0], 63)                  # در تعطیلی: مقدار آخرین روز باز
        self.assertAlmostEqual(adv[160, 0], 10.0)
        self.assertLess(td[160, 3], 40)                   # نماد کم‌معامله همچنان کم‌معامله است

    def test_old_window_would_fail_everyone(self):
        # رفتار پیشین (همهٔ ردیف‌ها): در روز ۱۶۰ فقط ۱۳ روز معامله از ۶۳ ⇒ فیلتر «ملایم» (≥ ۵۰) همه را رد می‌کرد
        old = (val > 0).astype(float)[160 - 62:161].sum(0)
        self.assertEqual(old[0], 13)


if __name__ == "__main__":
    unittest.main()
