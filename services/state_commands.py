from rich import print
from core.state_manager import state_manager


def show_state(args, kwargs):
    print(state_manager.state)
