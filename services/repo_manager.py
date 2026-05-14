import os
from rich.table import Table
from utils.console import console, error, warn


def list_repos(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    path = kwargs.get("path")
    if not path and args:
        path = args[0]
    if not path:
        path = r"C:\Users\reeva\OneDrive\Desktop"

    if not os.path.exists(path):
        error(f"Path not found: {path}")
        return

    try:
        entries = sorted(os.listdir(path), key=str.lower)
    except OSError:
        error(f"Failed to read directory: {path}")
        return

    repos = []
    for entry in entries:
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, ".git")):
            repos.append(entry)

    if not repos:
        warn(f"No git repositories found in {path}")
        return

    table = Table(title=f"Repositories ({len(repos)} found)")
    table.add_column("Repo", style="cyan")

    for repo in repos:
        table.add_row(repo)

    console.print(table)
