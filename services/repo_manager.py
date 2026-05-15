import os
import shutil
import subprocess
import threading
from typing import Dict, Iterable, List, Tuple

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from utils.console import (
    console,
    error,
    hide_stats_widget,
    info,
    show_stats_widget,
    update_stats_widget,
    warn,
)

DEFAULT_REPO_PATH = r"C:\Users\reeva\OneDrive\Desktop"
NO_EXT_KEY = "<no_ext>"
BAR_WIDTH = 24

_scan_lock = threading.Lock()
_scan_in_progress = False


def list_repos(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    path = kwargs.get("path")
    if not path and args:
        path = args[0]
    if not path:
        path = DEFAULT_REPO_PATH

    if not os.path.exists(path):
        error(f"Path not found: {path}")
        return

    try:
        entries = sorted(os.listdir(path), key=str.lower)
    except OSError:
        error(f"Failed to read directory: {path}")
        return

    repos = []
    for entry in entries:
        full_path = os.path.join(path, entry)
        if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, ".git")):
            repos.append(entry)

    if not repos:
        warn(f"No git repositories found in {path}")
        return

    table = Table(title=f"Repositories ({len(repos)} found)")
    table.add_column("Repo", style="cyan")

    for repo in repos:
        table.add_row(repo)

    console.print(table)


def open_repo(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        error("Usage: repo <folder-name> [path]")
        return

    repo_name = args[0]
    base_path = kwargs.get("path")
    if not base_path and len(args) > 1:
        base_path = args[1]
    if not base_path:
        base_path = DEFAULT_REPO_PATH

    repo_path = repo_name
    if not os.path.isabs(repo_name):
        repo_path = os.path.join(base_path, repo_name)

    if not os.path.exists(repo_path):
        error(f"Path not found: {repo_path}")
        return

    if not os.path.isdir(repo_path):
        error(f"Not a directory: {repo_path}")
        return

    if not os.path.exists(os.path.join(repo_path, ".git")):
        warn(f"Not a git repository: {repo_path}")
        return

    code_cmd = shutil.which("code")
    if not code_cmd:
        error(
            "VS Code command 'code' not found. In VS Code: Cmd/Ctrl+Shift+P -> "
            "Shell Command: Install 'code' command in PATH'."
        )
        return

    try:
        subprocess.Popen([code_cmd, repo_path])
    except OSError:
        error(f"Failed to open VS Code for: {repo_path}")


def repo_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        error("Usage: repo <repo_name> [path] | repo <repo_name> stats [path]")
        return

    action = str(args[0]).strip().lower()
    if action in {"stats", "stat"}:
        _handle_repo_stats_visibility(args[1:], kwargs)
        return

    repo_name = args[0]
    if len(args) > 1 and str(args[1]).strip().lower() in {"stats", "stat"}:
        repo_stats(repo_name, args[2:], kwargs)
        return

    open_repo(args, kwargs)


def repo_stats(repo_name: str, args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if _wants_close(args, kwargs):
        hide_stats_widget()
        info("Repo stats widget hidden.")
        return

    base_path = kwargs.get("path")
    if not base_path and args:
        base_path = args[0]
    if not base_path:
        base_path = DEFAULT_REPO_PATH

    repo_path = repo_name
    if not os.path.isabs(repo_name):
        repo_path = os.path.join(base_path, repo_name)

    show_stats_widget()

    if not os.path.exists(repo_path):
        message = f"Path not found: {repo_path}"
        error(message)
        update_stats_widget(_build_error_panel(message))
        return

    if not os.path.isdir(repo_path):
        message = f"Not a directory: {repo_path}"
        error(message)
        update_stats_widget(_build_error_panel(message))
        return

    if not os.path.exists(os.path.join(repo_path, ".git")):
        message = f"Not a git repository: {repo_path}"
        warn(message)
        update_stats_widget(_build_error_panel(message))
        return

    if not _begin_scan():
        warn("Repo stats scan already running. Please wait.")
        return

    update_stats_widget(_build_loading_panel(repo_path))
    info(f"Scanning repo: {repo_path}")

    worker = threading.Thread(
        target=_scan_repo_worker,
        args=(repo_path,),
        daemon=True,
    )
    worker.start()


def _handle_repo_stats_visibility(args, kwargs) -> None:
    if _wants_close(args, kwargs):
        hide_stats_widget()
        info("Repo stats widget hidden.")
        return
    error("Usage: repo <repo_name> stats [path] | repo stats --hide")


def _wants_close(args, kwargs) -> bool:
    if "hide" in kwargs or "close" in kwargs:
        return True
    if args:
        action = str(args[0]).strip().lower()
        if action in {"hide", "close"}:
            return True
    return False


def _scan_repo_worker(repo_path: str) -> None:
    try:
        stats = _scan_repo(repo_path)
        if stats is None:
            update_stats_widget(
                _build_error_panel("Scan failed. See output for details.")
            )
            return
        panel = _build_repo_stats_panel(stats)
        update_stats_widget(panel)
        info("Repo stats ready.")
    finally:
        _end_scan()


def _begin_scan() -> bool:
    global _scan_in_progress
    with _scan_lock:
        if _scan_in_progress:
            return False
        _scan_in_progress = True
        return True


def _end_scan() -> None:
    global _scan_in_progress
    with _scan_lock:
        _scan_in_progress = False


def _scan_repo(repo_path: str):
    try:
        ext_counts: Dict[str, int] = {}
        files: List[str] = []

        for root, dirs, filenames in os.walk(repo_path):
            if ".git" in dirs:
                dirs.remove(".git")

            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, repo_path)
                files.append(rel_path)

                ext = os.path.splitext(filename)[1].lower()
                if not ext:
                    ext = NO_EXT_KEY
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

        files.sort(key=str.lower)
        return {
            "path": repo_path,
            "fileCount": len(files),
            "extCounts": ext_counts,
            "files": files,
        }
    except Exception as exc:
        error(f"Repo scan failed: {exc}")
        return None


def _build_repo_stats_panel(stats: Dict) -> Panel:
    path = str(stats.get("path", ""))
    file_count = _to_int(stats.get("fileCount", 0))
    ext_counts = _coerce_dict(stats.get("extCounts", {}))
    files = [str(item) for item in stats.get("files", [])]

    if file_count == 0:
        return Panel(
            Text("No files found in repo.", style="yellow"),
            title="Repo Stats",
            subtitle=path,
            border_style="yellow",
            box=box.HEAVY,
        )

    rows = _build_extension_rows(ext_counts, file_count)
    summary = Text.assemble(
        ("Files: ", "bold"),
        (f"{file_count:,}", "green"),
        (" | Types: ", "bold"),
        (f"{len(ext_counts):,}", "magenta"),
    )

    ext_table = _build_extension_table(rows)
    files_table = _build_files_table(files)

    body = Group(summary, Text(""), ext_table, Text(""), files_table)
    return Panel(
        body,
        title="Repo Stats",
        subtitle=path,
        border_style="bright_magenta",
        box=box.HEAVY,
    )


def _build_extension_rows(
    ext_counts: Dict[str, int], file_count: int
) -> List[Tuple[str, int, float]]:
    rows = []
    for ext, count in sorted(ext_counts.items(), key=lambda x: (-x[1], x[0])):
        label = _label_for_ext(ext)
        rows.append((label, count, _percent(count, file_count)))
    return rows


def _build_extension_table(rows: Iterable[Tuple[str, int, float]]) -> Table:
    table = Table(title="By File Type", box=box.SIMPLE_HEAVY)
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("%", justify="right", style="magenta")
    table.add_column("Bar", style="white")

    for label, count, percent in rows:
        table.add_row(label, f"{count:,}", f"{percent:5.1f}%", _bar_text(percent))

    return table


def _build_files_table(files: Iterable[str]) -> Table:
    table = Table(title="Files", box=box.SIMPLE)
    table.add_column("#", justify="right", style="bright_black")
    table.add_column("Path", style="cyan")

    for index, path in enumerate(files, start=1):
        table.add_row(str(index), path)

    return table


def _build_loading_panel(path: str) -> Panel:
    return Panel(
        Text("Scanning repo...", style="yellow"),
        title="Repo Stats",
        subtitle=path,
        border_style="yellow",
        box=box.HEAVY,
    )


def _build_error_panel(message: str) -> Panel:
    return Panel(
        Text(message, style="red"),
        title="Repo Stats",
        border_style="red",
        box=box.HEAVY,
    )


def _bar_text(percent: float, width: int = BAR_WIDTH) -> Text:
    pct = max(0.0, min(100.0, percent))
    filled = int(round(pct / 100.0 * width))
    filled = max(0, min(width, filled))

    bar = Text("[")
    if filled:
        bar.append("=" * filled, style="bright_cyan")
    if filled < width:
        bar.append(" " * (width - filled), style="bright_black")
    bar.append("]")
    return bar


def _percent(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (value / total) * 100.0


def _label_for_ext(ext: str) -> str:
    if ext == NO_EXT_KEY:
        return "no extension"
    return ext


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_dict(value) -> Dict[str, int]:
    if isinstance(value, dict):
        return {str(k): _to_int(v) for k, v in value.items()}
    return {}
