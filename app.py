import os
import shlex
import shutil
import subprocess
import threading
from typing import List

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static

from core.command_registry import CommandRegistry
from core.math_eval import eval_math_expression, looks_like_math
from core.plugin_loader import load_plugins
from core.parser import parse_input
from core.state_manager import state_manager
from utils.console import (
    set_output_handler,
    set_stats_handler,
    set_stats_visibility_handler,
    set_converter_handler,
    set_converter_visibility_handler,
    set_theme_handler,
    hide_converter_widget,
    update_converter_widget,
)
from services.file_converter import (
    convert_word_files,
    convert_pdf_files,
    DEFAULT_OUTPUT_DIR,
)
from services.quote_manager import print_startup_quote


class FileConverterPanel(Vertical):
    can_focus = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Static("File Converter", id="converter_title")
        yield Static(
            "Run 'convert doc to pdf' or 'convert pdf to doc/docx', then drop "
            f"files here. Output: {DEFAULT_OUTPUT_DIR}",
            id="converter_help",
        )
        yield Button("Close", id="converter_close")
        yield RichLog(id="converter_log", highlight=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "converter_close":
            hide_converter_widget()

    def on_file_drop(self, event) -> None:
        self._handle_drop_event(event)

    def on_drop(self, event) -> None:
        self._handle_drop_event(event)

    def _handle_drop_event(self, event) -> None:
        paths = self._extract_paths(event)
        if not paths:
            text = getattr(event, "text", None) or getattr(event, "value", None)
            paths = self._extract_paths_from_text(text)
        if not paths:
            self._log("No files detected in drop.", "yellow")
            return
        self.handle_file_drop(paths)
        if hasattr(event, "stop"):
            event.stop()

    def handle_file_drop(self, paths: List[str]) -> None:
        if self._busy:
            self._log("Conversion already running. Please wait.", "yellow")
            return

        mode = self._get_converter_mode()
        allowed_exts = {".doc", ".docx"} if mode == "doc_to_pdf" else {".pdf"}
        valid, invalid = self._filter_paths(paths, allowed_exts)
        if invalid:
            self._log(f"Skipped {len(invalid)} unsupported file(s).", "yellow")
        if not valid:
            if mode == "doc_to_pdf":
                self._log("No .doc/.docx files to convert.", "yellow")
            else:
                self._log("No .pdf files to convert.", "yellow")
            return

        self._busy = True
        if mode == "doc_to_pdf":
            self._log(
                f"Converting {len(valid)} Word file(s) to PDF...",
                "cyan",
            )
        else:
            target_label = "DOCX" if mode == "pdf_to_docx" else "DOC"
            self._log(
                f"Converting {len(valid)} PDF file(s) to {target_label}...",
                "cyan",
            )

        worker = threading.Thread(
            target=self._convert_worker,
            args=(mode, valid),
            daemon=True,
        )
        worker.start()

    def _convert_worker(self, mode: str, paths: List[str]) -> None:
        try:
            if mode == "doc_to_pdf":
                results = convert_word_files(paths, DEFAULT_OUTPUT_DIR)
            else:
                target = "docx" if mode == "pdf_to_docx" else "doc"
                results = convert_pdf_files(paths, DEFAULT_OUTPUT_DIR, target)
        except Exception as exc:
            self._log(f"Conversion failed: {exc}", "red")
            self.app.call_from_thread(self._set_busy, False)
            return

        success_count = 0
        for src, dest, ok, err in results:
            if ok:
                success_count += 1
                self._log(f"Saved: {dest}", "green")
            else:
                label = dest or src
                self._log(f"Failed: {label} ({err})", "red")

        self._log(
            f"Done. {success_count}/{len(results)} file(s) converted.",
            "green",
        )
        self.app.call_from_thread(self._set_busy, False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

    def _filter_paths(self, paths: List[str], allowed_exts):
        valid = []
        invalid = []
        for path in paths:
            if os.path.isdir(path):
                invalid.append(path)
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext in allowed_exts:
                valid.append(path)
            else:
                invalid.append(path)
        return valid, invalid

    def _get_converter_mode(self) -> str:
        mode = state_manager.get("converter_mode", "doc_to_pdf")
        if mode not in {"doc_to_pdf", "pdf_to_doc", "pdf_to_docx"}:
            mode = "doc_to_pdf"
        return mode

    def _extract_paths(self, event) -> List[str]:
        if hasattr(event, "paths") and event.paths:
            return [str(path) for path in event.paths]
        if hasattr(event, "files") and event.files:
            return [str(path) for path in event.files]
        if hasattr(event, "path") and event.path:
            return [str(event.path)]
        if hasattr(event, "value") and event.value:
            return self._coerce_paths(event.value)
        return []

    def _extract_paths_from_text(self, text) -> List[str]:
        if not text:
            return []

        raw_text = str(text).strip()
        if not raw_text:
            return []

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        candidates: List[str] = []
        if len(lines) > 1:
            for line in lines:
                candidates.extend(self._split_text_paths(line))
        else:
            candidates = self._split_text_paths(raw_text)

        cleaned: List[str] = []
        for item in candidates:
            cleaned_item = item.strip().strip('"').strip("'")
            if cleaned_item.startswith("{") and cleaned_item.endswith("}"):
                cleaned_item = cleaned_item[1:-1].strip()
            if cleaned_item:
                cleaned.append(cleaned_item)

        return [path for path in cleaned if os.path.exists(path)]

    def _split_text_paths(self, text: str) -> List[str]:
        try:
            parts = shlex.split(text, posix=False)
        except ValueError:
            parts = text.split()
        return parts or [text]

    def _coerce_paths(self, value) -> List[str]:
        if isinstance(value, (list, tuple, set)):
            return [str(path) for path in value]
        return [str(value)]

    def _log(self, message: str, style: str = "") -> None:
        if style:
            update_converter_widget(Text(message, style=style))
        else:
            update_converter_widget(Text(message))


class ReevzTUI(App):

    THEME_NAMES = ("default", "ember", "glacier", "orchid", "matrix")

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

    #main_content {
        layout: horizontal;
        height: 1fr;
    }

    #main_stack {
        width: 1fr;
        height: 1fr;
    }

    #converter_panel {
        width: 40;
        margin-left: 1;
        border: round #38bdf8;
        background: #0b1a2a;
        color: #e2e8f0;
        padding: 1;
    }

    #converter_title {
        text-style: bold;
        color: #e2e8f0;
    }

    #converter_help {
        color: #94a3b8;
        margin-bottom: 1;
    }

    #converter_close {
        margin-bottom: 1;
    }

    #converter_log {
        height: 1fr;
        overflow-y: auto;
        scrollbar-color: #475569;
        scrollbar-background: #0b1a2a;
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

    Screen.theme-orchid #output {
        border: round #e879f9;
        background: #1a0f1f;
        color: #fdf2f8;
        scrollbar-color: #c084fc;
        scrollbar-background: #1a0f1f;
    }

    Screen.theme-orchid #command_input {
        border: round #c084fc;
        background: #140a1d;
        color: #fce7f3;
    }

    Screen.theme-orchid #command_input:focus {
        border: round #f9a8d4;
    }

    Screen.theme-matrix #output {
        border: round #22c55e;
        background: #050b06;
        color: #dcfce7;
        scrollbar-color: #16a34a;
        scrollbar-background: #050b06;
    }

    Screen.theme-matrix #command_input {
        border: round #22c55e;
        background: #030703;
        color: #bbf7d0;
    }

    Screen.theme-matrix #command_input:focus {
        border: round #86efac;
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

        yield Horizontal(
            Vertical(
                RichLog(id="stat_widget", classes="hidden", highlight=True),
                RichLog(id="output", highlight=True),
                id="main_stack",
            ),
            FileConverterPanel(id="converter_panel", classes="hidden"),
            id="main_content",
        )

        yield Input(placeholder="Enter command...", id="command_input")

        yield Footer()

    def on_mount(self) -> None:
        output = self.query_one("#output", RichLog)
        stats_widget = self.query_one("#stat_widget", RichLog)
        converter_panel = self.query_one("#converter_panel", FileConverterPanel)
        converter_log = converter_panel.query_one("#converter_log", RichLog)
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

        def _update_converter(renderable):
            _dispatch(converter_log.write, renderable)

        def _set_converter_visible(visible: bool):
            def _apply_visibility():
                converter_panel.set_class(not visible, "hidden")
                if visible:
                    converter_log.clear()
                    converter_panel.focus()

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
        set_converter_handler(_update_converter)
        set_converter_visibility_handler(_set_converter_visible)
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
        set_converter_handler(None)
        set_converter_visibility_handler(None)
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

        parts = command_text.split()
        if parts and parts[0].lower() == "git":
            output.write(Text(f"> {command_text}", style="bold #93c5fd"))

            ps_exe = shutil.which("pwsh") or shutil.which("powershell")
            if ps_exe:
                result = subprocess.run(
                    [ps_exe, "-NoProfile", "-Command", command_text],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
            else:
                result = subprocess.run(
                    command_text,
                    shell=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )

            if result.stdout:
                output.write(result.stdout.rstrip())
            if result.stderr:
                output.write(Text(result.stderr.rstrip(), style="red"))
            if result.returncode != 0 and not result.stderr:
                output.write(
                    Text(
                        f"[ERROR] Git exited with code {result.returncode}",
                        style="red",
                    )
                )
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

    def on_file_drop(self, event) -> None:
        converter_panel = self.query_one("#converter_panel", FileConverterPanel)
        if converter_panel.has_class("hidden"):
            return

        paths = converter_panel._extract_paths(event)
        if not paths:
            text = getattr(event, "text", None) or getattr(event, "value", None)
            paths = converter_panel._extract_paths_from_text(text)
        if not paths:
            return

        converter_panel.handle_file_drop(paths)
        if hasattr(event, "stop"):
            event.stop()

    def on_paste(self, event) -> None:
        converter_panel = self.query_one("#converter_panel", FileConverterPanel)
        if converter_panel.has_class("hidden"):
            return

        text = getattr(event, "text", None) or getattr(event, "value", None)
        if not text:
            return

        paths = converter_panel._extract_paths_from_text(text)
        if not paths:
            return

        mode = state_manager.get("converter_mode", "doc_to_pdf")
        allowed_exts = {".doc", ".docx"} if mode == "doc_to_pdf" else {".pdf"}
        if not any(os.path.splitext(path)[1].lower() in allowed_exts for path in paths):
            return

        converter_panel.handle_file_drop(paths)
        if hasattr(event, "stop"):
            event.stop()


if __name__ == "__main__":
    app = ReevzTUI()
    app.run()
