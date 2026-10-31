from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "api" / "app" / "static"


def test_balance_theme_contains_reference_palette_and_accessibility_rules():
    css = (STATIC / "css" / "balance-theme.css").read_text(encoding="utf-8")
    assert "--persimmon: #B85516" in css
    assert "--honey: #EAAE35" in css
    assert ":focus-visible" in css
    assert "prefers-reduced-motion" in css


def test_landing_loads_shared_theme_without_changing_primary_routes():
    html = (STATIC / "landing.html").read_text(encoding="utf-8")
    assert "/static/css/balance-theme.css" in html
    assert 'href="/me"' in html
    assert 'href="/admin-login"' in html
    assert 'href="/download"' in html


def test_landing_topbar_background_extends_to_viewport_edges():
    html = (STATIC / "landing.html").read_text(encoding="utf-8")
    assert ".topbar::before" in html
    assert "inset: 0 calc(50% - 50vw);" in html
    assert "isolation: isolate;" in html


def test_personal_dashboard_brand_uses_dark_text():
    html = (STATIC / "me.html").read_text(encoding="utf-8")
    assert ".side-head .brand { color: var(--ink); }" in html


def test_balance_fallback_is_accessible_and_self_contained():
    svg = (STATIC / "balance-fallback.svg").read_text(encoding="utf-8")
    assert 'role="img"' in svg
    assert "利益与算法的平衡" in svg
    assert "左侧价格与利益符号，右侧芯片与算法节点" in svg
    assert 'href="http' not in svg and "xlink:href=\"http" not in svg


def test_landing_has_accessible_balance_scene_and_module():
    html = (STATIC / "landing.html").read_text(encoding="utf-8")
    assert 'id="balanceScene"' in html
    assert "/static/js/balance-scene.js" in html
    assert 'type="importmap"' in html
    assert "/static/vendor/three.module.min.js" in html
