from core.command_registry import CommandRegistry
from core.parser import parse_input
from core.plugin_loader import load_plugins
from utils.console import error


def main():
    registry = CommandRegistry()

    # Load built-in commands
    registry.load_builtin_commands()

    # Load plugins
    load_plugins(registry)

    print("🚀 CLI ready. Type 'help' or 'exit'.")

    while True:
        try:
            user_input = input("> ")
            if user_input.strip() in ["exit", "quit"]:
                break

            command, args, kwargs = parse_input(user_input)
            registry.execute(command, args, kwargs)

        except Exception as e:
            error(str(e))


if __name__ == "__main__":
    main()
