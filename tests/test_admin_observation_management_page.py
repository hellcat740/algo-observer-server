import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "index.html"


class AdminObservationManagementPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_sidebar_removes_only_high_dimensional_link(self):
        sidebar = self.text.split('<nav class="sidebar">', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn('href="/visualization"', sidebar)
        self.assertIn('href="/space"', sidebar)

    def test_classification_button_and_cached_category_loader(self):
        for marker in (
            'id="obs-classifyBtn"', 'title="后台分类未分类商品"',
            '>分类</button>', "async function obsClassify()",
            "async function obsLoadCategories(items)", "/api/observations/categories",
            "/api/space/classification-check", "/api/space/classification-status",
            ">类别</th>", "obsCategoryText",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)

    def test_edit_precedes_delete_and_supports_all_business_fields(self):
        row = self.text.split('async function obsLoad()', 1)[1].split("function obsSearch", 1)[0]
        self.assertLess(row.index("obsEdit("), row.index("obsDelete("))
        for marker in (
            'id="obs-editDrawer"', "async function obsEdit(id)", "function obsEditClose()",
            "async function obsEditSubmit()", 'method: \'PUT\'', "obs-edit-fields",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)
        for field in (
            "task_id", "user_ref", "platform_code", "source_type", "product_id", "product_name",
            "seller_id", "product_url", "display_price_cents", "actual_pay_price_cents", "currency",
            "discount_coupon_amount_cents", "promo_type", "promo_label", "is_login",
            "membership_level", "is_new_user", "register_days", "user_agent", "platform",
            "language", "device_memory", "hardware_concurrency", "screen_resolution",
            "device_price_score_estimate", "ip_city", "shipping_city", "peak_hour", "stock_hint",
            "fetch_ts", "screenshot_path", "dom_price_text", "dom_snapshot_path", "source_code_version",
        ):
            with self.subTest(field=field):
                self.assertIn(f'key: "{field}"', self.text)

    def test_fixed_format_fields_use_selects(self):
        for field in ("platform_code", "currency", "is_login", "is_new_user", "peak_hour"):
            start = self.text.index(f'key: "{field}"')
            descriptor = self.text[start:self.text.index("}", start) + 1]
            self.assertIn('type: "select"', descriptor)
        for marker in ('value: ""', 'value: "true"', 'value: "false"', 'value: "CNY"', 'value: "USD"'):
            self.assertIn(marker, self.text)


if __name__ == "__main__":
    unittest.main()
