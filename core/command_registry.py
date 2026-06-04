import os
import subprocess
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
        from services.repo_manager import list_repos, repo_command
        from services.info_manager import statfile
        from services.script_manager import run_script, list_scripts
        from services.password_manager import (
            password_command,
            add_password_command,
            delete_password_command,
            update_password_command,
        )
        from services.workflow_manager import run_workflow, list_workflows
        from services.state_commands import show_state
        from services.state_commands import show_recent_commands, show_recent_workflows
        from services.theme_manager import theme_command
        from services.file_converter import convert_command
        from services.zip_extractor import zip_command
        from services.device_manager import device_command
        from services.network_manager import net_command
        from services.llm_manager import chatgpt_command
        from services.text_manager import text_command
        from services.music_manager import music_command

        self.register("open", open_app, "Open an application")
        self.register("run", run_script, "Run a script")
        self.register(
            "search",
            search_files,
            "Search file contents or names (search <pattern> | search <folder> for <name>)",
        )
        self.register("repos", list_repos, "List git repositories on Desktop")
        self.register("repo", repo_command, "Open a repo in VS Code or show stats")
        self.register("workflow", run_workflow, "Run a workflow")
        self.register(
            "statfile",
            statfile,
            "Scan drive and show file stats (--hide to close)",
        )
        self.register(
            "device",
            device_command,
            "Show device stats (device stats --hide to close)",
        )
        self.register("net", net_command, "Check internet connectivity")
        self.register(
            "histwf", show_recent_workflows, "Show recently executed workflows"
        )
        self.register("close", close_terminal, "Close the terminal")
        self.register("workflows", list_workflows, "List all available workflows")
        self.register("state", show_state, "Show current state")
        self.register("theme", theme_command, "List or set the theme")
        self.register("hist", show_recent_commands, "Show recent commands")
        self.register("scripts", list_scripts, "List all available scripts")
        self.register("apps", list_apps, "List all registered apps")
        self.register(
            "convert",
            convert_command,
            "Convert doc/docx to PDF or PDF to doc/docx",
        )
        self.register(
            "zip",
            zip_command,
            "Extract zip files to the Desktop",
        )
        self.register(
            "password",
            password_command,
            "List passwords or show a password",
        )
        self.register(
            "add",
            add_password_command,
            "Add password entry (add password <key> <value>)",
        )
        self.register(
            "delete",
            delete_password_command,
            "Delete password entry (delete password <key>)",
        )
        self.register(
            "update",
            update_password_command,
            "Update password entry (update password <key> <value>)",
        )
        self.register(
            "chatgpt",
            chatgpt_command,
            "Start a ChatGPT session",
        )
        self.register(
            "music",
            music_command,
            "Play music (music | music <song> | music pause)",
        )
        self.register(
            "text",
            text_command,
            "Manage text files (text | text new <file> | text delete <file> | text <file>)",
        )
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


def close_terminal(args, kwargs=None):
    console.print("Closing terminal...")
    if os.name == "nt":
        try:
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)
        except Exception:
            pass
        try:
            ppid = os.getppid()
            if ppid:
                result = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {ppid}"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                tasklist_out = result.stdout.lower()
                if "powershell.exe" in tasklist_out or "pwsh.exe" in tasklist_out:
                    subprocess.Popen(
                        ["taskkill", "/PID", str(ppid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
        except Exception:
            pass
    raise SystemExit(0)
