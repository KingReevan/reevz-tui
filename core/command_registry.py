from difflib import get_close_matches
import json
from utils.console import error, warn, console, success
from rich.table import Table
from services.workflow_runner import run_workflow


class CommandRegistry:
    def __init__(self):
        self.commands = {}

    def register(self, name, func, help_text=""):
        self.commands[name] = {"func": func, "help": help_text}

    def execute(self, name, args, kwargs=None):
        if kwargs is None:
            kwargs = {}

        if name not in self.commands:
            matches = get_close_matches(name, self.commands.keys())
            if matches:
                warn(f"Unknown command: {name}. Did you mean {matches[0]}?")
            else:
                error(f"Unknown command: {name}")
            return

        self.commands[name]["func"](args, kwargs)

    def load_builtin_commands(self):
        from services.app_launcher import open_app
        from services.file_search import search_files
        from services.script_runner import run_script

        self.register("open", open_app, "Open an application")
        self.register("run", run_script, "Run a script")
        self.register("search", search_files, "Search files")
        self.register("workflow", run_workflow, "Run a workflow")
        self.register("workflows", self.list_workflows, "List all available workflows")
        self.register(name="help", func=self.show_help, help_text="Show commands")
        self.register(
            name="cls",
            func=lambda args, kwargs=None: print("\033c"),
            help_text="Clear the screen",
        )

    def list_workflows(self, args, kwargs=None):
        if kwargs is None:
            kwargs = {}

        try:
            with open("config/workflows.json") as f:
                workflows = json.load(f)
        except FileNotFoundError:
            error("Workflows configuration not found")
            return
        except json.JSONDecodeError:
            error("Invalid workflows configuration")
            return

        if not workflows:
            warn("No workflows available")
            return

        table = Table(title="Available Workflows")
        table.add_column("Workflow Name", style="cyan")
        table.add_column("Steps", style="green")

        for name, workflow in workflows.items():
            if isinstance(workflow, dict) and "steps" in workflow:
                step_count = len(workflow["steps"])
                table.add_row(name, f"{step_count} step(s)")
            else:
                table.add_row(name, "Invalid format")

        console.print(table)
        success(f"Total workflows: {len(workflows)}")

    def show_help(self, args, kwargs=None):
        if kwargs is None:
            kwargs = {}
        table = Table(title="Commands")

        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")

        for name, meta in self.commands.items():
            table.add_row(name, meta["help"])

        console.print(table)
