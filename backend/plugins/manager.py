from .loader import PluginLoader, PluginInfo

class PluginManager:
    def __init__(self):
        self._plugins: dict[str, PluginInfo] = {}

    def load_all(self):
        for plugin in PluginLoader.discover():
            self._plugins[plugin.name] = plugin

    def list_plugins(self) -> list[dict]:
        return [
            {"name": p.name, "description": p.manifest.get("description", ""), "enabled": p.enabled}
            for p in self._plugins.values()
        ]

    def enable(self, name: str):
        if name in self._plugins:
            PluginLoader.load_module(self._plugins[name])
            self._plugins[name].enabled = True

    def disable(self, name: str):
        if name in self._plugins:
            self._plugins[name].enabled = False
            self._plugins[name].module = None

plugin_manager = PluginManager()
plugin_manager.load_all()
