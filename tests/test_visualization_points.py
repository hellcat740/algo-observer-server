import hashlib
import json
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from app.visualization import (  # noqa: E402
    build_visualization_point,
    build_visualization_points,
    user_pseudonym,
)


USER_REF = "7a2d01a2-7490-4b25-9527-17ed35f1f73f"
POINT_FIELDS = {
    "observation_id", "fetch_ts", "user_pseudonym", "platform_code",
    "product_id", "product_key", "seller_id", "product_name", "category_l1",
    "category_l2", "category_confidence", "display_price_cents",
    "actual_pay_price_cents", "basis_price_cents", "price_basis", "currency",
    "normalized_price_cents", "exchange_rate", "exchange_rate_date",
    "exchange_stale", "promo_type", "promo_label", "is_login",
    "membership_level", "is_new_user", "register_days", "ip_city",
    "shipping_city", "platform", "device_price_score_estimate", "stock_hint",
    "peak_hour", "dom_price_text", "has_screenshot", "has_dom_snapshot",
    "source_code_version",
}


def make_observation(**overrides):
    values = {
        "observation_id": "obs-1",
        "fetch_ts": datetime(2026, 10, 29, 12, 0, 0),
        "user_ref": USER_REF,
        "platform_code": "amazon",
        "product_id": "A-100",
        "seller_id": "seller-1",
        "product_name": "Apple iPhone 15 Pro Max 智能手机",
        "display_price_cents": 1000,
        "actual_pay_price_cents": 900,
        "currency": "CNY",
        "promo_type": "coupon",
        "promo_label": "测试优惠",
        "is_login": True,
        "membership_level": "gold",
        "is_new_user": False,
        "register_days": 30,
        "ip_city": "上海",
        "shipping_city": "北京",
        "platform": "Win32",
        "device_price_score_estimate": 80,
        "stock_hint": "现货",
        "peak_hour": True,
        "dom_price_text": "$10.00",
        "screenshot_path": "screenshots/obs-1.png",
        "dom_snapshot_path": "dom/obs-1.html",
        "source_code_version": "1.1.0",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_classification(**overrides):
    values = {
        "product_key": "p" * 64,
        "category_l1": "手机数码",
        "category_l2": "手机",
        "confidence": 0.96,
    }
    values.update(overrides)
    return values


class VisualizationPointTest(unittest.TestCase):
    def test_cny_display_price_is_the_complete_point_basis(self):
        point = build_visualization_point(make_observation(), make_classification())
        self.assertEqual(set(point), POINT_FIELDS)
        self.assertEqual(point["basis_price_cents"], 1000)
        self.assertEqual(point["price_basis"], "DISPLAY")
        self.assertEqual(point["normalized_price_cents"], 1000)
        self.assertEqual(point["exchange_rate"], 1.0)
        self.assertIsNone(point["exchange_rate_date"])
        self.assertFalse(point["exchange_stale"])
        self.assertEqual(point["display_price_cents"], 1000)
        self.assertEqual(point["actual_pay_price_cents"], 900)
        self.assertEqual(point["category_confidence"], 0.96)
        self.assertTrue(point["has_screenshot"])
        self.assertTrue(point["has_dom_snapshot"])

    def test_usd_actual_price_fallback_uses_supplied_rate(self):
        observation = make_observation(
            display_price_cents=None, actual_pay_price_cents=900, currency="USD"
        )
        point = build_visualization_point(
            observation,
            make_classification(),
            {"rate": 7.2, "rate_date": "2026-10-29", "stale": False},
        )
        self.assertEqual(point["basis_price_cents"], 900)
        self.assertEqual(point["price_basis"], "ACTUAL")
        self.assertEqual(point["normalized_price_cents"], 6480)
        self.assertEqual(point["exchange_rate"], 7.2)
        self.assertEqual(point["exchange_rate_date"], "2026-10-29")
        self.assertFalse(point["exchange_stale"])
        self.assertEqual(point["actual_pay_price_cents"], 900)

    def test_stale_rate_is_preserved_and_marked(self):
        observation = make_observation(currency="USD")
        point = build_visualization_point(
            observation,
            make_classification(),
            {"rate": 7.1, "rate_date": "2026-10-28", "stale": True},
        )
        self.assertEqual(point["normalized_price_cents"], 7100)
        self.assertEqual(point["exchange_rate_date"], "2026-10-28")
        self.assertTrue(point["exchange_stale"])

    def test_missing_rate_and_unsupported_currency_do_not_normalize(self):
        usd = build_visualization_point(
            make_observation(currency="USD"), make_classification(), None
        )
        eur = build_visualization_point(
            make_observation(currency="EUR"),
            make_classification(),
            {"rate": 7.2, "rate_date": "2026-10-29", "stale": False},
        )
        for point in (usd, eur):
            self.assertIsNone(point["normalized_price_cents"])
            self.assertIsNone(point["exchange_rate"])
            self.assertIsNone(point["exchange_rate_date"])
            self.assertFalse(point["exchange_stale"])
            self.assertEqual(point["basis_price_cents"], 1000)

    def test_normalization_rounds_half_up_to_integer_cents(self):
        point = build_visualization_point(
            make_observation(display_price_cents=101, currency="USD"),
            make_classification(),
            {"rate": 7.005, "rate_date": "2026-10-29", "stale": False},
        )
        self.assertEqual(point["normalized_price_cents"], 708)

    def test_stable_pseudonym_and_raw_uuid_never_leak(self):
        expected = "u_" + hashlib.sha256(USER_REF.encode("utf-8")).hexdigest()[:10]
        self.assertEqual(user_pseudonym(USER_REF), expected)
        point = build_visualization_point(make_observation(), make_classification())
        self.assertEqual(point["user_pseudonym"], expected)
        self.assertNotIn("user_ref", point)
        self.assertNotIn(USER_REF, json.dumps(point, ensure_ascii=False))
        self.assertIsNone(user_pseudonym(None))
        self.assertIsNone(
            build_visualization_point(
                make_observation(user_ref=None), make_classification()
            )["user_pseudonym"]
        )

    def test_fetch_time_is_utc_and_evidence_flags_use_path_presence(self):
        aware = make_observation(
            fetch_ts=datetime(2026, 10, 29, 20, 0, tzinfo=timezone(timedelta(hours=8))),
            screenshot_path="",
            dom_snapshot_path=None,
        )
        point = build_visualization_point(aware, make_classification())
        self.assertEqual(point["fetch_ts"], "2026-10-29T12:00:00+00:00")
        self.assertFalse(point["has_screenshot"])
        self.assertFalse(point["has_dom_snapshot"])
        naive = build_visualization_point(make_observation(), make_classification())
        self.assertEqual(naive["fetch_ts"], "2026-10-29T12:00:00+00:00")

    def test_batch_builder_preserves_observation_order(self):
        first = make_observation()
        second = make_observation(observation_id="obs-2")
        key = hashlib.sha256(
            json.dumps(
                ["amazon", "A-100", "seller-1", first.product_name],
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        points = build_visualization_points(
            [first, second], {key: make_classification()}
        )
        self.assertEqual([point["observation_id"] for point in points], ["obs-1", "obs-2"])


if __name__ == "__main__":
    unittest.main()
