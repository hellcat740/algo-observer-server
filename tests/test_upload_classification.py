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

INGEST_KEY = "ing_76b1aafdb8aa410c73c28139"
USER_ID = "11111111-1111-4111-8111-111111111111"


class UploadClassificationTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
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

    def test_observation_upload_runs_qwen_in_background(self):
        payload = {
            "platform_code": "taobao",
            "product_id": "UPLOAD-QWEN-1",
            "product_name": "自动分类测试智能手机",
            "product_url": "https://item.taobao.com/item.htm?id=UPLOAD-QWEN-1",
            "display_price_cents": 199900,
            "user_agent": "upload-classification-test",
        }
        with patch.dict(os.environ, {
            "UPLOAD_CLASSIFICATION_PROVIDER": "qwen", "QWEN_API_KEY": "test-qwen"
        }, clear=False), patch("app.space_api.run_classification_worker") as worker:
            response = self.client.post(
                "/api/observations", json=payload, headers={"X-API-Key": INGEST_KEY}
            )
        self.assertEqual(response.status_code, 201, response.text)
        worker.assert_called_once()
        self.assertEqual(worker.call_args.kwargs["provider"], "qwen")
        self.assertEqual(worker.call_args.args[0][0].product_id, "UPLOAD-QWEN-1")

    def test_pool_upload_classifies_only_new_observations(self):
        item = {
            "observation_id": "22222222-2222-4222-8222-222222222222",
            "platform_code": "jd",
            "product_id": "POOL-QWEN-1",
            "product_name": "批量上行自动分类笔记本电脑",
            "product_url": "https://item.jd.com/POOL-QWEN-1.html",
            "display_price_cents": 499900,
            "user_agent": "pool-upload-classification-test",
        }
        with patch.dict(os.environ, {
            "UPLOAD_CLASSIFICATION_PROVIDER": "qwen", "QWEN_API_KEY": "test-qwen"
        }, clear=False), patch("app.space_api.run_classification_worker") as worker:
            response = self.client.post(
                "/api/pool/sync", json={"items": [item]}, headers={"X-User-Id": USER_ID}
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["inserted"], 1)
        worker.assert_called_once()
        products = worker.call_args.args[0]
        self.assertEqual([product.product_id for product in products], ["POOL-QWEN-1"])
        self.assertEqual(worker.call_args.kwargs["provider"], "qwen")


if __name__ == "__main__":
    unittest.main()
