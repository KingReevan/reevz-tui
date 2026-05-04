from utils.console import info
from core.state_manager import state_manager


def show_state(args, kwargs):
    print(state_manager.state)


def show_recent_commands(args, kwargs):
    recent_commands = state_manager.get("recent_commands")

    if recent_commands is None:
        info("No recent commands found.")
        return

    for idx, command in enumerate(recent_commands):
        print(f"{idx}: {command}")
    print()


def show_recent_workflows(args, kwargs):
    recent_workflows = state_manager.get("recent_workflows")

    if recent_workflows is None:
        info("No recent workflows found.")
        return

    for idx, workflow in enumerate(recent_workflows):
        print(f"{idx}: {workflow}")
    print()
