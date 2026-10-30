from pathlib import Path
import pytest

STATIC = Path(__file__).resolve().parents[1] / "api" / "app" / "static"


@pytest.mark.parametrize("name", ["me.html", "overview.html", "lab.html", "about.html"])
def test_user_pages_share_balance_theme(name):
    assert "/static/css/balance-theme.css" in (STATIC / name).read_text(encoding="utf-8")


def test_user_shell_behavior_markers_remain():
    me = (STATIC / "me.html").read_text(encoding="utf-8")
    lab = (STATIC / "lab.html").read_text(encoding="utf-8")
    for marker in ["obs_user_id", "TAB_SRC", "?tab=", "?embed=1"]:
        assert marker in me
    for marker in ["lab_saved_datasets", "/api/pool/my-products", "/api/pool/observations"]:
        assert marker in lab
