from pathlib import Path
import pytest

STATIC = Path(__file__).resolve().parents[1] / "api" / "app" / "static"


@pytest.mark.parametrize("name", ["index.html", "admin.html", "analysis.html", "admin-login.html", "download.html"])
def test_admin_pages_share_balance_theme(name):
    assert "/static/css/balance-theme.css" in (STATIC / name).read_text(encoding="utf-8")


def test_admin_behavior_markers_remain():
    console = (STATIC / "index.html").read_text(encoding="utf-8")
    login = (STATIC / "admin-login.html").read_text(encoding="utf-8")
    download = (STATIC / "download.html").read_text(encoding="utf-8")
    for marker in ["#/overview", "hashchange", "checkHealth()"]:
        assert marker in console
    assert "/api/auth/admin" in login and "obs_api_key" in login
    assert "/download/plugin.zip" in download
