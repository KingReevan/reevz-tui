import subprocess
import os
from rich.table import Table
from utils.console import console, error, warn


# region search_files
def search_files(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        error(
            "Usage: search <pattern> [--path <dir>] [--type <ext>] [--max <num>] [--ignore-case]"
        )
        return

    pattern = args[0]
    path = kwargs.get("path", ".")
    file_type = kwargs.get("type", None)
    max_results = kwargs.get("max", kwargs.get("m", None))
    ignore_case = "ignore-case" in kwargs or "i" in kwargs

    # Validate path exists
    if not os.path.exists(path):
        error(f"Path not found: {path}")
        return

    try:
        # Build ripgrep command
        cmd = ["rg", "--color=never"]

        if ignore_case:
            cmd.append("--ignore-case")

        # Add file type filter if specified
        if file_type:
            cmd.extend(["--type", file_type])

        # Add pattern and path
        cmd.append(pattern)
        cmd.append(path)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        lines = result.stdout.splitlines()

        # Parse results
        results = []
        for line in lines:
            if ":" in line:
                parts = line.split(":", 3)
                if len(parts) >= 3:
                    results.append(
                        {
                            "file": parts[0],
                            "line": parts[1],
                            "col": parts[2],
                            "match": parts[3].strip() if len(parts) > 3 else "",
                        }
                    )

        if not results:
            warn(f"No matches found for '{pattern}'")
            return

        # Limit results if specified
        if max_results:
            try:
                max_results = int(max_results)
                if len(results) > max_results:
                    warn(f"Found {len(results)} results, showing first {max_results}")
                    results = results[:max_results]
            except ValueError:
                error(f"Invalid --max value: {max_results}")
                return

        # Display results in table
        table = Table(title=f"Search Results ({len(results)} found)")
        table.add_column("File", style="cyan")
        table.add_column("Line:Col", style="yellow")
        table.add_column("Match", style="magenta")

        for result in results:
            line_col = f"{result['line']}:{result['col']}"
            table.add_row(result["file"], line_col, result["match"][:80])

        console.print(table)

    except subprocess.TimeoutExpired:
        error("Search timed out (10 seconds)")
    except FileNotFoundError:
        error(
            "ripgrep (rg) not installed. Install it from: https://github.com/BurntSushi/ripgrep"
        )
