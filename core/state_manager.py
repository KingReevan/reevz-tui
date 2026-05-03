import json
import os
from typing import Any

STATE_PATH = "config/state.json"


class StateManager:
    def __init__(self):
        self.state = {}
        self.load()

    def load(self):
        """
        Load persistent state from disk.
        """

        if not os.path.exists(STATE_PATH):
            self.state = self.default_state()
            self.save()
            return

        try:
            with open(STATE_PATH, "r") as f:
                self.state = json.load(f)

        except Exception:
            self.state = self.default_state()
            self.save()

    def save(self):
        """
        Save state to disk.
        """

        with open(STATE_PATH, "w") as f:
            json.dump(self.state, f, indent=2)

    def default_state(self):
        return {
            "current_workspace": None,
            "recent_workflows": [],
            "recent_commands": [],
            "theme": "default",
        }

    def get(self, key: str, default=None):
        return self.state.get(key, default)

    def set(self, key: str, value: Any):
        self.state[key] = value
        self.save()

    def append_recent_command(self, command: str):
        commands = self.state["recent_commands"]

        commands.append(command)

        # keep only last 20
        self.state["recent_commands"] = commands[-20:]

        self.save()


state_manager = StateManager()
