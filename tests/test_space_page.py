import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


class SpacePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_space_page_is_research_only_and_uses_existing_admin_session(self):
        response = self.client.get("/space")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("三维观测空间", response.text)
        self.assertIn("统计疑似不等于法律认定，可视化结果仅用于研究线索筛查。", response.text)
        self.assertNotIn('type="password"', response.text)
        self.assertNotIn("unpkg.com", response.text)
        self.assertNotIn("user_ref", response.text)
        self.assertIn("obs_api_key", response.text)

    def test_local_three_runtime_and_import_map(self):
        page = self.client.get("/space").text
        self.assertIn('"/static/vendor/three.module.min.js"', page)
        self.assertIn('/static/js/space.js', page)
        three = self.client.get("/static/vendor/three.module.min.js")
        controls = self.client.get("/static/vendor/OrbitControls.js")
        self.assertEqual(three.status_code, 200)
        self.assertEqual(controls.status_code, 200)
        self.assertGreater(len(three.content), 100000)
        self.assertGreater(len(controls.content), 10000)
        self.assertIn("from 'three'", controls.text)

    def test_console_links_to_space(self):
        index = (API_DIR / "app" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="/space"', index)
        self.assertIn("三维数据空间", index)


if __name__ == "__main__":
    unittest.main()
