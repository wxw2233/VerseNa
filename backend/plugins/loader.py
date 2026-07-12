import json, importlib.util
from pathlib import Path

PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"

class PluginInfo:
    def __init__(self, name, manifest, module=None):
        self.name = name
        self.manifest = manifest
        self.module = module
        self.enabled = False

class PluginLoader:
    @staticmethod
    def discover() -> list:
        plugins = []
        if not PLUGINS_DIR.exists():
            return plugins
        for d in PLUGINS_DIR.iterdir():
            manifest_path = d / "manifest.json"
            if d.is_dir() and manifest_path.exists():
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                plugins.append(PluginInfo(name=d.name, manifest=manifest))
        return plugins

    @staticmethod
    def load_module(plugin_info):
        plugin_dir = PLUGINS_DIR / plugin_info.name
        main_path = plugin_dir / "main.py"
        if main_path.exists():
            spec = importlib.util.spec_from_file_location(f"plugins.{plugin_info.name}", main_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            plugin_info.module = module
