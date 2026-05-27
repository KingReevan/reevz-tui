import os
import shlex
import shutil
import subprocess
import threading
import textwrap
from typing import List

from rich.panel import Panel
from rich.text import Text
from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, RichLog, Static, TextArea

from core.command_registry import CommandRegistry
from core.math_eval import eval_math_expression, looks_like_math
from core.plugin_loader import load_plugins
from core.parser import parse_input
from core.state_manager import state_manager
from utils.console import (
    set_output_handler,
    set_output_clear_handler,
    set_stats_handler,
    set_stats_visibility_handler,
    set_converter_handler,
    set_converter_visibility_handler,
    set_theme_handler,
    hide_converter_widget,
    update_converter_widget,
    set_text_editor_handler,
    set_text_editor_visibility_handler,
    set_text_editor_focus_handler,
    hide_text_editor_widget,
)
from services.file_converter import (
    convert_word_files,
    convert_pdf_files,
    DEFAULT_OUTPUT_DIR,
)
from services.quote_manager import print_startup_quote
from services.llm_manager import (
    is_chat_active,
    reset_chat_session,
    set_chat_active,
    stream_chat_response,
)


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

    CSS_PATH = "ui/reevz.tcss"

    def __init__(self):
        super().__init__()
        self.sub_title = "Reevz TUI"
        self.registry = CommandRegistry()
        self.registry.load_builtin_commands()
        load_plugins(self.registry)
        set_chat_active(False)
        recent_commands = state_manager.get("recent_commands")
        self._history = (
            list(recent_commands) if isinstance(recent_commands, list) else []
        )
        self._history_index = None
        self._history_draft = ""
        self._chat_lines = []
        self._chat_partial = ""
        self._chat_busy = False
        self._chat_lock = threading.Lock()
        self._chat_spinner_frames = ["|", "/", "-", "\\"]
        self._chat_spinner_index = 0
        self._chat_spinner_timer = None
        self._ui_thread_id = None
        self._norm_mode = bool(state_manager.get("norm_mode", False))
        self._norm_cwd = os.getcwd()
        self._base_sub_title = self.sub_title
        self._norm_marker = "__REEVZ_PWD__:"

    def compose(self) -> ComposeResult:
        yield Header()

        yield Horizontal(
            Vertical(
                RichLog(id="stat_widget", classes="hidden", highlight=True),
                RichLog(id="output", highlight=True),
                TextArea(id="text_editor", classes="hidden"),
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
        text_editor = self.query_one("#text_editor", TextArea)
        command_input = self.query_one("#command_input", Input)
        app_thread_id = threading.get_ident()
        self._ui_thread_id = app_thread_id

        def _dispatch(widget_fn, *args):
            if threading.get_ident() == app_thread_id:
                widget_fn(*args)
            else:
                self.call_from_thread(widget_fn, *args)

        def _write_output(renderable):
            _dispatch(output.write, renderable)

        def _clear_output():
            _dispatch(output.clear)

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

        def _set_text_editor_text(text: str) -> None:
            def _apply_text():
                text_editor.text = text

            _dispatch(_apply_text)

        def _set_text_editor_visible(visible: bool) -> None:
            def _apply_visibility():
                text_editor.set_class(not visible, "hidden")
                output.set_class(visible, "hidden")
                if visible:
                    text_editor.focus()
                else:
                    output.focus()

            _dispatch(_apply_visibility)

        def _focus_text_editor() -> None:
            _dispatch(text_editor.focus)

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
        set_output_clear_handler(_clear_output)
        set_stats_handler(_update_stats)
        set_stats_visibility_handler(_set_stats_visible)
        set_converter_handler(_update_converter)
        set_converter_visibility_handler(_set_converter_visible)
        set_theme_handler(_set_theme)
        set_text_editor_handler(_set_text_editor_text)
        set_text_editor_visibility_handler(_set_text_editor_visible)
        set_text_editor_focus_handler(_focus_text_editor)

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
        self._set_norm_mode(self._norm_mode)
        print_startup_quote()
        command_input.focus()
        self._chat_spinner_timer = self.set_interval(0.2, self._tick_chat_spinner)

    def on_unmount(self) -> None:
        if self._chat_spinner_timer is not None:
            self._chat_spinner_timer.stop()
            self._chat_spinner_timer = None
        set_output_handler(None)
        set_output_clear_handler(None)
        set_stats_handler(None)
        set_stats_visibility_handler(None)
        set_converter_handler(None)
        set_converter_visibility_handler(None)
        set_theme_handler(None)
        set_text_editor_handler(None)
        set_text_editor_visibility_handler(None)
        set_text_editor_focus_handler(None)

    def _record_command(self, command_text: str) -> None:
        state_manager.append_recent_command(command_text)
        recent_commands = state_manager.get("recent_commands")
        self._history = (
            list(recent_commands) if isinstance(recent_commands, list) else []
        )
        self._history_index = None
        self._history_draft = ""

    def _wrap_plain_text(self, text: str, width: int) -> List[str]:
        if width <= 0:
            return [text]
        wrapper = textwrap.TextWrapper(
            width=width,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines: List[str] = []
        paragraphs = text.splitlines() or [""]
        for paragraph in paragraphs:
            if paragraph == "":
                lines.append("")
                continue
            wrapped = wrapper.wrap(paragraph)
            lines.extend(wrapped if wrapped else [""])
        return lines

    def _wrap_prefixed_text(self, prefix: str, content: str, width: int) -> List[str]:
        if width <= 0:
            return [f"{prefix}{content}"]
        prefix_len = len(prefix)
        initial = textwrap.TextWrapper(
            width=width,
            initial_indent=prefix,
            subsequent_indent=" " * prefix_len,
            break_long_words=False,
            break_on_hyphens=False,
        )
        subsequent = textwrap.TextWrapper(
            width=width,
            initial_indent=" " * prefix_len,
            subsequent_indent=" " * prefix_len,
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines: List[str] = []
        first = True
        paragraphs = content.splitlines() or [""]
        for paragraph in paragraphs:
            if paragraph == "":
                if first:
                    lines.append(prefix.rstrip())
                    first = False
                else:
                    lines.append("")
                continue
            wrapper = initial if first else subsequent
            wrapped = wrapper.wrap(paragraph)
            if not wrapped:
                lines.append(prefix.rstrip() if first else "")
            else:
                lines.extend(wrapped)
            first = False
        return lines

    def _write_wrapped_line(self, output: RichLog, line: Text, width: int) -> None:
        plain = line.plain
        style = line.style
        for prefix in ("ChatGPT: ", "You: "):
            if plain.startswith(prefix):
                content = plain[len(prefix) :]
                for wrapped_line in self._wrap_prefixed_text(prefix, content, width):
                    output.write(Text(wrapped_line, style=style))
                return
        for wrapped_line in self._wrap_plain_text(plain, width):
            output.write(Text(wrapped_line, style=style))

    def _render_chat_log(self) -> None:
        if self._norm_mode:
            return
        with self._chat_lock:
            lines = list(self._chat_lines)
            partial = self._chat_partial
            busy = self._chat_busy
            spinner_index = self._chat_spinner_index

        def _apply():
            output = self.query_one("#output", RichLog)
            output.clear()
            width = output.size.width if output.size else 0
            if not width:
                width = 80
            width = max(20, width)
            for line in lines:
                self._write_wrapped_line(output, line, width)
            if partial:
                self._write_wrapped_line(
                    output,
                    Text(f"ChatGPT: {partial}", style="green"),
                    width,
                )
            elif busy:
                frame = ""
                if self._chat_spinner_frames:
                    frame = self._chat_spinner_frames[
                        spinner_index % len(self._chat_spinner_frames)
                    ]
                suffix = f" {frame}" if frame else ""
                self._write_wrapped_line(
                    output,
                    Text(
                        f"ChatGPT: writing response...{suffix}",
                        style="dim",
                    ),
                    width,
                )

        if (
            self._ui_thread_id is not None
            and threading.get_ident() != self._ui_thread_id
        ):
            self.call_from_thread(_apply)
        else:
            _apply()

    def _append_chat_line(self, line: Text) -> None:
        with self._chat_lock:
            self._chat_lines.append(line)
        self._render_chat_log()

    def _tick_chat_spinner(self) -> None:
        if self._norm_mode:
            return
        should_render = False
        with self._chat_lock:
            if self._chat_busy and not self._chat_partial and self._chat_spinner_frames:
                self._chat_spinner_index = (self._chat_spinner_index + 1) % len(
                    self._chat_spinner_frames
                )
                should_render = True
        if should_render:
            self._render_chat_log()

    def _handle_chat_input(self, message: str) -> bool:
        if not is_chat_active():
            return False

        lowered = message.strip().lower()
        if lowered in {"/exit", "/quit"}:
            set_chat_active(False)
            self._chat_busy = False
            with self._chat_lock:
                self._chat_partial = ""
                self._chat_lines.append(Text("Exited chatgpt.", style="yellow"))
            self._render_chat_log()
            return True

        if lowered in {"/reset", "/clear"}:
            reset_chat_session()
            with self._chat_lock:
                self._chat_lines = []
                self._chat_partial = ""
            self._append_chat_line(Text("ChatGPT session reset.", style="yellow"))
            return True

        if self._chat_busy:
            self._append_chat_line(
                Text("ChatGPT is still responding. Please wait.", style="yellow")
            )
            return True

        with self._chat_lock:
            self._chat_lines.append(Text(f"You: {message}", style="bold #93c5fd"))
            self._chat_partial = ""
            self._chat_busy = True
            self._chat_spinner_index = 0
        self._render_chat_log()

        def _on_chunk(chunk: str) -> None:
            with self._chat_lock:
                self._chat_partial += chunk
            self._render_chat_log()

        def _on_done(response: str) -> None:
            with self._chat_lock:
                final_text = response or self._chat_partial
                self._chat_partial = ""
                self._chat_lines.append(Text(f"ChatGPT: {final_text}", style="green"))
                self._chat_lines.append(Text(""))
            self._chat_busy = False
            self._render_chat_log()

        def _on_error(exc: Exception) -> None:
            with self._chat_lock:
                self._chat_partial = ""
                self._chat_lines.append(Text(f"[ERROR] {exc}", style="red"))
                self._chat_lines.append(Text(""))
            self._chat_busy = False
            self._render_chat_log()

        stream_chat_response(message, _on_chunk, _on_done, _on_error)
        return True

    def _set_norm_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        self._norm_mode = enabled
        state_manager.set("norm_mode", enabled)
        command_input = self.query_one("#command_input", Input)
        if enabled:
            self.sub_title = f"{self._base_sub_title} (NORM)"
            command_input.placeholder = "PowerShell command..."
        else:
            self.sub_title = self._base_sub_title
            command_input.placeholder = "Enter command..."

    def _toggle_norm_mode(self, output: RichLog) -> None:
        enabled = not self._norm_mode
        if enabled:
            set_chat_active(False)
            self._chat_busy = False
            self._chat_partial = ""
        self._set_norm_mode(enabled)
        if enabled:
            output.write(
                Text(
                    "Norm mode enabled. PowerShell commands are now active.",
                    style="yellow",
                )
            )
            if self._norm_cwd:
                output.write(Text(f"PowerShell cwd: {self._norm_cwd}", style="dim"))
        else:
            output.write(
                Text(
                    "Norm mode disabled. Back to Reevz commands.",
                    style="yellow",
                )
            )

    def _extract_norm_output(self, stdout: str, marker: str):
        if not stdout:
            return None, ""

        lines = stdout.splitlines()
        cleaned_lines = []
        new_cwd = None

        for line in lines:
            if line.startswith(marker):
                new_cwd = line[len(marker) :].strip()
                continue
            cleaned_lines.append(line)

        return new_cwd, "\n".join(cleaned_lines)

    def _run_powershell_command(self, command_text: str, output: RichLog) -> None:
        output.write(Text(f"> {command_text}", style="bold #93c5fd"))

        lowered = command_text.strip().lower()
        if lowered in {"cls", "clear"}:
            output.clear()
            self._record_command(command_text)
            return

        ps_exe = shutil.which("pwsh") or shutil.which("powershell")
        if not ps_exe:
            output.write(Text("[ERROR] PowerShell not found on PATH.", style="red"))
            self._record_command(command_text)
            return

        cwd = self._norm_cwd or os.getcwd()
        cwd_escaped = cwd.replace("'", "''")
        marker = self._norm_marker
        script = (
            "$ErrorActionPreference='Continue'\n"
            f"Set-Location -LiteralPath '{cwd_escaped}'\n"
            f"{command_text}\n"
            f"Write-Output '{marker}' + (Get-Location).Path\n"
        )

        result = subprocess.run(
            [ps_exe, "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        new_cwd, cleaned_stdout = self._extract_norm_output(stdout, marker)
        if new_cwd:
            self._norm_cwd = new_cwd

        if cleaned_stdout.strip():
            output.write(cleaned_stdout.rstrip())
        if stderr:
            output.write(Text(stderr.rstrip(), style="red"))
        if result.returncode != 0 and not stderr:
            output.write(
                Text(
                    f"[ERROR] PowerShell exited with code {result.returncode}",
                    style="red",
                )
            )

        self._record_command(command_text)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            text_editor = self.query_one("#text_editor", TextArea)
            if not text_editor.has_class("hidden"):
                content = text_editor.text
                hide_text_editor_widget()
                from services.text_manager import save_active_text

                save_active_text(content)
                event.stop()
                return

        if event.key not in {"up", "down"}:
            return

        command_input = self.query_one("#command_input", Input)
        if not command_input.has_focus:
            return

        if not self._history:
            return

        if event.key == "up":
            if self._history_index is None:
                self._history_draft = command_input.value
                self._history_index = len(self._history) - 1
            elif self._history_index > 0:
                self._history_index -= 1

            command_input.value = self._history[self._history_index]
            command_input.cursor_position = len(command_input.value)
            event.stop()
            return

        if self._history_index is None:
            return

        if self._history_index < len(self._history) - 1:
            self._history_index += 1
            command_input.value = self._history[self._history_index]
        else:
            self._history_index = None
            command_input.value = self._history_draft

        command_input.cursor_position = len(command_input.value)
        event.stop()

    async def on_input_submitted(self, event: Input.Submitted):

        command_text = event.value.strip()

        output = self.query_one("#output", RichLog)

        event.input.value = ""

        if not command_text:
            return

        if command_text.strip().lower() == "norm":
            self._toggle_norm_mode(output)
            self._record_command(command_text)
            return

        if self._norm_mode:
            self._run_powershell_command(command_text, output)
            return

        if self._handle_chat_input(command_text):
            return

        if looks_like_math(command_text):
            output.write(Text(f"> {command_text}", style="bold #93c5fd"))
            try:
                result = eval_math_expression(command_text)
            except Exception as e:
                output.write(Text(f"[ERROR] {e}", style="red"))
            else:
                output.write(Text(str(result), style="bold #34d399"))
            self._record_command(command_text)
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
            self._record_command(command_text)
            return

        try:
            command, args, kwargs = parse_input(command_text)

            if not command:
                return

            if command in {"cls", "clear"}:
                output.clear()
                self._record_command(command_text)
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

            self._record_command(command_text)

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
