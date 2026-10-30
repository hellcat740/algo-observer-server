import hashlib
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import ProductCategoryCache  # noqa: E402
from app.product_categories import (  # noqa: E402
    cache_key,
    classification_request,
    classify_products,
    deduplicate_products,
    product_key,
)


def make_product(**overrides):
    values = {
        "platform_code": "amazon",
        "product_id": "A-100",
        "seller_id": None,
        "product_name": "Apple iPhone 15 Pro Max 智能手机",
        "product_url": "https://www.amazon.com/dp/A-100",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def valid_classification(**overrides):
    values = {
        "product_key": "model-cannot-be-trusted",
        "product_id": "model-cannot-be-trusted",
        "seller_id": "model-cannot-be-trusted",
        "category_l1": "手机数码",
        "category_l2": "手机",
        "category_l3": "智能手机",
        "confidence": 0.96,
        "evidence": "iPhone 15 Pro Max",
        "needs_human_review": False,
    }
    values.update(overrides)
    return values


class FakeCaller:
    def __init__(self, response):
        self.response = response
        self.products = []

    def __call__(self, product):
        self.products.append(product)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    @property
    def calls(self):
        return len(self.products)


class ProductCategoryTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.product = make_product()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_product_and_cache_keys_have_distinct_stability(self):
        renamed = make_product(product_name="Apple iPhone 15 Pro 256GB")
        self.assertEqual(product_key(self.product), product_key(renamed))
        self.assertNotEqual(cache_key(self.product), cache_key(renamed))
        expected = hashlib.sha256(
            json.dumps(
                ["amazon", "A-100", ""], ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(product_key(self.product), expected)

    def test_deduplicates_observations_before_one_model_call(self):
        self.assertEqual(len(deduplicate_products([self.product, self.product])), 1)
        caller = FakeCaller(valid_classification())
        results, warnings = classify_products(
            self.db, [self.product, self.product], caller=caller
        )
        self.assertEqual(caller.calls, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(warnings, [])
        result = results[cache_key(self.product)]
        self.assertEqual(result["product_key"], product_key(self.product))
        self.assertEqual(result["product_id"], "A-100")
        self.assertEqual(result["seller_id"], "")
        self.assertEqual(result["category_l1"], "手机数码")
        self.assertFalse(result["needs_human_review"])

    def test_selected_qwen_model_is_persisted(self):
        with patch.dict(os.environ, {"CLASSIFICATION_PROVIDER": "qwen", "QWEN_API_KEY": "test-qwen"}, clear=False):
            results, warnings = classify_products(
                self.db, [self.product], caller=FakeCaller(valid_classification())
            )
        self.assertEqual(warnings, [])
        self.assertEqual(results[cache_key(self.product)]["model_name"], "qwen3.8flash")

    def test_cache_hit_avoids_repeated_model_call(self):
        first = FakeCaller(valid_classification())
        classify_products(self.db, [self.product], caller=first)
        second = FakeCaller(RuntimeError("must not be called"))
        results, warnings = classify_products(self.db, [self.product], caller=second)
        self.assertEqual(first.calls, 1)
        self.assertEqual(second.calls, 0)
        self.assertEqual(warnings, [])
        self.assertEqual(results[cache_key(self.product)]["category_l2"], "手机")

    def test_product_name_change_uses_a_new_cache_entry(self):
        classify_products(
            self.db, [self.product], caller=FakeCaller(valid_classification())
        )
        renamed = make_product(product_name="Apple iPhone 15 Pro 256GB 手机")
        caller = FakeCaller(valid_classification(evidence="iPhone 15 Pro"))
        classify_products(self.db, [renamed], caller=caller)
        self.assertEqual(caller.calls, 1)
        self.assertEqual(self.db.query(ProductCategoryCache).count(), 2)

    def test_model_request_contains_only_allowed_product_fields(self):
        request = classification_request(self.product)
        content = json.loads(request["messages"][1]["content"])
        self.assertEqual(
            set(content),
            {"product_name", "seller_id", "product_url", "platform_code"},
        )
        self.assertEqual(request["model"], "v4.1flash")
        self.assertEqual(request["response_format"], {"type": "json_object"})
        forbidden_keys = {
            "user_ref", "ip_city", "shipping_city", "membership_level",
            "is_login", "is_new_user", "platform", "device_price_score_estimate",
        }
        self.assertTrue(forbidden_keys.isdisjoint(content))

    def test_low_confidence_forces_human_review(self):
        caller = FakeCaller(valid_classification(confidence=0.5, needs_human_review=False))
        results, _ = classify_products(self.db, [self.product], caller=caller)
        result = results[cache_key(self.product)]
        self.assertEqual(result["confidence"], 0.5)
        self.assertTrue(result["needs_human_review"])

    def test_invalid_category_falls_back_without_caching(self):
        caller = FakeCaller(valid_classification(category_l1="不存在的分类"))
        results, warnings = classify_products(self.db, [self.product], caller=caller)
        result = results[cache_key(self.product)]
        self.assertEqual(result["category_l1"], "其他／无法判断")
        self.assertEqual(result["category_l2"], "无法判断")
        self.assertEqual(result["confidence"], 0.0)
        self.assertTrue(result["needs_human_review"])
        self.assertTrue(warnings)
        self.assertEqual(self.db.query(ProductCategoryCache).count(), 0)

    def test_invalid_evidence_falls_back(self):
        caller = FakeCaller(valid_classification(evidence="并非商品名称中的片段"))
        results, _ = classify_products(self.db, [self.product], caller=caller)
        self.assertEqual(
            results[cache_key(self.product)]["category_l1"], "其他／无法判断"
        )

    def test_missing_api_key_degrades_without_network_or_cache(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False):
            results, warnings = classify_products(self.db, [self.product])
        self.assertEqual(
            results[cache_key(self.product)]["category_l1"], "其他／无法判断"
        )
        self.assertTrue(warnings)
        self.assertEqual(self.db.query(ProductCategoryCache).count(), 0)

    def test_short_product_name_bypasses_model_and_is_stable(self):
        short = make_product(product_name="  书  ")
        caller = FakeCaller(RuntimeError("must not be called"))
        results, _ = classify_products(self.db, [short], caller=caller)
        result = results[cache_key(short)]
        self.assertEqual(caller.calls, 0)
        self.assertEqual(result["category_l1"], "其他／无法判断")
        self.assertTrue(result["needs_human_review"])
        self.assertEqual(self.db.query(ProductCategoryCache).count(), 1)


if __name__ == "__main__":
    unittest.main()
