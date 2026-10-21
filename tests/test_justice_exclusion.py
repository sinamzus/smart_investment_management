# -*- coding: utf-8 -*-
"""شرکت‌های سرمایه‌گذاری استانی سهام عدالت از ساخت همتا کنار گذاشته می‌شوند (construction.justice_provincial؛ تصمیم مالک ۲۰۲۶-۱۰-۲۱).

    python -m unittest tests.test_justice_exclusion -v
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import construction as cn  # noqa: E402
import new_listings as nl  # noqa: E402


class JusticeProvincial(unittest.TestCase):
    def test_mask_by_name(self):
        mk = SimpleNamespace(cols=np.array(["11358107932902023", "2328862017676109", "999"]), sym=np.array(["وسمازن", "وسپه", "وسکرمان"]))
        m = cn.justice_provincial(mk)
        self.assertEqual(m.tolist(), [True, False, True])       # وسپه (سرمایه‌گذاری سپه) استانی نیست؛ وسکرمان با نماد هم شناخته می‌شود

    def test_layer_skips_excluded(self):
        n, k = 400, 3
        val = np.ones((n, k)); val[:100, 2] = 0
        mk = SimpleNamespace(n=n, val=val, mcap=np.full((n, k), 100.0), eligible=lambda t, require_trade=False: np.array([True, True, False]))
        ok = np.ones(k, bool)
        self.assertEqual([e["i"] for e in nl.events(mk, ok, 300)], [2])
        self.assertEqual(nl.events(mk, ok, 300, exclude=np.array([False, False, True])), [])


if __name__ == "__main__":
    unittest.main()
