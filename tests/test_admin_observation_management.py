import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import ProductCategoryCache, User  # noqa: E402
from app.product_categories import cache_key, product_key  # noqa: E402
from tests.test_space_api import ADMIN_KEY, USER_A, USER_B, make_observation  # noqa: E402


class AdminObservationManagementTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            self.observation = make_observation()
            db.add(self.observation)
            db.add(User(anonymous_id=USER_A, observation_count=1))
            db.add(User(anonymous_id=USER_B, observation_count=2))
            db.commit()
            db.refresh(self.observation)
            self.oid = self.observation.observation_id
            db.add(ProductCategoryCache(
                cache_key=cache_key(self.observation), product_key=product_key(self.observation),
                product_id=self.observation.product_id, seller_id=None,
                platform_code=self.observation.platform_code,
                product_name=self.observation.product_name, product_url=self.observation.product_url,
                category_l1="手机数码", category_l2="手机", category_l3="智能手机",
                confidence=0.98, evidence="华为", needs_human_review=False, model_name="test",
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
        self.headers = {"X-API-Key": ADMIN_KEY}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()

    def test_categories_require_admin(self):
        response = self.client.post("/api/observations/categories", json={"observation_ids": [self.oid]})
        self.assertEqual(response.status_code, 401)

    def test_categories_read_cache_without_model_calls(self):
        with patch("app.product_categories._call_model", side_effect=AssertionError("model called")) as model:
            response = self.client.post(
                "/api/observations/categories",
                json={"observation_ids": [self.oid, self.oid, "missing"]}, headers=self.headers,
            )
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["items"]
        self.assertEqual(items[self.oid]["category_l1"], "手机数码")
        self.assertEqual(items[self.oid]["category_l2"], "手机")
        self.assertIsNone(items["missing"])
        self.assertEqual(model.call_count, 0)

    def edit_payload(self, **changes):
        response = self.client.get("/api/observations/" + self.oid, headers=self.headers)
        payload = response.json()
        for field in ("observation_id", "user_ref", "created_at", "origin", "synced_at"):
            payload.pop(field, None)
        payload["anonymous_id"] = USER_A
        payload.update(changes)
        return payload

    def test_edit_updates_fields_and_preserves_metadata(self):
        before = self.client.get("/api/observations/" + self.oid, headers=self.headers).json()
        payload = self.edit_payload(
            product_name="修改后的商品名称", seller_id="seller-new", actual_pay_price_cents=8800,
            currency="USD", is_login=False, is_new_user=None, peak_hour=True,
            membership_level="PLUS", platform="Win32", language="zh-CN",
            device_memory=16.0, hardware_concurrency=8, screen_resolution="1920x1080",
            device_price_score_estimate=75, ip_city="北京", shipping_city="上海",
            stock_hint="现货", dom_price_text="$99.00", source_code_version="edit-test",
            observation_id="must-not-change", created_at="2020-01-01T00:00:00Z",
            origin="pulled", synced_at="2020-01-01T00:00:00Z",
        )
        response = self.client.put("/api/observations/" + self.oid, json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["product_name"], "修改后的商品名称")
        self.assertEqual(body["seller_id"], "seller-new")
        self.assertEqual(body["actual_pay_price_cents"], 8800)
        self.assertEqual(body["currency"], "USD")
        self.assertFalse(body["is_login"])
        self.assertIsNone(body["is_new_user"])
        self.assertTrue(body["peak_hour"])
        self.assertEqual(body["device_memory"], 16.0)
        self.assertEqual(body["observation_id"], self.oid)
        self.assertEqual(body["created_at"], before["created_at"])
        self.assertEqual(body["origin"], before["origin"])
        self.assertEqual(body["synced_at"], before["synced_at"])

    def test_edit_reassigns_anonymous_user_counts(self):
        response = self.client.put(
            "/api/observations/" + self.oid,
            json=self.edit_payload(anonymous_id=USER_B), headers=self.headers,
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["user_ref"], USER_B)
        with self.Session() as db:
            self.assertEqual(db.query(User).filter_by(anonymous_id=USER_A).one().observation_count, 0)
            self.assertEqual(db.query(User).filter_by(anonymous_id=USER_B).one().observation_count, 3)

    def test_edit_validates_and_handles_auth_and_missing_records(self):
        self.assertEqual(self.client.put(
            "/api/observations/" + self.oid, json=self.edit_payload()
        ).status_code, 401)
        self.assertEqual(self.client.put(
            "/api/observations/" + self.oid, json=self.edit_payload(display_price_cents=0), headers=self.headers
        ).status_code, 422)
        self.assertEqual(self.client.put(
            "/api/observations/missing", json=self.edit_payload(), headers=self.headers
        ).status_code, 404)


if __name__ == "__main__":
    unittest.main()
