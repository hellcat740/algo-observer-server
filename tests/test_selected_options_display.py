"""用户看板与管理控制台已选规格展示回归测试。"""
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "api" / "app" / "static"


class SelectedOptionsDisplayTest(unittest.TestCase):
    def test_observation_tables_show_sku_and_selected_options(self):
        for name in ("me.html", "index.html", "admin.html"):
            with self.subTest(page=name):
                text = (STATIC / name).read_text(encoding="utf-8")
                self.assertIn("<th>SKU</th>", text)
                self.assertIn("<th>已选规格</th>", text)
                self.assertIn("function formatSelectedOptions(options)", text)
                self.assertIn("formatSelectedOptions(o.selected_options)", text)

    def test_user_dashboard_details_include_sku_and_options(self):
        text = (STATIC / "me.html").read_text(encoding="utf-8")
        self.assertIn("['SKU ID', o.sku_id]", text)
        self.assertIn("['已选规格', formatSelectedOptions(o.selected_options)]", text)

    def test_console_details_include_sku_and_formatted_options(self):
        for name in ("index.html", "admin.html"):
            with self.subTest(page=name):
                text = (STATIC / name).read_text(encoding="utf-8")
                self.assertIn("sku_id: 'SKU ID'", text)
                self.assertIn("selected_options: '已选规格'", text)
                self.assertIn("v = formatSelectedOptions(v)", text)


if __name__ == "__main__":
    unittest.main()
