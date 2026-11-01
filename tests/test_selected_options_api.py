"""已选规格 API 入库、输出和旧库迁移测试。"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

API_DIR = Path(__file__).resolve().parent.parent / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base, get_db  # noqa: E402
from app.main import _migrate_lightweight, app  # noqa: E402
from app.models import Observation  # noqa: E402

INGEST_KEY = "ing_76b1aafdb8aa410c73c28139"
ADMIN_KEY = "adm_0e606056c947a33fa94b9339"

class SelectedOptionsApiTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread":False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
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

    def test_options_round_trip(self):
        payload = {
            "platform_code":"taobao", "product_id":"906092642193", "sku_id":"5827913353815",
            "selected_options":[{"name":"颜色","value":"黑色"},{"name":"尺码","value":"L"}],
            "product_name":"多规格测试商品", "product_url":"https://item.taobao.com/item.htm?id=906092642193",
            "display_price_cents":8000, "user_agent":"selected-options-test",
        }
        response = self.client.post("/api/observations",json=payload,headers={"X-API-Key":INGEST_KEY})
        self.assertEqual(response.status_code,201,response.text)
        observation_id = response.json()["observation_id"]
        with self.Session() as db:
            saved = db.get(Observation,observation_id)
            self.assertEqual(saved.sku_id,"5827913353815")
            self.assertEqual(saved.selected_options,payload["selected_options"])
        detail = self.client.get(f"/api/observations/{observation_id}",headers={"X-API-Key":ADMIN_KEY})
        self.assertEqual(detail.status_code,200,detail.text)
        self.assertEqual(detail.json()["selected_options"],payload["selected_options"])
        self.assertEqual(detail.json()["sku_id"],payload["sku_id"])

    def test_old_observations_default_to_null(self):
        payload = {
            "platform_code":"jd", "product_id":"OLD-1", "product_name":"旧插件商品",
            "product_url":"https://item.jd.com/OLD-1.html", "display_price_cents":100,
            "user_agent":"old-client",
        }
        response = self.client.post("/api/observations",json=payload,headers={"X-API-Key":INGEST_KEY})
        self.assertEqual(response.status_code,201,response.text)
        with self.Session() as db:
            saved = db.get(Observation,response.json()["observation_id"])
            self.assertIsNone(saved.sku_id)
            self.assertIsNone(saved.selected_options)

    def test_lightweight_migration_adds_option_columns(self):
        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE observations (observation_id VARCHAR(36) PRIMARY KEY)"))
        with patch("app.main.engine",engine):
            _migrate_lightweight()
        columns = {column["name"] for column in inspect(engine).get_columns("observations")}
        self.assertIn("sku_id",columns)
        self.assertIn("selected_options",columns)
        engine.dispose()

if __name__ == "__main__":
    unittest.main()
