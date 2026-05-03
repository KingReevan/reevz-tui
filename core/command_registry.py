from difflib import get_close_matches
from utils.console import error, warn, console
from rich.table import Table


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
        from services.app_manager import open_app, list_apps
        from services.file_search import search_files
        from services.script_manager import run_script, list_scripts
        from services.workflow_manager import run_workflow, list_workflows

        self.register("open", open_app, "Open an application")
        self.register("run", run_script, "Run a script")
        self.register("search", search_files, "Search files")
        self.register("workflow", run_workflow, "Run a workflow")
        self.register("workflows", list_workflows, "List all available workflows")
        self.register("scripts", list_scripts, "List all available scripts")
        self.register("apps", list_apps, "List all registered apps")
        self.register(name="help", func=self.show_help, help_text="Show commands")
        self.register(
            name="cls",
            func=lambda args, kwargs=None: print("\033c"),
            help_text="Clear the screen",
        )

    def show_help(self, args, kwargs=None):
        if kwargs is None:
            kwargs = {}
        table = Table(title="Commands")

        table.add_column("Command", style="cyan")
        table.add_column("Description", style="green")

        for name, meta in self.commands.items():
            table.add_row(name, meta["help"])

        console.print(table)
        console.print()
