# -*- coding: utf-8 -*-
"""ui/data/docs.js (راهنمای درون‌برنامه) باید با docs/*.md یکی باشد؛ پس از هر تغییر سند: python tools/build_ui_docs.py

    python -m unittest tests.test_ui_docs -v
"""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class UiDocsBundle(unittest.TestCase):
    def test_bundle_is_fresh(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_ui_docs.py"), "--check"], capture_output=True)
        self.assertEqual(r.returncode, 0, "ui/data/docs.js کهنه است: python tools/build_ui_docs.py")


if __name__ == "__main__":
    unittest.main()
