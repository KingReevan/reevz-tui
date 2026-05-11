import threading

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog

from core.command_registry import CommandRegistry
from core.math_eval import eval_math_expression, looks_like_math
from core.plugin_loader import load_plugins
from core.parser import parse_input
from core.state_manager import state_manager
from utils.console import (
    set_output_handler,
    set_stats_handler,
    set_stats_visibility_handler,
    set_theme_handler,
)
from services.quote_manager import print_startup_quote


class ReevzTUI(App):

    THEME_NAMES = ("default", "ember", "glacier")

    CSS = """
    Screen {
        layout: vertical;
        background: #0b1020;
        padding: 1 2;
    }

    Header, Footer {
        background: #111827;
        color: #e5e7eb;
    }

    #output {
        width: 100%;
        height: 1fr;
        padding: 1;
        overflow-y: auto;
    }

    #stat_widget {
        height: 14;
        border: round #f59e0b;
        background: #0f172a;
        color: #e5e7eb;
        padding: 1;
        margin-bottom: 1;
        scrollbar-color: #475569;
        scrollbar-background: #0f172a;
        overflow-y: auto;
    }

    .hidden {
        display: none;
    }

    #command_input {
        height: 3;
        padding: 0 1;
        margin-top: 1;
    }

    Screen.theme-default #output {
        border: round #60a5fa;
        background: #0f172a;
        color: #e5e7eb;
        scrollbar-color: #475569;
        scrollbar-background: #0f172a;
    }

    Screen.theme-default #command_input {
        border: round #34d399;
        background: #0b1324;
        color: #f8fafc;
    }

    Screen.theme-default #command_input:focus {
        border: round #a7f3d0;
    }

    Screen.theme-ember #output {
        border: round #f97316;
        background: #241311;
        color: #ffe8d6;
        scrollbar-color: #fb923c;
        scrollbar-background: #241311;
    }

    Screen.theme-ember #command_input {
        border: round #fb923c;
        background: #1a0f0c;
        color: #fff7ed;
    }

    Screen.theme-ember #command_input:focus {
        border: round #fdba74;
    }

    Screen.theme-glacier #output {
        border: round #38bdf8;
        background: #0b1d2a;
        color: #e0f2fe;
        scrollbar-color: #7dd3fc;
        scrollbar-background: #0b1d2a;
    }

    Screen.theme-glacier #command_input {
        border: round #7dd3fc;
        background: #0a1620;
        color: #f0f9ff;
    }

    Screen.theme-glacier #command_input:focus {
        border: round #bae6fd;
    }
    """

    def __init__(self):
        super().__init__()
        self.sub_title = "Reevz TUI"
        self.registry = CommandRegistry()
        self.registry.load_builtin_commands()
        load_plugins(self.registry)

    def compose(self) -> ComposeResult:
        yield Header()

        yield RichLog(id="stat_widget", classes="hidden", highlight=True)

        yield RichLog(id="output", highlight=True)

        yield Input(placeholder="Enter command...", id="command_input")

        yield Footer()

    def on_mount(self) -> None:
        output = self.query_one("#output", RichLog)
        stats_widget = self.query_one("#stat_widget", RichLog)
        app_thread_id = threading.get_ident()

        def _dispatch(widget_fn, *args):
            if threading.get_ident() == app_thread_id:
                widget_fn(*args)
            else:
                self.call_from_thread(widget_fn, *args)

        def _write_output(renderable):
            _dispatch(output.write, renderable)

        def _update_stats(renderable):
            def _apply_stats():
                stats_widget.clear()
                stats_widget.write(renderable)

            _dispatch(_apply_stats)

        def _set_stats_visible(visible: bool):
            def _apply_visibility():
                stats_widget.set_class(not visible, "hidden")

            _dispatch(_apply_visibility)

        theme_classes = {name: f"theme-{name}" for name in self.THEME_NAMES}

        def _apply_theme(theme_name: str):
            theme_key = str(theme_name or "").strip().lower()
            if theme_key not in theme_classes:
                theme_key = "default"
            for class_name in theme_classes.values():
                self.screen.remove_class(class_name)
            self.screen.add_class(theme_classes[theme_key])

        def _set_theme(theme_name: str):
            _dispatch(_apply_theme, theme_name)

        set_output_handler(_write_output)
        set_stats_handler(_update_stats)
        set_stats_visibility_handler(_set_stats_visible)
        set_theme_handler(_set_theme)

        current_theme = state_manager.get("theme", "default")
        if current_theme not in theme_classes:
            current_theme = "default"
            state_manager.set("theme", current_theme)
        _set_theme(current_theme)
        _update_stats(
            Panel(
                Text("Run 'statfile' to scan the drive.", style="dim"),
                title="File Stats",
                border_style="bright_black",
            )
        )
        print_startup_quote()

    def on_unmount(self) -> None:
        set_output_handler(None)
        set_stats_handler(None)
        set_stats_visibility_handler(None)
        set_theme_handler(None)

    async def on_input_submitted(self, event: Input.Submitted):

        command_text = event.value.strip()

        output = self.query_one("#output", RichLog)

        event.input.value = ""

        if not command_text:
            return

        if looks_like_math(command_text):
            output.write(Text(f"> {command_text}", style="bold #93c5fd"))
            try:
                result = eval_math_expression(command_text)
            except Exception as e:
                output.write(Text(f"[ERROR] {e}", style="red"))
            else:
                output.write(Text(str(result), style="bold #34d399"))
            return

        try:
            command, args, kwargs = parse_input(command_text)

            if not command:
                return

            if command in {"cls", "clear"}:
                output.clear()
                return

            output.write(Text(f"> {command_text}", style="bold #93c5fd"))

            import io
            from contextlib import redirect_stdout

            buffer = io.StringIO()

            with redirect_stdout(buffer):

                self.registry.execute(command, args, kwargs)

            captured = buffer.getvalue()

            if captured.strip():
                output.write(captured)

        except Exception as e:
            output.write(f"[ERROR] {e}")


if __name__ == "__main__":
    app = ReevzTUI()
    app.run()
