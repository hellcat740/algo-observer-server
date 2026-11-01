"""我的看板三维观测入口与普通用户访问权限测试。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


class UserSpaceAccessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.me = (API_DIR / "app" / "static" / "me.html").read_text(encoding="utf-8")
        cls.source = (API_DIR / "app" / "static" / "js" / "user-space.js").read_text(encoding="utf-8")

    def test_user_dashboard_embeds_user_space_below_overview(self):
        overview = self.me.index('data-tab="overview"')
        space = self.me.index('data-tab="user-space"')
        lab = self.me.index('data-tab="lab"')
        self.assertLess(overview, space)
        self.assertLess(space, lab)
        self.assertIn('id="tab-user-space"', self.me)
        self.assertIn("'user-space': '/user-space?embed=1'", self.me)

    def test_user_space_uses_user_identity_without_admin_key(self):
        self.assertIn("obs_user_id", self.source)
        self.assertIn("X-User-Id", self.source)
        self.assertIn("/api/my/space/points", self.source)
        self.assertNotIn("请先在管理控制台登录", self.source)

    def test_user_space_admin_console_link_requires_login(self):
        page = self.client.get("/user-space").text
        self.assertIn('<a href="/admin-login">管理控制台</a>', page)
        self.assertNotIn('<a href="/console">管理控制台</a>', page)

    def test_space_points_accept_user_id_and_still_require_identity(self):
        user_id = "123e4567-e89b-42d3-a456-426614174000"
        response = self.client.get("/api/my/space/points", headers={"X-User-Id": user_id})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("points", response.json())
        self.assertEqual(self.client.get("/api/my/space/points").status_code, 401)


if __name__ == "__main__":
    unittest.main()
