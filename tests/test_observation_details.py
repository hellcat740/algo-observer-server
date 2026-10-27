"""我的观测记录行内详情回归测试。"""
import unittest
from pathlib import Path

PAGE = Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "me.html"


class ObservationDetailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_rows_have_accessible_expand_controls(self):
        for marker in (
            "function renderObservationDetails(o)", "function toggleObservation(index)",
            "data-obs-index", 'role="button"', 'tabindex="0"', 'aria-expanded="false"',
            "obs-detail-", "event.key === 'Enter'", "event.key === ' '",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.text)

    def test_details_cover_product_user_device_and_sync_fields(self):
        for field in (
            "observation_id", "product_url", "seller_id", "discount_coupon_amount_cents",
            "promo_type", "promo_label", "membership_level", "is_new_user", "register_days",
            "ip_city", "shipping_city", "stock_hint", "user_agent", "platform",
            "language", "device_memory", "hardware_concurrency", "screen_resolution",
            "device_price_score_estimate", "peak_hour", "fetch_ts", "created_at",
            "origin", "synced_at",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.text)

    def test_details_escape_content_and_restrict_links(self):
        self.assertIn("function esc(s)", self.text)
        self.assertIn("url.protocol !== 'http:' && url.protocol !== 'https:'", self.text)
        self.assertIn("function fmtBool(value)", self.text)
        self.assertIn("colspan=\"5\"", self.text)


if __name__ == "__main__":
    unittest.main()
