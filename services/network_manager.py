import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from rich.table import Table
from rich.text import Text

from utils.console import console, error, info, success, warn

DEFAULT_TIMEOUT = 2.5
DNS_TEST_HOST = "example.com"
TCP_TARGETS = [
    ("1.1.1.1", 443, "Cloudflare HTTPS"),
    ("8.8.8.8", 53, "Google DNS"),
    ("9.9.9.9", 53, "Quad9 DNS"),
]
HTTP_URLS = [
    "https://www.google.com/generate_204",
    "https://www.cloudflare.com/cdn-cgi/trace",
    "http://www.msftconnecttest.com/connecttest.txt",
]
USER_AGENT = "reevz-tui/1.0 (network-check)"


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    scope: str
    elapsed_ms: Optional[int] = None


def net_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    timeout = _coerce_timeout(kwargs.get("timeout") or kwargs.get("t"))
    if timeout is None:
        timeout = DEFAULT_TIMEOUT

    results = [
        _run_check("Route", "local", _check_route, timeout),
        _run_check("DNS", "internet", _check_dns, timeout),
        _run_check("TCP", "internet", _check_tcp, timeout),
        _run_check("HTTP", "internet", _check_http, timeout),
    ]

    internet_checks = [item for item in results if item.scope == "internet"]
    passed_count = sum(1 for item in internet_checks if item.passed)
    connected = passed_count > 0

    if connected:
        success(
            f"Internet: Connected ({passed_count}/{len(internet_checks)} checks passed)"
        )
    else:
        error("Internet: Not connected (no external checks passed)")

    if kwargs.get("brief") or kwargs.get("b"):
        return

    table = Table(title="Network Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Result", style="green")
    table.add_column("Detail")
    table.add_column("Time", justify="right")

    for item in results:
        status = (
            Text("PASS", style="green") if item.passed else Text("FAIL", style="red")
        )
        elapsed = f"{item.elapsed_ms} ms" if item.elapsed_ms is not None else "-"
        table.add_row(item.name, status, item.detail, elapsed)

    console.print(table)
    info("Tip: use --brief for summary only, or --timeout <seconds> to adjust.")


def _coerce_timeout(value) -> Optional[float]:
    if value is None:
        return None
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        warn("Invalid --timeout value. Using default.")
        return None
    if timeout <= 0:
        warn("--timeout must be > 0. Using default.")
        return None
    return timeout


def _run_check(
    name: str,
    scope: str,
    check: Callable[[float], Tuple[bool, str]],
    timeout: float,
) -> CheckResult:
    start = time.monotonic()
    try:
        passed, detail = check(timeout)
    except Exception as exc:
        passed = False
        detail = f"Error: {exc}"
    elapsed_ms = int((time.monotonic() - start) * 1000)
    return CheckResult(
        name=name,
        passed=passed,
        detail=detail,
        scope=scope,
        elapsed_ms=elapsed_ms,
    )


def _check_route(timeout: float) -> Tuple[bool, str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.connect(("8.8.8.8", 53))
            local_ip = sock.getsockname()[0]
    except OSError as exc:
        return False, f"No route available ({exc})"

    if local_ip.startswith("127.") or local_ip.startswith("169.254."):
        return False, f"Local IP {local_ip} (not routed)"

    return True, f"Local IP {local_ip}"


def _check_dns(timeout: float) -> Tuple[bool, str]:
    try:
        addr_info = socket.getaddrinfo(DNS_TEST_HOST, 80, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return False, f"DNS lookup failed ({exc})"

    ips = []
    for entry in addr_info:
        if entry and len(entry) > 4 and entry[4]:
            ip = entry[4][0]
            if ip not in ips:
                ips.append(ip)
        if len(ips) >= 2:
            break

    if not ips:
        return False, "DNS resolved no addresses"

    return True, f"Resolved {DNS_TEST_HOST} -> {', '.join(ips)}"


def _check_tcp(timeout: float) -> Tuple[bool, str]:
    last_error = None
    for host, port, label in TCP_TARGETS:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True, f"Connected to {label} ({host}:{port})"
        except OSError as exc:
            last_error = exc

    detail = (
        f"TCP connect failed ({last_error})" if last_error else "TCP connect failed"
    )
    return False, detail


def _check_http(timeout: float) -> Tuple[bool, str]:
    last_error = None
    headers = {"User-Agent": USER_AGENT}
    for url in HTTP_URLS:
        request = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = response.getcode() or 0
                if 200 <= status < 400:
                    return True, f"{url} -> HTTP {status}"
                last_error = f"{url} -> HTTP {status}"
                continue
        except urllib.error.HTTPError as exc:
            return True, f"{url} -> HTTP {exc.code}"
        except urllib.error.URLError as exc:
            last_error = exc

    detail = (
        f"HTTP request failed ({last_error})" if last_error else "HTTP request failed"
    )
    return False, detail
