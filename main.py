from core.command_registry import CommandRegistry
from core.math_eval import eval_math_expression, looks_like_math
from core.parser import parse_input
from core.plugin_loader import load_plugins
from utils.console import error, info
from core.state_manager import state_manager


def main():
    registry = CommandRegistry()

    # Load built-in commands
    registry.load_builtin_commands()

    # Load plugins
    load_plugins(registry)

    info("WELCOME TO REEVZ TUI! Type 'help' to see available commands.\n")

    while True:
        try:
            user_input = input("> ")
            print()
            if user_input.strip() in ["exit", "quit"]:
                break

            if looks_like_math(user_input):
                try:
                    result = eval_math_expression(user_input)
                    info(result)
                except Exception as e:
                    error(str(e))
                continue

            command, args, kwargs = parse_input(user_input)
            registry.execute(command, args, kwargs)
            state_manager.append_recent_command(user_input)
        except Exception as e:
            error(str(e))


if __name__ == "__main__":
    main()
