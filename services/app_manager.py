import json
import os
from utils.console import console, warn, success, error, info
from rich.table import Table

CONFIG_PATH = "config/apps.json"


# region open app
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


# region list apps
def list_apps(self, args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    try:
        with open("config/apps.json") as f:
            apps = json.load(f)
    except FileNotFoundError:
        error("App configuration not found\n")
        return
    except json.JSONDecodeError:
        error("Invalid App configuration\n")
        return

    if not apps:
        warn("No apps available\n")
        return

    table = Table(title="Available Apps")
    table.add_column("App Name", style="cyan")

    for name, _ in apps.items():
        if isinstance(name, str):
            table.add_row(name)

    console.print(table)
    success(f"Total Apps: {len(apps)}")
    info("Command Usage: 'open <app_name>'\n")
