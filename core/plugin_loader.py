import os
import importlib


def load_plugins(registry):
    plugin_dir = "plugins"

    if not os.path.exists(plugin_dir):
        return

    for file in os.listdir(plugin_dir):
        if file.endswith(".py") and not file.startswith("_"):
            module_name = f"plugins.{file[:-3]}"
            module = importlib.import_module(module_name)

            if hasattr(module, "register"):
                module.register(registry)
