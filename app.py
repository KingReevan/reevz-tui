from rich.text import Text
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog

from core.command_registry import CommandRegistry
from core.plugin_loader import load_plugins
from core.parser import parse_input
from utils.console import set_output_handler


class ReevzTUI(App):

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
        border: round #60a5fa;
        background: #0f172a;
        color: #e5e7eb;
        padding: 1;
        scrollbar-color: #475569;
        scrollbar-background: #0f172a;
        overflow-y: auto;
    }

    #command_input {
        height: 3;
        border: round #34d399;
        background: #0b1324;
        color: #f8fafc;
        padding: 0 1;
        margin-top: 1;
    }

    #command_input:focus {
        border: round #a7f3d0;
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

        yield RichLog(id="output", highlight=True)

        yield Input(placeholder="Enter command...", id="command_input")

        yield Footer()

    def on_mount(self) -> None:
        output = self.query_one("#output", RichLog)
        set_output_handler(output.write)

    def on_unmount(self) -> None:
        set_output_handler(None)

    async def on_input_submitted(self, event: Input.Submitted):

        command_text = event.value.strip()

        output = self.query_one("#output", RichLog)

        event.input.value = ""

        if not command_text:
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
