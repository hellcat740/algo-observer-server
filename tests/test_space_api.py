import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Observation, ProductCategoryCache  # noqa: E402
from app.product_categories import cache_key, product_key  # noqa: E402


ADMIN_KEY = "adm_0e606056c947a33fa94b9339"
USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


def make_observation(observation_id="space-1", user_ref=USER_A, price=10000, hours=0):
    return Observation(
        observation_id=observation_id,
        user_ref=user_ref,
        platform_code="jd",
        product_id="PHONE-1",
        product_name="华为 Mate 70 智能手机",
        seller_id=None,
        product_url="https://item.jd.com/PHONE-1.html",
        display_price_cents=price,
        actual_pay_price_cents=price - 100,
        discount_coupon_amount_cents=100,
        currency="CNY",
        user_agent="private-user-agent",
        fetch_ts=NOW + timedelta(hours=hours),
    )


class SpaceApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            db.add(make_observation())
            db.add(make_observation("space-2", USER_B, 12000, 1))
            db.commit()

        def override_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def get(self, path="/api/space/points", authenticated=True):
        headers = {"X-API-Key": ADMIN_KEY} if authenticated else {}
        return self.client.get(path, headers=headers)

    def add_cached_classification(self):
        with self.Session() as db:
            product = db.query(Observation).first()
            db.add(ProductCategoryCache(
                cache_key=cache_key(product),
                product_key=product_key(product),
                platform_code=product.platform_code,
                product_id=product.product_id,
                seller_id=None,
                product_name=product.product_name,
                product_url=product.product_url,
                category_l1="手机数码",
                category_l2="手机",
                category_l3="智能手机",
                confidence=0.98,
                evidence="华为 Mate 70",
                needs_human_review=False,
                model_name="test",
            ))
            db.commit()

    def test_requires_admin_credentials(self):
        self.assertEqual(self.get(authenticated=False).status_code, 401)

    def test_uncached_points_return_without_calling_model(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False), patch(
            "app.product_categories._call_deepseek",
            side_effect=AssertionError("model must not run in the points request"),
        ) as caller:
            response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(caller.call_count, 0)
        self.assertEqual(body["meta"]["total"], 2)
        self.assertEqual(body["meta"]["returned"], 2)
        self.assertEqual(body["meta"]["uncached_products"], 1)
        self.assertEqual(body["meta"]["classification_status"], "not_configured")
        self.assertTrue(all(point["category_l1"] == "" for point in body["points"]))
        self.assertTrue(all(point["category_l2"] == "" for point in body["points"]))
        self.assertNotIn(USER_A, response.text)
        self.assertNotIn(USER_B, response.text)
        self.assertNotIn("private-user-agent", response.text)
        self.assertNotIn("user_ref", body["points"][0])

    def test_cached_categories_statistics_and_edges_are_returned(self):
        self.add_cached_classification()
        response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["meta"]["uncached_products"], 0)
        self.assertTrue(all(point["category_l1"] == "手机数码" for point in body["points"]))
        self.assertEqual(body["statistics"][0]["status"], "DESCRIPTIVE_SMALL_SAMPLE")
        self.assertTrue(any(edge["type"] == "PRICE_GAP" for edge in body["edges"]))
        self.assertIn("jd", body["platform_replication"])
        self.assertFalse(body["platform_replication"]["jd"]["suspected"])

    def test_point_limit_returns_latest_and_separate_total(self):
        with self.Session() as db:
            db.add(make_observation("space-3", USER_A, 11000, 2))
            db.commit()
        response = self.get("/api/space/points?limit=2")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["meta"]["total"], 3)
        self.assertEqual(body["meta"]["returned"], 2)
        self.assertTrue(body["meta"]["truncated"])
        self.assertEqual(len(body["points"]), 2)
        self.assertEqual(body["points"][0]["observation_id"], "space-3")

    def test_cached_only_helper_needs_no_model(self):
        from app.product_categories import get_cached_classifications

        with self.Session() as db:
            observations = db.query(Observation).all()
            self.assertEqual(get_cached_classifications(db, observations), {})
            self.add_cached_classification()
        with self.Session() as db:
            observations = db.query(Observation).all()
            cached = get_cached_classifications(db, observations)
        self.assertEqual(cached[cache_key(observations[0])]["category_l2"], "手机")


class SpaceClassificationWorkerTest(unittest.TestCase):
    def setUp(self):
        from app import space_api

        self.space_api = space_api
        self.space_api.reset_classification_status()
        self.products = [SimpleNamespace(product_id=str(index)) for index in range(101)]

    def tearDown(self):
        self.space_api.reset_classification_status()

    def test_worker_processes_batches_and_resets_running_state(self):
        batches = []

        def classifier(db, products):
            batches.append(len(products))
            return {}, []

        session = SimpleNamespace(close=lambda: None)
        self.space_api.run_classification_worker(
            self.products,
            session_factory=lambda: session,
            classifier=classifier,
        )
        self.assertEqual(batches, [50, 50, 1])
        status = self.space_api.get_classification_status()
        self.assertEqual(status["status"], "success")
        self.assertEqual(status["processed"], 101)
        self.assertEqual(status["total"], 101)

    def test_worker_error_is_visible_and_not_left_running(self):
        def classifier(db, products):
            raise RuntimeError("private model failure")

        session = SimpleNamespace(close=lambda: None)
        self.space_api.run_classification_worker(
            self.products[:1],
            session_factory=lambda: session,
            classifier=classifier,
        )
        status = self.space_api.get_classification_status()
        self.assertEqual(status["status"], "error")
        self.assertEqual(status["processed"], 0)
        self.assertNotIn("private model failure", status["message"])


if __name__ == "__main__":
    unittest.main()
