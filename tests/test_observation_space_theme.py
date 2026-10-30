from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "api" / "app" / "static"


def test_visualization_pages_share_balance_theme():
    for name in ["visualization.html", "space.html"]:
        assert "/static/css/balance-theme.css" in (STATIC / name).read_text(encoding="utf-8")


def test_space_interaction_and_research_markers_remain():
    html = (STATIC / "space.html").read_text(encoding="utf-8")
    js = (STATIC / "js" / "space.js").read_text(encoding="utf-8")
    for marker in ["data-relation", "data-view", "platformFilter", "categoryFilter", "playPosition", "统计疑似不等于法律认定"]:
        assert marker in html
    for marker in ["businessCoordinates", "featureProjection", "filterPoints", "toCSV", "/api/space/points"]:
        assert marker in js
