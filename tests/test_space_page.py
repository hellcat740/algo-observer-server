import base64
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

    def test_scene_uses_required_three_primitives_and_interactions(self):
        source = (API_DIR / "app" / "static" / "js" / "space.js").read_text(encoding="utf-8")
        for token in (
            "THREE.Points", "THREE.BufferGeometry", "THREE.LineSegments",
            "THREE.Raycaster", "OrbitControls", "normalized_price_cents",
            "PRICE_GAP", "toCSV", "play", "window.innerWidth",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        subprocess.run([NODE, "--check", str(API_DIR / "app" / "static" / "js" / "space.js")], check=True)

    def test_pure_coordinate_filter_and_csv_behavior(self):
        core = (API_DIR / "app" / "static" / "js" / "space-core.js").read_bytes()
        module = base64.b64encode(core).decode("ascii")
        script = """
import { businessCoordinates, featureProjection, filterPoints, toCSV } from 'data:text/javascript;base64,%s';
const points = [
 {observation_id:'a',fetch_ts:'2026-10-29T00:00:00Z',user_pseudonym:'u_a',product_key:'p1',product_id:'P1',product_name:'手机, "Pro"',category_l1:'手机数码',platform_code:'jd',currency:'CNY',basis_price_cents:1000,normalized_price_cents:1000,price_deviation:-0.1,promo_type:'none',promo_label:'',ip_city:'上海',price_gap_direction:'LOW'},
 {observation_id:'b',fetch_ts:'2026-10-29T01:00:00Z',user_pseudonym:'u_b',product_key:'p1',product_id:'P1',product_name:'手机',category_l1:'手机数码',platform_code:'jd',currency:'CNY',basis_price_cents:1200,normalized_price_cents:1200,price_deviation:0.1,promo_type:'coupon',promo_label:'券',ip_city:'北京',price_gap_direction:'HIGH',price_gap_suspected:true}
];
const coords = businessCoordinates(points);
if (coords.length !== 2 || coords[0].position[0] !== -50 || coords[1].position[0] !== 50) throw new Error('business coordinates');
if (coords[0].position[2] >= 0 || coords[1].position[2] <= 0) throw new Error('price deviation');
const projection = featureProjection(points[0]);
if (projection.length !== 3 || projection.some(value => !Number.isFinite(value))) throw new Error('projection');
if (JSON.stringify(projection) !== JSON.stringify(featureProjection(points[0]))) throw new Error('not deterministic');
if (filterPoints(points, {platform:'jd',promo:'yes'}).length !== 1) throw new Error('promo filter');
if (filterPoints(points, {search:'pro',city:'上海'}).length !== 1) throw new Error('search filter');
if (filterPoints(points, {start:'2026-10-29T00:30:00Z'}).length !== 1) throw new Error('time filter');
const csv = toCSV(points);
if (!csv.includes('u_a') || csv.includes('user_ref') || csv.includes('user_agent')) throw new Error('CSV privacy');
if (!csv.includes('""Pro""')) throw new Error('CSV escaping');
console.log('space core behavior ok');
""" % module
        result = subprocess.run(
            [NODE, "--input-type=module"],
            input=script, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("space core behavior ok", result.stdout)

    def test_mock_statistics_follow_the_sample_size_rule(self):
        source = (API_DIR / "app" / "static" / "js" / "space-mock.js").read_bytes()
        module = base64.b64encode(source).decode("ascii")
        script = """
import { createMockData } from 'data:text/javascript;base64,%s';
const data = createMockData();
if (data.statistics.some(stat => stat.n_a >= 3 && stat.n_b >= 3 && stat.status !== 'TESTS_AVAILABLE')) throw new Error('mock sample status');
if (data.points.some(point => point.statistical_status !== 'TESTS_AVAILABLE')) throw new Error('mock point status');
console.log('mock statistics ok');
""" % module
        result = subprocess.run(
            [NODE, "--input-type=module"], input=script,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mock statistics ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
