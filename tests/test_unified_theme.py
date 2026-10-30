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
