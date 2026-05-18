import json
import shutil
import subprocess
import threading
import time
from typing import Dict, Optional, Tuple

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from utils.console import clear_output_widget, console, info, warn

UPDATE_INTERVAL = 1.0
BAR_WIDTH = 28

_stats_lock = threading.Lock()
_stats_active = False
_stats_stop_event = threading.Event()


def device_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        warn("Usage: device stats [--hide]")
        return

    action = str(args[0]).strip().lower()
    if action in {"stats", "stat"}:
        device_stats(args[1:], kwargs)
        return

    warn("Usage: device stats [--hide]")


def device_stats(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if _wants_close(args, kwargs):
        if _end_stats():
            clear_output_widget()
            info("Device stats closed.")
        else:
            warn("Device stats is not running.")
        return

    if not _begin_stats():
        warn("Device stats is already running.")
        return

    clear_output_widget()
    console.print(_build_loading_panel())

    worker = threading.Thread(target=_stats_loop, daemon=True)
    worker.start()


def _wants_close(args, kwargs) -> bool:
    if "hide" in kwargs or "close" in kwargs:
        return True
    if args:
        action = str(args[0]).strip().lower()
        if action in {"hide", "close"}:
            return True
    return False


def _begin_stats() -> bool:
    global _stats_active
    with _stats_lock:
        if _stats_active:
            return False
        _stats_active = True
        _stats_stop_event.clear()
        return True


def _end_stats() -> bool:
    global _stats_active
    with _stats_lock:
        if not _stats_active:
            return False
        _stats_active = False
        _stats_stop_event.set()
        return True


def _stats_loop() -> None:
    while not _stats_stop_event.is_set():
        stats, err = _collect_device_stats()
        if stats is None:
            panel = _build_error_panel(err or "Device stats unavailable.")
        else:
            timestamp = time.strftime("%H:%M:%S")
            panel = _build_device_panel(stats, timestamp)

        clear_output_widget()
        console.print(panel)

        _stats_stop_event.wait(UPDATE_INTERVAL)


def _collect_device_stats() -> Tuple[Optional[Dict], Optional[str]]:
    ps_exe = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_exe:
        return None, "PowerShell not found. Install PowerShell or enable it in PATH."

    script = r"""
$ErrorActionPreference = 'SilentlyContinue'

$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cpuPerf = Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'"
$os = Get-CimInstance Win32_OperatingSystem
$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1

$gpuName = $null
$gpuVram = $null
if ($gpu) {
	$gpuName = $gpu.Name
	$gpuVram = [int64]$gpu.AdapterRAM
}

$gpuUsage = $null
$gpuCounters = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue
if ($gpuCounters) {
	$gpu3d = $gpuCounters | Where-Object { $_.Name -like "*engtype_3D*" }
	if ($gpu3d) {
		$usage = ($gpu3d | Measure-Object -Property UtilizationPercentage -Sum).Sum
		if ($null -ne $usage) {
			if ($usage -gt 100) { $usage = 100 }
			$gpuUsage = [math]::Round([double]$usage, 1)
		}
	}
}

$drives = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
	[ordered]@{
		name = $_.DeviceID
		size = [int64]$_.Size
		free = [int64]$_.FreeSpace
	}
}

$result = [ordered]@{
	cpuName = $cpu.Name
	cpuCores = $cpu.NumberOfCores
	cpuLogical = $cpu.NumberOfLogicalProcessors
	cpuClock = $cpu.MaxClockSpeed
	cpuUsage = $cpuPerf.PercentProcessorTime
	memoryTotal = [int64]$os.TotalVisibleMemorySize * 1024
	memoryFree = [int64]$os.FreePhysicalMemory * 1024
	gpuName = $gpuName
	gpuVram = $gpuVram
	gpuUsage = $gpuUsage
	disks = $drives
}

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
        return None, f"Failed to run PowerShell: {exc}"

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        return None, f"PowerShell error: {err or 'Unknown error'}"

    payload = (result.stdout or "").strip()
    if not payload:
        return None, "PowerShell returned no data."

    try:
        return json.loads(payload), None
    except json.JSONDecodeError:
        return None, "Failed to parse PowerShell output."


def _build_loading_panel() -> Panel:
    return Panel(
        Text("Loading device stats...", style="yellow"),
        title="Device Stats",
        subtitle="device stats --hide to close",
        border_style="yellow",
        box=box.HEAVY,
    )


def _build_error_panel(message: str) -> Panel:
    return Panel(
        Text(message, style="red"),
        title="Device Stats",
        subtitle="device stats --hide to close",
        border_style="red",
        box=box.HEAVY,
    )


def _build_device_panel(stats: Dict, timestamp: str) -> Panel:
    cpu_name = _to_str(stats.get("cpuName"), "Unknown CPU")
    cpu_cores = _to_int(stats.get("cpuCores"))
    cpu_logical = _to_int(stats.get("cpuLogical"))
    cpu_clock = _to_int(stats.get("cpuClock"))
    cpu_usage = _to_float(stats.get("cpuUsage"))

    gpu_name = _to_str(stats.get("gpuName"), "Unknown GPU")
    gpu_vram = _to_int(stats.get("gpuVram"))
    gpu_usage = _to_float(stats.get("gpuUsage"), allow_none=True)

    mem_total = _to_int(stats.get("memoryTotal"))
    mem_free = _to_int(stats.get("memoryFree"))
    mem_used = max(0, mem_total - mem_free)
    mem_pct = _percent(mem_used, mem_total)

    summary = Text.assemble(
        ("CPU: ", "bold"),
        (cpu_name, "bright_cyan"),
        (" | GPU: ", "bold"),
        (gpu_name, "bright_magenta"),
    )

    detail = Text()
    has_detail = False
    if cpu_cores or cpu_logical:
        detail.append(
            f"Cores/Threads: {cpu_cores or '?'}C/{cpu_logical or '?'}T",
            style="green",
        )
        has_detail = True
    if cpu_clock:
        if has_detail:
            detail.append(" | ", style="dim")
        detail.append(f"Max Clock: {cpu_clock} MHz", style="yellow")
        has_detail = True
    if gpu_vram:
        if has_detail:
            detail.append(" | ", style="dim")
        detail.append(f"GPU VRAM: {_format_bytes(gpu_vram)}", style="magenta")
        has_detail = True

    usage_table = Table(title="Usage", box=box.SIMPLE_HEAVY)
    usage_table.add_column("Device", style="cyan")
    usage_table.add_column("Usage", justify="right", style="green")
    usage_table.add_column("Graph")

    usage_table.add_row(
        "CPU",
        f"{cpu_usage:5.1f}%",
        _usage_bar(cpu_usage, _usage_style(cpu_usage)),
    )

    if gpu_usage is None:
        usage_table.add_row("GPU", "N/A", Text("unavailable", style="yellow"))
    else:
        usage_table.add_row(
            "GPU",
            f"{gpu_usage:5.1f}%",
            _usage_bar(gpu_usage, _usage_style(gpu_usage)),
        )

    memory_table = Table(title="Memory", box=box.SIMPLE_HEAVY)
    memory_table.add_column("Type", style="cyan")
    memory_table.add_column("Used", justify="right", style="green")
    memory_table.add_column("Total", justify="right", style="magenta")
    memory_table.add_column("Usage", justify="right", style="green")
    memory_table.add_column("Graph")
    memory_table.add_row(
        "RAM",
        _format_bytes(mem_used),
        _format_bytes(mem_total),
        f"{mem_pct:5.1f}%",
        _usage_bar(mem_pct, _usage_style(mem_pct)),
    )

    disk_table = Table(title="Disks", box=box.SIMPLE_HEAVY)
    disk_table.add_column("Drive", style="cyan")
    disk_table.add_column("Used", justify="right", style="green")
    disk_table.add_column("Total", justify="right", style="magenta")
    disk_table.add_column("Usage", justify="right", style="green")
    disk_table.add_column("Graph")

    disks = stats.get("disks") or []
    if isinstance(disks, list) and disks:
        for disk in disks:
            if not isinstance(disk, dict):
                continue
            name = _to_str(disk.get("name"), "?")
            size = _to_int(disk.get("size"))
            free = _to_int(disk.get("free"))
            used = max(0, size - free)
            pct = _percent(used, size)
            disk_table.add_row(
                name,
                _format_bytes(used),
                _format_bytes(size),
                f"{pct:5.1f}%",
                _usage_bar(pct, _usage_style(pct)),
            )
    else:
        disk_table.add_row("N/A", "-", "-", "-", Text("no disks found", style="yellow"))

    body = Group(
        summary,
        detail,
        Text(""),
        usage_table,
        Text(""),
        memory_table,
        Text(""),
        disk_table,
    )
    return Panel(
        body,
        title="Device Stats",
        subtitle=f"Updated {timestamp} | device stats --hide to close",
        border_style="bright_blue",
        box=box.HEAVY,
    )


def _usage_bar(percent: float, fill_style: str) -> Text:
    pct = max(0.0, min(100.0, percent))
    filled = int(round(pct / 100.0 * BAR_WIDTH))
    filled = max(0, min(BAR_WIDTH, filled))

    bar = Text("[")
    if filled:
        bar.append("=" * filled, style=fill_style)
    if filled < BAR_WIDTH:
        bar.append(" " * (BAR_WIDTH - filled), style="bright_black")
    bar.append("]")
    return bar


def _usage_style(percent: float) -> str:
    if percent >= 85:
        return "red"
    if percent >= 60:
        return "yellow"
    return "green"


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


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_float(value, allow_none: bool = False) -> Optional[float]:
    if value is None and allow_none:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None if allow_none else 0.0


def _to_str(value, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback
