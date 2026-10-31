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
            "THREE.Points", "THREE.BufferGeometry",
            "THREE.Raycaster", "OrbitControls", "normalized_price_cents",
            "toCSV", "play", "window.innerWidth",
            "buildSemanticLayout", "userColor", "movementVector", "keydown",
            "CylinderGeometry", "categoryOpacity", "buildComparisonGeometry", "frameCamera",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        for removed in (
            "businessCoordinates", "featureProjection", "AxesHelper", "coordinateMode", "colorDimension",
            "comparisonCircleGeometry", "relationGroup", "renderRelations",
        ):
            self.assertNotIn(removed, source)
        subprocess.run([NODE, "--check", str(API_DIR / "app" / "static" / "js" / "space.js")], check=True)

    def test_grids_stay_in_world_coordinates_and_category_labels_are_restored(self):
        source = (API_DIR / "app" / "static" / "js" / "space.js").read_text(encoding="utf-8")
        grid_update = source[source.index("function updateGrids()"):source.index("function animate()")]
        self.assertNotIn("plane.position.set", grid_update)
        self.assertNotIn("controls.target.x", grid_update)
        self.assertNotIn("controls.target.y", grid_update)
        self.assertNotIn("controls.target.z", grid_update)
        for marker in (
            "function categoryLabel(category)", "new THREE.CanvasTexture(canvas)",
            "new THREE.SpriteMaterial", "categoryGroup.add(categoryLabel(category))",
            "type: 'label'", "selectedL2", "object.userData.type === 'volume'",
        ):
            self.assertIn(marker, source)
        category_update = source[source.index("function updateCategoryVisuals()"):source.index("function renderUserLegend()")]
        self.assertNotIn("object.position.z = controls.target.z;\n    const distance", category_update)

    def test_comparison_tree_uses_native_lines_and_is_automatically_framed(self):
        source = (API_DIR / "app" / "static" / "js" / "space.js").read_text(encoding="utf-8")
        for marker in (
            "comparison-link", "frameCamera(framingPositions)",
            "new THREE.BufferGeometry().setFromPoints([from, to])",
            "new THREE.LineBasicMaterial({color, transparent: true, opacity: 0.9, depthWrite: false})",
            "const link = new THREE.Line(geometry, material)",
        ):
            self.assertIn(marker, source)
        for removed in (
            "comparison-ellipsoid", "SphereGeometry", "wireframe", "descriptor.clusters",
            "updateComparisonVisuals", "distance * 0.0015", "new THREE.Mesh(\n    new THREE.CylinderGeometry(1, 1, length",
        ):
            self.assertNotIn(removed, source)

    def test_spatial_canvas_is_larger_on_desktop_and_narrow_screens(self):
        page = self.client.get("/space").text
        self.assertIn("#scene{height:clamp(720px,78vh,960px)}", page)
        self.assertIn("@media(max-width:1100px){#scene{height:720px}}", page)
        self.assertIn("@media(max-width:700px){#scene{height:640px}}", page)
        self.assertIn("grid-template-columns:minmax(0,1fr) 320px", page)

    def test_spatial_layers_replace_legacy_relation_controls(self):
        page = self.client.get("/space").text
        self.assertIn('data-layer="categories"', page)
        self.assertIn('data-layer="comparison"', page)
        self.assertIn("分类圆柱", page)
        self.assertIn("对比分析", page)
        self.assertNotIn("data-relation=", page)
        for relation in ("SAME_PRODUCT", "SAME_USER", "SAME_USER_PRODUCT", "TIME_NEIGHBOR", "PRICE_GAP", "PROMO_DIFFERENCE", "ACTIVE_COMPARISON"):
            self.assertNotIn(f'data-relation="{relation}"', page)

    def test_wasd_is_enabled_for_2d_and_3d_but_not_editable_controls(self):
        source = (API_DIR / "app" / "static" / "js" / "space.js").read_text(encoding="utf-8")
        self.assertEqual(source.count("!['2d', '3d'].includes(state.view)"), 2)
        self.assertNotIn("state.view !== '3d' || !pressedKeys.size", source)
        self.assertIn("editableTarget(event.target)", source)
        self.assertIn("target.matches('input,select,textarea,[contenteditable=", source)

    def test_pure_filter_and_csv_behavior(self):
        core = (API_DIR / "app" / "static" / "js" / "space-core.js").read_bytes()
        module = base64.b64encode(core).decode("ascii")
        script = """
import { filterPoints, toCSV } from 'data:text/javascript;base64,%s';
const points = [
 {observation_id:'a',fetch_ts:'2026-10-29T00:00:00Z',user_pseudonym:'u_a',product_key:'p1',product_id:'P1',product_name:'手机, "Pro"',category_l1:'手机数码',platform_code:'jd',currency:'CNY',basis_price_cents:1000,normalized_price_cents:1000,price_deviation:-0.1,promo_type:'none',promo_label:'',ip_city:'上海',price_gap_direction:'LOW'},
 {observation_id:'b',fetch_ts:'2026-10-29T01:00:00Z',user_pseudonym:'u_b',product_key:'p1',product_id:'P1',product_name:'手机',category_l1:'手机数码',platform_code:'jd',currency:'CNY',basis_price_cents:1200,normalized_price_cents:1200,price_deviation:0.1,promo_type:'coupon',promo_label:'券',ip_city:'北京',price_gap_direction:'HIGH',price_gap_suspected:true}
];
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
            input=script, capture_output=True, text=True, encoding="utf-8",
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
if (!data.category_taxonomy || !data.category_taxonomy['手机数码']?.includes('手机')) throw new Error('mock taxonomy');
console.log('mock statistics ok');
""" % module
        result = subprocess.run(
            [NODE, "--input-type=module"], input=script,
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mock statistics ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
