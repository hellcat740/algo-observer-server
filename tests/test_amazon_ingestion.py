"""Amazon.com 观测入库与看板币种展示回归测试。"""
import unittest
import zipfile
from pathlib import Path

from api.app.cleaning import clean_observation
from api.app.schemas import ObservationIn

ROOT = Path(__file__).resolve().parent.parent


class AmazonIngestionTest(unittest.TestCase):
    def test_clean_amazon_usd_observation(self):
        observation = ObservationIn(
            platform_code="amazon",
            product_id="B0HF7H35WS",
            product_name="Gaming PC",
            product_url="https://www.amazon.com/dp/B0HF7H35WS",
            display_price_cents=2669.0,
            actual_pay_price_cents=1199.99,
            currency="USD",
            user_agent="test-agent",
        )
        cleaned, _warnings, _anonymous_id = clean_observation(observation)
        self.assertEqual(cleaned["platform_code"], "amazon")
        self.assertEqual(cleaned["display_price_cents"], 266900)
        self.assertEqual(cleaned["actual_pay_price_cents"], 119999)
        self.assertEqual(cleaned["currency"], "USD")

    def test_amazon_display_names_registered(self):
        for page in ("me.html", "lab.html", "overview.html"):
            with self.subTest(page=page):
                text = (ROOT / "api" / "app" / "static" / page).read_text(encoding="utf-8")
                self.assertIn("amazon: '亚马逊'", text)

    def test_personal_dashboard_formats_usd(self):
        text = (ROOT / "api" / "app" / "static" / "me.html").read_text(encoding="utf-8")
        self.assertIn("function fmtCents(c, currency)", text)
        self.assertIn("fmtCents(o.display_price_cents, o.currency)", text)
        self.assertIn("fmtCents(o.actual_pay_price_cents, o.currency)", text)

    def test_local_report_formats_usd(self):
        with zipfile.ZipFile(ROOT / "api" / "app" / "static" / "plugin.zip") as zf:
            text = zf.read("report/report.js").decode("utf-8")
        self.assertIn('amazon: "亚马逊"', text)
        self.assertIn('r.price.currency === "USD" ? "$" : "¥"', text)


if __name__ == "__main__":
    unittest.main()
