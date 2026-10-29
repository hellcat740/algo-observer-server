import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from app.space import (  # noqa: E402
    build_edges,
    compute_price_statistics,
    enrich_points,
    platform_replication,
)


BASE_TIME = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def make_point(
    observation_id,
    user="u_a",
    product_key="p1",
    product_id="P1",
    platform="jd",
    price=1000,
    hours=0,
    promo="none",
    label="",
    currency="CNY",
):
    return {
        "observation_id": observation_id,
        "fetch_ts": (BASE_TIME + timedelta(hours=hours)).isoformat(),
        "user_pseudonym": user,
        "platform_code": platform,
        "product_id": product_id,
        "product_key": product_key,
        "product_name": "测试商品",
        "category_l1": "手机数码",
        "category_l2": "手机",
        "category_confidence": 0.9,
        "currency": currency,
        "normalized_price_cents": price,
        "promo_type": promo,
        "promo_label": label,
    }


def edge_set(edges):
    return {(edge["type"], edge["source"], edge["target"]) for edge in edges}


class SpaceComputationTest(unittest.TestCase):
    def test_field_driven_relationship_types(self):
        points = [
            make_point("a1", hours=0),
            make_point("a2", hours=12),
            make_point("b1", user="u_b", price=1200, hours=1, promo="coupon", label="券"),
            make_point("c1", product_key="p2", product_id="P2", hours=2),
            make_point("late", hours=49),
        ]
        statistics = compute_price_statistics(points)
        edges, candidate_count, truncated = build_edges(points, statistics)
        relations = edge_set(edges)
        self.assertIn(("SAME_PRODUCT", "a1", "b1"), relations)
        self.assertIn(("SAME_USER", "a1", "c1"), relations)
        self.assertIn(("SAME_USER_PRODUCT", "a1", "a2"), relations)
        self.assertIn(("TIME_NEIGHBOR", "a1", "a2"), relations)
        self.assertIn(("PROMO_DIFFERENCE", "a1", "b1"), relations)
        self.assertIn(("PRICE_GAP", "a1", "b1"), relations)
        self.assertNotIn(("TIME_NEIGHBOR", "a1", "late"), relations)
        self.assertFalse(truncated)
        self.assertEqual(candidate_count, len(edges))

    def test_price_gap_uses_max_median_denominator_and_five_percent_threshold(self):
        points = [
            make_point("a", user="u_a", price=10000),
            make_point("b", user="u_b", price=10500),
        ]
        statistics = compute_price_statistics(points)
        self.assertEqual(len(statistics), 1)
        self.assertAlmostEqual(statistics[0]["diff_percent"], 500 / 10500 * 100)
        self.assertFalse(statistics[0]["suspected"])
        points[1]["normalized_price_cents"] = 10527
        self.assertTrue(compute_price_statistics(points)[0]["suspected"])
        points[1]["normalized_price_cents"] = 10499
        self.assertFalse(compute_price_statistics(points)[0]["suspected"])

    def test_null_and_unsupported_currency_never_create_price_gap(self):
        points = [
            make_point("eur1", user="u_a", price=None, currency="EUR"),
            make_point("eur2", user="u_b", price=None, currency="EUR"),
            make_point("usd1", user="u_c", price=None, currency="USD"),
        ]
        statistics = compute_price_statistics(points)
        edges, _, _ = build_edges(points, statistics)
        self.assertEqual(statistics, [])
        self.assertFalse(any(edge["type"] == "PRICE_GAP" for edge in edges))

    def test_relationship_limit_and_enabled_types(self):
        points = [make_point(f"p{index}", user=f"u_{index}") for index in range(46)]
        edges, candidate_count, truncated = build_edges(
            points, [], enabled={"SAME_PRODUCT"}, limit=1000
        )
        self.assertEqual(len(edges), 1000)
        self.assertGreater(candidate_count, 1000)
        self.assertTrue(truncated)
        self.assertTrue(all(edge["type"] == "SAME_PRODUCT" for edge in edges))

    def test_time_neighbor_threshold_is_configurable(self):
        points = [make_point("a", hours=0), make_point("b", user="u_b", hours=2)]
        edges, _, _ = build_edges(points, [], enabled={"TIME_NEIGHBOR"}, time_threshold_hours=1)
        self.assertEqual(edges, [])
        edges, _, _ = build_edges(points, [], enabled={"TIME_NEIGHBOR"}, time_threshold_hours=2)
        self.assertEqual(len(edges), 1)

    def test_small_sample_is_descriptive_only(self):
        points = [
            make_point("a1", user="u_a", price=1000),
            make_point("a2", user="u_a", price=1010),
            make_point("b1", user="u_b", price=1100),
            make_point("b2", user="u_b", price=1110),
        ]
        stat = compute_price_statistics(points)[0]
        self.assertEqual(stat["status"], "DESCRIPTIVE_SMALL_SAMPLE")
        self.assertIsNone(stat["mann_whitney_u"])
        self.assertIsNone(stat["mann_whitney_p"])
        self.assertIsNone(stat["welch_t"])
        self.assertIsNone(stat["welch_p"])
        self.assertTrue(stat["suspected"])

    def test_three_samples_enable_mann_whitney_and_welch(self):
        points = []
        for index, price in enumerate((1000, 1010, 1020)):
            points.append(make_point(f"a{index}", user="u_a", price=price))
        for index, price in enumerate((1100, 1110, 1120)):
            points.append(make_point(f"b{index}", user="u_b", price=price))
        stat = compute_price_statistics(points)[0]
        self.assertEqual(stat["status"], "TESTS_AVAILABLE")
        self.assertTrue(math.isfinite(stat["mann_whitney_u"]))
        self.assertTrue(math.isfinite(stat["mann_whitney_p"]))
        self.assertTrue(math.isfinite(stat["welch_t"]))
        self.assertTrue(math.isfinite(stat["welch_p"]))

    def test_constant_prices_never_emit_non_finite_test_values(self):
        points = []
        for index in range(3):
            points.append(make_point(f"a{index}", user="u_a", price=1000))
            points.append(make_point(f"b{index}", user="u_b", price=1000))
        stat = compute_price_statistics(points)[0]
        self.assertEqual(stat["status"], "TESTS_AVAILABLE")
        self.assertIsNone(stat["mann_whitney_p"])
        self.assertIsNone(stat["welch_t"])
        self.assertIsNone(stat["welch_p"])

    def test_zero_price_medians_do_not_divide_by_zero(self):
        points = [
            make_point("a", user="u_a", price=0),
            make_point("b", user="u_b", price=0),
        ]
        stat = compute_price_statistics(points)[0]
        self.assertEqual(stat["diff_percent"], 0.0)
        self.assertFalse(stat["suspected"])

    def test_enrichment_preserves_inputs_and_computes_sample_and_deviation(self):
        points = [
            make_point("a", user="u_a", price=1000),
            make_point("b", user="u_b", price=1200),
            make_point("null", user="u_c", price=None),
        ]
        original = [dict(point) for point in points]
        observations = [
            SimpleNamespace(observation_id="a", discount_coupon_amount_cents=100),
            SimpleNamespace(observation_id="b", discount_coupon_amount_cents=200),
            SimpleNamespace(observation_id="null", discount_coupon_amount_cents=None),
        ]
        enriched = enrich_points(points, observations)
        self.assertEqual(points, original)
        self.assertEqual(enriched[0]["sample_size"], 3)
        self.assertAlmostEqual(enriched[0]["price_deviation"], (1000 - 1100) / 1100)
        self.assertAlmostEqual(enriched[1]["price_deviation"], (1200 - 1100) / 1100)
        self.assertIsNone(enriched[2]["price_deviation"])
        self.assertEqual(enriched[0]["discount_coupon_amount_cents"], 100)
        self.assertEqual(enriched[0]["price_gap_direction"], "LOW")
        self.assertEqual(enriched[1]["price_gap_direction"], "HIGH")
        self.assertTrue(enriched[0]["price_gap_suspected"])
        self.assertEqual(enriched[0]["statistical_status"], "DESCRIPTIVE_SMALL_SAMPLE")

    def test_platform_suspicion_requires_two_products(self):
        points = [
            make_point("a1", product_key="p1", product_id="P1"),
            make_point("b1", user="u_b", product_key="p1", product_id="P1", price=1200),
            make_point("a2", product_key="p2", product_id="P2"),
            make_point("b2", user="u_b", product_key="p2", product_id="P2", price=1200),
        ]
        statistics = compute_price_statistics(points)
        replication = platform_replication(points, statistics)
        self.assertTrue(replication["jd"]["suspected"])
        self.assertEqual(replication["jd"]["product_count"], 2)
        one_product = platform_replication(points[:2], statistics[:1])
        self.assertFalse(one_product["jd"]["suspected"])


if __name__ == "__main__":
    unittest.main()
