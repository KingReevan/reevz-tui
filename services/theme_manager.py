import json
import os
from typing import Any, Dict

from rich.table import Table

from core.state_manager import state_manager
from utils.console import console, error, info, success, warn, request_theme_change

THEMES_PATH = "config/themes.json"


def _load_themes() -> Dict[str, Any]:
    if not os.path.exists(THEMES_PATH):
        error("Themes configuration not found.")
        return {}

    try:
        with open(THEMES_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        error("Invalid themes configuration.")
        return {}
    except Exception as exc:
        error(f"Failed to load themes: {exc}")
        return {}

    if not isinstance(payload, dict) or not payload:
        warn("No themes available.")
        return {}

    return payload


def _render_themes(themes: Dict[str, Any]) -> None:
    table = Table(title="Available Themes")
    table.add_column("Theme", style="cyan")
    table.add_column("Label", style="magenta")
    table.add_column("Description", style="green")

    for name, meta in themes.items():
        label = name
        description = ""
        if isinstance(meta, dict):
            label = str(meta.get("label") or name)
            description = str(meta.get("description") or "")
        elif meta is not None:
            description = str(meta)
        table.add_row(name, label, description)

    console.print(table)
    success(f"Total themes: {len(themes)}")


def theme_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    themes = _load_themes()
    if not themes:
        return

    if not args or "list" in kwargs or "l" in kwargs:
        _render_themes(themes)
        current = state_manager.get("theme", "default")
        info(f"Current theme: {current}")
        info("Usage: theme <name>")
        return

    theme_name = str(args[0]).strip().lower()
    if theme_name not in themes:
        error(f"Theme not found: {theme_name}")
        _render_themes(themes)
        return

    state_manager.set("theme", theme_name)

    if request_theme_change(theme_name):
        success(f"Theme set to: {theme_name}")
    else:
        warn(f"Theme set to: {theme_name}. Restart the TUI to apply.")
