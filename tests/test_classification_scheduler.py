import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.classification_scheduler import find_uncached_products, next_run, run_idle_check, start_classification_scheduler  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import ProductCategoryCache  # noqa: E402
from app.product_categories import cache_key, product_key  # noqa: E402
from app.space_api import reset_classification_status  # noqa: E402
from tests.test_space_api import make_observation  # noqa: E402


class ClassificationSchedulerTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        reset_classification_status()

    def tearDown(self):
        reset_classification_status()
        self.engine.dispose()

    def add_products(self, count):
        with self.Session() as db:
            for index in range(count):
                observation = make_observation(f"product-{index}")
                observation.product_id = f"P-{index}"
                db.add(observation)
            db.commit()

    def test_next_run_uses_beijing_time_and_rolls_to_tomorrow(self):
        before = datetime(2026, 10, 29, 17, 16, tzinfo=timezone.utc)
        exact = datetime(2026, 10, 29, 17, 17, tzinfo=timezone.utc)
        self.assertEqual(next_run(before), exact)
        self.assertEqual(next_run(exact), exact + timedelta(days=1))

    def test_uncached_products_are_limited_to_100(self):
        self.add_products(101)
        with self.Session() as db:
            products = find_uncached_products(db)
        self.assertEqual(len(products), 100)
        self.assertEqual(set(vars(products[0])), {"platform_code", "product_id", "seller_id", "product_name", "product_url"})

    def test_cached_products_are_excluded(self):
        self.add_products(2)
        with self.Session() as db:
            from app.models import Observation
            product = db.query(Observation).first()
            db.add(ProductCategoryCache(
                cache_key=cache_key(product), product_key=product_key(product),
                product_id=product.product_id, seller_id=None, platform_code=product.platform_code,
                product_name=product.product_name, product_url=product.product_url,
                category_l1="手机数码", category_l2="手机", category_l3="",
                confidence=1.0, evidence="华为", needs_human_review=False, model_name="test",
            ))
            db.commit()
            self.assertEqual(len(find_uncached_products(db)), 1)

    def test_unconfigured_check_does_not_start_worker(self):
        self.add_products(1)
        worker = Mock()
        with patch.dict(os.environ, {}, clear=True):
            status = run_idle_check(session_factory=self.Session, worker=worker)
        worker.assert_not_called()
        self.assertEqual(status["status"], "not_configured")

    def test_empty_check_is_idle(self):
        worker = Mock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "configured"}, clear=True):
            status = run_idle_check(session_factory=self.Session, worker=worker)
        worker.assert_not_called()
        self.assertEqual(status["status"], "idle")

    def test_configured_check_passes_bounded_products_to_worker(self):
        self.add_products(1)
        worker = Mock()
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "configured"}, clear=True):
            run_idle_check(session_factory=self.Session, worker=worker)
        self.assertEqual(len(worker.call_args.args[0]), 1)
        self.assertEqual(worker.call_args.kwargs["session_factory"], self.Session)

    def test_scheduler_is_disabled_on_vercel_and_idempotent_elsewhere(self):
        start_classification_scheduler.started = False
        with patch.dict(os.environ, {"VERCEL": "1"}, clear=True):
            self.assertFalse(start_classification_scheduler())
        with patch.dict(os.environ, {}, clear=True), patch("app.classification_scheduler.threading.Thread") as thread:
            self.assertTrue(start_classification_scheduler())
            self.assertFalse(start_classification_scheduler())
            thread.assert_called_once()
            self.assertTrue(thread.call_args.kwargs["daemon"])
        start_classification_scheduler.started = False


if __name__ == "__main__":
    unittest.main()
