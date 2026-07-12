import pytest
from plugins.manager import PluginManager

def test_plugin_manager_init():
    pm = PluginManager()
    pm.load_all()
    assert isinstance(pm.list_plugins(), list)
