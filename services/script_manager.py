import json
import subprocess
from utils.console import error, warn, success, console
from rich.table import Table

CONFIG_PATH = "config/scripts.json"


# region run script
def run_script(args, kwargs=None):
    if kwargs is None:
        kwargs = {}
    if not args:
        print("Usage: run <script_name>")
        return

    name = args[0]

    with open(CONFIG_PATH) as f:
        scripts = json.load(f)

    if name not in scripts:
        print(f"Script not found: {name}")
        return

    command = scripts[name]
    subprocess.Popen(command, shell=True)


# region list scripts
def list_scripts(self, args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    try:
        with open("config/scripts.json") as f:
            scripts = json.load(f)
    except FileNotFoundError:
        error("Script configuration not found\n")
        return
    except json.JSONDecodeError:
        error("Invalid script configuration\n")
        return

    if not scripts:
        warn("No scripts available\n")
        return

    table = Table(title="Available Scripts")
    table.add_column("Script Name", style="cyan")
    table.add_column("Command to Run", style="cyan")

    for name, command in scripts.items():
        if isinstance(name, str) and isinstance(command, str):
            table.add_row(name, command)
        else:
            table.add_row(name, "Invalid format")

    console.print(table)
    success(f"Total Scripts: {len(scripts)}\n")
