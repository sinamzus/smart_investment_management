# -*- coding: utf-8 -*-
"""ui/data/docs.js (راهنمای درون‌برنامه) باید با docs/*.md یکی باشد؛ پس از هر تغییر سند: python tools/build_ui_docs.py

    python -m unittest tests.test_ui_docs -v
"""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class UiDocsBundle(unittest.TestCase):
    def test_bundle_is_fresh(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_ui_docs.py"), "--check"], capture_output=True)
        self.assertEqual(r.returncode, 0, "ui/data/docs.js کهنه است: python tools/build_ui_docs.py")

    @unittest.skipUnless(shutil.which("node"), "node نصب نیست")
    def test_formulas_render(self):
        """هر فرمول $…$ و $$…$$ سند با KaTeX رابط بی‌خطا رندر شود (tools/docs_math_check.js)."""
        r = subprocess.run(["node", str(ROOT / "tools" / "docs_math_check.js")], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
