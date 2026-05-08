import json
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
    error,
    hide_stats_widget,
    info,
    show_stats_widget,
    update_stats_widget,
    warn,
)

DEFAULT_PATH = "C:\\"
DEFAULT_TOP = 8
BAR_WIDTH = 24
NO_EXT_KEY = "<no_ext>"

_scan_lock = threading.Lock()
_scan_in_progress = False


def statfile(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if "hide" in kwargs or "close" in kwargs:
        hide_stats_widget()
        info("File stats widget hidden.")
        return

    path = kwargs.get("path") or (args[0] if args else DEFAULT_PATH)
    top_value = kwargs.get("top", kwargs.get("t", DEFAULT_TOP))

    try:
        top_n = int(top_value)
        if top_n < 1:
            raise ValueError("top must be >= 1")
    except (TypeError, ValueError):
        show_stats_widget()
        error("Invalid --top value. Use a positive integer.")
        update_stats_widget(_build_error_panel("Invalid --top value."))
        return

    show_stats_widget()

    if not os.path.exists(path):
        error(f"Path not found: {path}")
        update_stats_widget(_build_error_panel(f"Path not found: {path}"))
        return

    if not _begin_scan():
        warn("A scan is already running. Please wait for it to finish.")
        return

    update_stats_widget(_build_loading_panel(path))
    info(f"Scanning: {path}")

    worker = threading.Thread(
        target=_scan_worker,
        args=(path, top_n),
        daemon=True,
    )
    worker.start()


def _scan_worker(path: str, top_n: int) -> None:
    try:
        stats = _run_powershell_scan(path)
        if stats is None:
            update_stats_widget(
                _build_error_panel("Scan failed. See output for details.")
            )
            return

        panel = _build_stats_panel(stats, top_n)
        update_stats_widget(panel)
        info("Scan complete.")
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


def _run_powershell_scan(path: str):
    ps_exe = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_exe:
        error("PowerShell not found. Install PowerShell or enable it in PATH.")
        return None

    escaped_path = path.replace("'", "''")

    script = f"""
$ErrorActionPreference = 'SilentlyContinue'
$path = '{escaped_path}'
$extCounts = @{{}}
$extSizes = @{{}}
$folderCount = 0
$fileCount = 0
$totalSize = 0

Get-ChildItem -LiteralPath $path -Force -Recurse -ErrorAction SilentlyContinue | ForEach-Object {{
	if ($_.PSIsContainer) {{
		$folderCount++
	}} else {{
		$fileCount++
		$size = $_.Length
		$totalSize += $size
		$ext = $_.Extension
		if ([string]::IsNullOrEmpty($ext)) {{
			$ext = '{NO_EXT_KEY}'
		}}
		$ext = $ext.ToLowerInvariant()
		if (-not $extCounts.ContainsKey($ext)) {{
			$extCounts[$ext] = 0
			$extSizes[$ext] = 0
		}}
		$extCounts[$ext] += 1
		$extSizes[$ext] += $size
	}}
}}

$result = [ordered]@{{
	path = $path
	folderCount = $folderCount
	fileCount = $fileCount
	totalSize = $totalSize
	extCounts = $extCounts
	extSizes = $extSizes
}}

$result | ConvertTo-Json -Depth 4 -Compress
"""

    try:
        result = subprocess.run(
            [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as exc:
        error(f"Failed to run PowerShell: {exc}")
        return None

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        error(f"PowerShell scan failed: {err or 'Unknown error'}")
        return None

    payload = (result.stdout or "").strip()
    if not payload:
        error("PowerShell returned no data.")
        return None

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        error("Failed to parse PowerShell output.")
        return None


def _build_stats_panel(stats: Dict, top_n: int) -> Panel:
    ext_counts = _coerce_dict(stats.get("extCounts", {}))
    ext_sizes = _coerce_dict(stats.get("extSizes", {}))
    folder_count = _to_int(stats.get("folderCount", 0))
    file_count = _to_int(stats.get("fileCount", 0))
    total_size = _to_int(stats.get("totalSize", 0))
    path = str(stats.get("path", ""))

    total_items = folder_count + file_count
    if total_items == 0:
        return Panel(
            Text("No files or folders found.", style="yellow"),
            title="File Stats",
            subtitle=path,
            border_style="yellow",
            box=box.HEAVY,
        )

    items = _collect_extension_items(ext_counts, ext_sizes)
    count_rows = _build_count_rows(items, folder_count, total_items, top_n)
    size_rows = _build_size_rows(items, total_size, top_n)

    summary = Text.assemble(
        ("Files: ", "bold"),
        (f"{file_count:,}", "green"),
        (" | Folders: ", "bold"),
        (f"{folder_count:,}", "yellow"),
        (" | Total Size: ", "bold"),
        (_format_bytes(total_size), "magenta"),
    )

    count_table = _build_count_table(count_rows)
    size_table = _build_size_table(size_rows)

    body = Group(summary, Text(""), count_table, Text(""), size_table)
    return Panel(
        body,
        title="File Stats",
        subtitle=path,
        border_style="bright_blue",
        box=box.HEAVY,
    )


def _build_loading_panel(path: str) -> Panel:
    return Panel(
        Text("Scanning... this can take a while.", style="yellow"),
        title="File Stats",
        subtitle=path,
        border_style="yellow",
        box=box.HEAVY,
    )


def _build_error_panel(message: str) -> Panel:
    return Panel(
        Text(message, style="red"),
        title="File Stats",
        border_style="red",
        box=box.HEAVY,
    )


def _collect_extension_items(
    ext_counts: Dict[str, int], ext_sizes: Dict[str, int]
) -> List[Tuple[str, int, int]]:
    items = []
    for ext, count in ext_counts.items():
        size = _to_int(ext_sizes.get(ext, 0))
        items.append((str(ext), _to_int(count), size))
    return items


def _build_count_rows(
    items: Iterable[Tuple[str, int, int]],
    folder_count: int,
    total_items: int,
    top_n: int,
) -> List[Tuple[str, int, float]]:
    items = list(items)
    no_ext_count = _value_for_ext(items, NO_EXT_KEY, index=1)

    ext_items = [entry for entry in items if entry[0] != NO_EXT_KEY]
    sorted_items = sorted(ext_items, key=lambda x: x[1], reverse=True)
    top_items = sorted_items[:top_n]
    top_exts = {ext for ext, _, _ in top_items}
    other_count = sum(count for ext, count, _ in ext_items if ext not in top_exts)

    rows = [("folders", folder_count, _percent(folder_count, total_items))]

    for ext, count, _ in top_items:
        rows.append((_label_for_ext(ext), count, _percent(count, total_items)))

    if no_ext_count > 0:
        rows.append(("no extension", no_ext_count, _percent(no_ext_count, total_items)))

    if other_count > 0:
        rows.append(("other", other_count, _percent(other_count, total_items)))

    return rows


def _build_size_rows(
    items: Iterable[Tuple[str, int, int]], total_size: int, top_n: int
) -> List[Tuple[str, int, float]]:
    items = list(items)
    no_ext_size = _value_for_ext(items, NO_EXT_KEY, index=2)

    ext_items = [entry for entry in items if entry[0] != NO_EXT_KEY]
    sorted_items = sorted(ext_items, key=lambda x: x[2], reverse=True)
    top_items = sorted_items[:top_n]
    top_exts = {ext for ext, _, _ in top_items}
    other_size = sum(size for ext, _, size in ext_items if ext not in top_exts)

    rows = []

    for ext, _, size in top_items:
        rows.append((_label_for_ext(ext), size, _percent(size, total_size)))

    if no_ext_size > 0:
        rows.append(("no extension", no_ext_size, _percent(no_ext_size, total_size)))

    if other_size > 0:
        rows.append(("other", other_size, _percent(other_size, total_size)))

    return rows


def _build_count_table(rows: Iterable[Tuple[str, int, float]]) -> Table:
    table = Table(title="By Count (files + folders)", box=box.SIMPLE_HEAVY)
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right", style="green")
    table.add_column("%", justify="right", style="magenta")
    table.add_column("Bar", style="white")

    for label, count, percent in rows:
        table.add_row(
            label,
            f"{count:,}",
            f"{percent:5.1f}%",
            _bar_text(percent),
        )

    return table


def _build_size_table(rows: Iterable[Tuple[str, int, float]]) -> Table:
    table = Table(title="By Size (files only)", box=box.SIMPLE_HEAVY)
    table.add_column("Type", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("%", justify="right", style="magenta")
    table.add_column("Bar", style="white")

    for label, size, percent in rows:
        table.add_row(
            label,
            _format_bytes(size),
            f"{percent:5.1f}%",
            _bar_text(percent),
        )

    return table


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


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB", "PB"]:
        if size < 1024 or unit == "PB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def _percent(value: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (value / total) * 100.0


def _value_for_ext(items: Iterable[Tuple[str, int, int]], ext: str, index: int) -> int:
    for item in items:
        if item[0] == ext:
            return _to_int(item[index])
    return 0


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
    if not isinstance(value, dict):
        return {}
    coerced = {}
    for key, val in value.items():
        coerced[str(key)] = _to_int(val)
    return coerced
