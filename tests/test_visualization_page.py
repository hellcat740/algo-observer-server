import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "api/app/static/visualization.html"
API_DIR = ROOT / "api"
sys.path.insert(0, str(API_DIR))

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


class VisualizationPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PAGE.read_text(encoding="utf-8")

    def test_page_loads_points_and_preserves_original_values(self):
        self.assertIn("/api/analysis/visualization-points", self.text)
        self.assertIn("chartablePoints", self.text)
        self.assertIn("normalized_price_cents", self.text)
        self.assertIn("basis_price_cents", self.text)
        self.assertIn("categoryColor", self.text)
        self.assertIn("platformShape", self.text)
        self.assertIn("原始价格", self.text)
        self.assertIn("需人工复核", self.text)
        self.assertNotIn("DEEPSEEK_API_KEY", self.text)

    def test_only_analysis_links_to_visualization(self):
        index = (ROOT / "api/app/static/index.html").read_text(encoding="utf-8")
        analysis = (ROOT / "api/app/static/analysis.html").read_text(encoding="utf-8")
        sidebar = index.split('<nav class="sidebar">', 1)[1].split("</nav>", 1)[0]
        self.assertNotIn('href="/visualization"', sidebar)
        self.assertIn('href="/visualization"', analysis)

    def test_page_route_returns_visualization(self):
        response = TestClient(app).get("/visualization")
        self.assertEqual(response.status_code, 200)
        self.assertIn("高维可视化", response.text)

    def test_javascript_syntax(self):
        match = re.search(r"<script>([\s\S]*?)</script>", self.text)
        self.assertIsNotNone(match)
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        self.assertIsNotNone(node, "运行 JavaScript 测试需要 Node.js")
        with tempfile.TemporaryDirectory(prefix="visualization-js-") as tmp:
            script = Path(tmp) / "visualization.js"
            script.write_text(match.group(1), encoding="utf-8")
            subprocess.run([node, "--check", str(script)], check=True, capture_output=True, text=True)

    def test_only_normalized_points_enter_chart_but_raw_points_remain(self):
        start = self.text.index("function chartablePoints")
        end = self.text.index("\nfunction ", start + 10)
        function = self.text[start:end]
        script = function + """
const points = [
  {fetch_ts:'2026-10-29T00:00:00+00:00',normalized_price_cents:1000},
  {fetch_ts:'2026-10-29T00:00:00+00:00',normalized_price_cents:null}
];
const chartable = chartablePoints(points);
if (chartable.length !== 1) throw Error('null normalized price must not be plotted');
if (points.length !== 2) throw Error('raw points must remain available');
"""
        node = os.environ.get("KIMI_DESKTOP_RUNTIME_NODE") or shutil.which("node") or shutil.which("node.exe")
        subprocess.run([node, "-e", script], check=True, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
