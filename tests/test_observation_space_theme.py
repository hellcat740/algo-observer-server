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
    for marker in ["buildSemanticLayout", "movementVector", "userColor", "filterPoints", "toCSV", "/api/space/points"]:
        assert marker in js
    for removed in ["businessCoordinates", "featureProjection", "coordinateMode", "colorDimension", "AxesHelper"]:
        assert removed not in js
    assert "coordinateMode" not in html
    assert "colorDimension" not in html
    assert "ACTIVE_COMPARISON" in html
    assert "采集用户" in html


def test_space_and_dashboard_share_the_mixed_comparison_rule():
    space = (STATIC / "js" / "space.js").read_text(encoding="utf-8")
    dashboard = (STATIC / "lab.html").read_text(encoding="utf-8")
    for source in [space, dashboard]:
        assert "comparison-rule.js" in source
        assert "comparePriceGroups" in source
    assert "buildComparisonPairs" in space
    assert "{ name: A.u, prices: A.prices }" in dashboard
    assert "if (diffPct >= 5 && !r.smallSample)" not in dashboard
    assert "关注 ≥5 元且 ≥5%；严重 ≥10 元且 >20%，两侧各 ≥3" in dashboard
    assert "全局中位数统计（后端研究口径）" in (STATIC / "space.html").read_text(encoding="utf-8")
