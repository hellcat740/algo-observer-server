import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

LAB = Path(__file__).resolve().parent.parent / "api/app/static/lab.html"


class CurrencyComparisonTest(unittest.TestCase):
    def test_usd_is_converted_without_mutating_original(self):
        text = LAB.read_text(encoding="utf-8")
        start = text.index("  function normalizeComparisonItems")
        end = text.index("\n  function mean", start)
        function = text[start:end]
        script = function + """
const original = [{display_price_cents:1000,actual_pay_price_cents:900,currency:'USD'}, {display_price_cents:1000,currency:'CNY'}];
const result = normalizeComparisonItems(original, {rate:7.2});
if (result[0].display_price_cents !== 7200 || result[0].actual_pay_price_cents !== 6480) throw Error('USD conversion');
if (result[1].display_price_cents !== 1000) throw Error('CNY changed');
if (original[0].display_price_cents !== 1000) throw Error('mutated original');
let rejected = false; try { normalizeComparisonItems([{display_price_cents:1,currency:'EUR'}], {}); } catch(e) { rejected = true; }
if (!rejected) throw Error('unknown currency accepted');
"""
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        self.assertIsNotNone(node, "运行 JavaScript 测试需要 Node.js")
        subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)

    def test_page_fetches_server_rate_and_displays_provenance(self):
        text = LAB.read_text(encoding="utf-8")
        self.assertIn("/api/exchange-rates/latest?base=USD&quote=CNY", text)
        self.assertIn("normalizeComparisonItems(items, exchangeRate)", text)
        self.assertIn("analysis.exchangeRate = exchangeRate", text)
        self.assertIn("最近成功汇率", text)
        self.assertIn("汇率日期", text)


if __name__ == "__main__":
    unittest.main()
