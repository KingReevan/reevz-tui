import json
import os
import subprocess
import webbrowser

from utils.console import success, error, info, warn, console
from rich.table import Table

WORKFLOW_CONFIG = "config/workflows.json"
APP_CONFIG = "config/apps.json"


# region run workflow
def run_workflow(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        error("Usage: workflow <name>")
        return

    workflow_name = args[0]

    with open(WORKFLOW_CONFIG) as f:
        workflows = json.load(f)

    if workflow_name not in workflows:
        error(f"Workflow not found: {workflow_name}")
        return

    with open(APP_CONFIG) as f:
        apps = json.load(f)

    # Get steps from workflow - workflows.json has a "steps" key inside each workflow
    workflow = workflows[workflow_name]
    if isinstance(workflow, dict) and "steps" in workflow:
        actions = workflow["steps"]
    else:
        error(f"Invalid workflow format for: {workflow_name}")
        return

    info(f"Launching workflow: {workflow_name}")

    for action in actions:
        action_type = action.get("type")
        target = action.get("target")

        if not action_type or not target:
            error(f"Invalid action in workflow: {action}")
            continue

        try:
            if action_type == "app":
                if target not in apps:
                    error(f"Unknown app: {target}")
                    continue

                subprocess.Popen(apps[target], shell=True)

            elif action_type == "folder":
                os.startfile(target)

            elif action_type == "url":
                webbrowser.open(target)

            elif action_type == "command":
                subprocess.Popen(target, shell=True)

            success(f"Opened: {target}")

        except Exception as e:
            error(f"Failed to open {target}: {e}")


# region list workflows
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
    success(f"Total workflows: {len(workflows)}\n")
