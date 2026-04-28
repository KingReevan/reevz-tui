import json
import os

CONFIG_PATH = "config/apps.json"


def open_app(args, kwargs=None):
    if kwargs is None:
        kwargs = {}
    if not args:
        print("Usage: open <app_name>")
        return

    app_name = args[0]

    with open(CONFIG_PATH) as f:
        apps = json.load(f)

    if app_name not in apps:
        print(f"App not found: {app_name}")
        return

    path = apps[app_name]
    os.startfile(path)
