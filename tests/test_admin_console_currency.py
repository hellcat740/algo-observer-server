import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "api/app/static"


class AdminConsoleCurrencyTest(unittest.TestCase):
    def test_analysis_pull_panel_and_branch_are_removed(self):
        text = (STATIC / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("分析时拉取服务器同商品数据合并比对", text)
        self.assertNotIn("id=\"an-pull\"", text)
        self.assertNotIn("anPullAnalyze", text)
        self.assertNotIn("anPullToggle", text)

    def test_console_formats_observation_amounts_by_currency(self):
        for name in ("index.html", "admin.html"):
            text = (STATIC / name).read_text(encoding="utf-8")
            with self.subTest(page=name):
                self.assertNotIn("标价(元)", text)
                self.assertNotIn("到手价(元)", text)
                self.assertIn("currency === 'USD' ? '$'", text)
                self.assertIn("o.display_price_cents, o.currency", text)
                self.assertIn("o.actual_pay_price_cents, o.currency", text)
                self.assertIn("fen(v, o.currency)", text) if name == "index.html" else self.assertIn("fen2yuan(v, o.currency)", text)


if __name__ == "__main__":
    unittest.main()
