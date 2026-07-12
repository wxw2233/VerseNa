import pytest
from themes.manager import ThemeManager

def test_list_themes():
    themes = ThemeManager.list_themes()
    ids = [t["id"] for t in themes]
    assert "default" in ids

def test_get_theme():
    t = ThemeManager.get_theme("default")
    assert t["name"] == "默认暗黑"
    assert "primary" in t["colors"]

def test_get_css():
    css = ThemeManager.get_css("miku")
    assert "#39C5BB" in css
