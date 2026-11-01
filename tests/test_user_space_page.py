import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

NODE = shutil.which("node")
if not NODE and os.environ.get("APPDATA"):
    managed_node = Path(os.environ["APPDATA"]) / "kimi-desktop" / "daimon-share" / "daimon" / "command-process-owner" / "bin" / "node"
    if managed_node.exists():
        NODE = str(managed_node)


class UserSpacePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_user_space_route_uses_existing_session_and_local_three(self):
        response = self.client.get("/user-space")
        self.assertEqual(response.status_code, 200, response.text)
        for marker in (
            "用户分簇三维观测", "/space", "obs_api_key", "/static/js/user-space.js",
            '"/static/vendor/three.module.min.js"', "统计疑似不等于法律认定",
        ):
            self.assertIn(marker, response.text)
        self.assertNotIn('type="password"', response.text)
        self.assertNotIn("unpkg.com", response.text)

    def test_user_space_reuses_comparison_rules_and_draws_native_lines(self):
        source = (API_DIR / "app" / "static" / "js" / "user-space.js").read_text(encoding="utf-8")
        for marker in (
            "buildUserClusterLayout", "categoryColor", "buildAnalyzableComparisonGroups",
            "buildComparisonGeometry", "comparePriceGroups", "new THREE.Line(geometry, material)",
            "opacity: 0.45", "/api/space/points",
        ):
            self.assertIn(marker, source)
        for removed in ("SphereGeometry", "CylinderGeometry", "updateComparisonVisuals"):
            self.assertNotIn(removed, source)
        for module in ("user-space.js", "user-space-layout.js"):
            subprocess.run([NODE, "--check", str(API_DIR / "app" / "static" / "js" / module)], check=True)

    def test_research_labels_stay_bright_after_shared_theme_loads(self):
        page = self.client.get("/user-space").text
        theme_position = page.index('href="/static/css/balance-theme.css"')
        for marker in (
            ".instrument-page h2{color:#fffdf7}",
            ".instrument-page .scene-head span,.instrument-page .layers label",
            ".instrument-page .legend,.instrument-page .detail",
            ".instrument-page .legend i{color:#f6d98a}",
        ):
            self.assertIn(marker, page)
            self.assertGreater(page.index(marker), theme_position)

    def test_original_space_links_to_user_cluster_space(self):
        self.assertIn('href="/user-space"', self.client.get("/space").text)


if __name__ == "__main__":
    unittest.main()
