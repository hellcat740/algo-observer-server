import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.exchange_rates import ExchangeRateUnavailable  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Observation, ProductCategoryCache  # noqa: E402
from app.product_categories import cache_key, product_key  # noqa: E402


ADMIN_KEY = "adm_0e606056c947a33fa94b9339"
USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)


class VisualizationApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            product = Observation(
                observation_id="viz-seed",
                user_ref=USER_A,
                platform_code="jd",
                product_id="PHONE-1",
                product_name="华为 Mate 70 智能手机",
                seller_id=None,
                product_url="https://item.jd.com/PHONE-1.html",
                display_price_cents=599900,
                actual_pay_price_cents=589900,
                currency="CNY",
                user_agent="test",
                fetch_ts=NOW,
            )
            db.add(product)
            db.add(Observation(
                observation_id="viz-2",
                user_ref=USER_B,
                platform_code="jd",
                product_id="PHONE-1",
                product_name=product.product_name,
                seller_id=None,
                product_url=product.product_url,
                display_price_cents=629900,
                actual_pay_price_cents=None,
                currency="CNY",
                user_agent="test",
                fetch_ts=NOW,
            ))
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

    def get(self, path="/api/analysis/visualization-points", authenticated=True):
        headers = {"X-API-Key": ADMIN_KEY} if authenticated else {}
        return self.client.get(path, headers=headers)

    def test_requires_admin_credentials(self):
        self.assertEqual(self.get(authenticated=False).status_code, 401)

    def test_returns_one_classification_and_two_complete_points(self):
        response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["points"]), 2)
        self.assertEqual(len(body["classifications"]), 1)
        self.assertEqual(body["classifications"][0]["category_l3"], "智能手机")
        self.assertEqual(body["meta"]["total"], 2)
        self.assertEqual(body["meta"]["normalized_total"], 2)
        self.assertEqual(body["meta"]["review_total"], 0)
        self.assertEqual(body["points"][0]["category_l1"], "手机数码")
        self.assertNotIn("user_ref", body["points"][0])
        self.assertNotIn(USER_A, response.text)
        self.assertNotIn(USER_B, response.text)

    def test_filters_before_and_after_classification(self):
        for query in (
            "?platform_code=jd",
            "?product_id=PHONE-1",
            "?currency=CNY",
            "?category_l1=手机数码",
        ):
            with self.subTest(query=query):
                response = self.get("/api/analysis/visualization-points" + query)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(response.json()["points"]), 2)
        response = self.get("/api/analysis/visualization-points?category_l1=家用电器")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["points"], [])
        self.assertEqual(response.json()["classifications"], [])

    def test_unavailable_usd_rate_keeps_original_points_without_normalizing(self):
        with self.Session() as db:
            db.query(Observation).update({"currency": "USD"})
            db.commit()
        with patch("app.analysis_api.latest_rate", side_effect=ExchangeRateUnavailable("offline")):
            response = self.get()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["meta"]["total"], 2)
        self.assertEqual(body["meta"]["normalized_total"], 0)
        self.assertTrue(body["meta"]["warnings"])
        self.assertTrue(all(point["currency"] == "USD" for point in body["points"]))
        self.assertTrue(all(point["normalized_price_cents"] is None for point in body["points"]))
        self.assertTrue(all(point["basis_price_cents"] is not None for point in body["points"]))


if __name__ == "__main__":
    unittest.main()
