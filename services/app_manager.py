import json
import os
import subprocess
from utils.console import console, warn, success, error, info
from rich.table import Table

CONFIG_PATH = "config/apps.json"

BRAVE_TABS = {
    "youtube": "https://www.youtube.com",
    "chatgpt": "https://chatgpt.com",
    "gemini": "https://gemini.google.com",
    "gmail": "https://mail.google.com",
}


def _resolve_brave_tabs(tokens):
    urls = []
    unknown = []
    for token in tokens:
        key = str(token).strip()
        if not key:
            continue
        lower_key = key.lower()
        if lower_key in BRAVE_TABS:
            urls.append(BRAVE_TABS[lower_key])
            continue
        if lower_key.startswith("http://") or lower_key.startswith("https://"):
            urls.append(key)
            continue
        if "." in lower_key:
            urls.append(f"https://{lower_key}")
            continue
        unknown.append(key)
    return urls, unknown


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

    if app_name.lower() == "brave" and len(args) > 1 and args[1].lower() == "with":
        urls, unknown = _resolve_brave_tabs(args[2:])
        if unknown:
            warn(f"Unknown Brave tabs: {', '.join(unknown)}")
        if not urls:
            warn("No valid Brave tabs provided. Opening Brave normally.")
            os.startfile(path)
            return

        try:
            subprocess.Popen([path, "--new-window", *urls])
            success(f"Opened Brave with {len(urls)} tab(s).")
        except Exception as exc:
            error(f"Failed to open Brave: {exc}")
        return

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
