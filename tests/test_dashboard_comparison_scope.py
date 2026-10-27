"""比对分析仅限当前用户已采集商品的回归测试。"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))
_tmp = tempfile.mkdtemp(prefix="observer-scope-test-")
os.chdir(_tmp)
os.environ["VERCEL"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp) / "obs.db")

from fastapi.testclient import TestClient  # noqa: E402
from index import app  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Observation  # noqa: E402

USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"
NOW = datetime.now(timezone.utc)


class DashboardComparisonScopeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        with SessionLocal() as db:
            rows = [
                ("a-jd-1", USER_A, "jd", "SHARED", "京东共享商品"),
                ("a-jd-2", USER_A, "jd", "SHARED", "京东共享商品"),
                ("a-amazon", USER_A, "amazon", "SHARED", "Amazon shared product"),
                ("a-other", USER_A, "jd", "ONLY-A", "专属商品"),
                ("b-other", USER_B, "jd", "ONLY-B", "他人商品"),
            ]
            for oid, user, platform, pid, name in rows:
                db.add(Observation(
                    observation_id=oid, user_ref=user, platform_code=platform,
                    product_id=pid, product_name=name, product_url="https://example.com/p",
                    display_price_cents=1000, user_agent="test", fetch_ts=NOW,
                ))
            db.commit()

    def get(self, path, user=USER_A):
        return self.client.get(path, headers={"X-User-Id": user})

    def test_my_products_are_scoped_and_grouped_by_platform(self):
        response = self.get("/api/pool/my-products")
        self.assertEqual(response.status_code, 200)
        products = response.json()["products"]
        keys = {(p["platform_code"], p["product_id"]) for p in products}
        self.assertEqual(keys, {("jd", "SHARED"), ("amazon", "SHARED"), ("jd", "ONLY-A")})
        jd_shared = next(p for p in products if p["platform_code"] == "jd" and p["product_id"] == "SHARED")
        self.assertEqual(jd_shared["n"], 2)

    def test_my_products_support_keyword_and_platform_filters(self):
        response = self.get("/api/pool/my-products?keyword=Amazon&platform_code=amazon")
        self.assertEqual([(p["platform_code"], p["product_id"]) for p in response.json()["products"]], [("amazon", "SHARED")])

    def test_my_products_requires_identity(self):
        self.assertEqual(self.client.get("/api/pool/my-products").status_code, 401)

    def test_pool_observations_filter_platform_and_product(self):
        response = self.get("/api/pool/observations?product_id=SHARED&platform_code=jd")
        self.assertEqual(response.status_code, 200)
        items = response.json()["items"]
        self.assertTrue(items)
        self.assertTrue(all(o["platform_code"] == "jd" and o["product_id"] == "SHARED" for o in items))

    def test_lab_uses_scoped_candidates_and_exact_product_matching(self):
        text = (Path(__file__).resolve().parent.parent / "api" / "app" / "static" / "lab.html").read_text(encoding="utf-8")
        self.assertIn("var url = '/api/pool/my-products?limit=100'", text)
        self.assertIn("api('/api/pool/my-products?limit=100')", text)
        self.assertIn("platform_code=' + encodeURIComponent(product.platform_code)", text)
        self.assertIn("product_id=' + encodeURIComponent(product.product_id)", text)
        self.assertNotIn("api('/api/pool/products?limit=100')", text)
        self.assertIn("本机已采集商品", text)


if __name__ == "__main__":
    unittest.main()
