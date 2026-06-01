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
        error(
            "    OR: search <folder> for <name> [--type <ext>] [--max <num>] [--case-sensitive]"
        )
        return

    file_type = kwargs.get("type", None)
    max_results = kwargs.get("max", kwargs.get("m", None))
    ignore_case = "ignore-case" in kwargs or "i" in kwargs
    case_sensitive = "case-sensitive" in kwargs or "cs" in kwargs

    if len(args) >= 3 and args[1].lower() == "for":
        path = args[0]
        name_pattern = " ".join(args[2:]).strip()
        if not name_pattern:
            error(
                "Usage: search <folder> for <name> [--type <ext>] [--max <num>] [--case-sensitive]"
            )
            return

        # Validate path exists
        if not os.path.exists(path):
            error(f"Path not found: {path}")
            return

        match_case = case_sensitive and not ignore_case
        name_cmp = name_pattern if match_case else name_pattern.lower()

        ext_filter = None
        if file_type:
            ext_filter = file_type if file_type.startswith(".") else f".{file_type}"
            if not match_case:
                ext_filter = ext_filter.lower()

        results = []
        path_display = os.path.normpath(path)
        abs_path = os.path.abspath(path)
        base_name = os.path.basename(abs_path)
        base_cmp = base_name if match_case else base_name.lower()

        if name_cmp in base_cmp:
            if os.path.isdir(abs_path):
                results.append({"path": path_display, "kind": "dir"})
            else:
                base_cmp_ext = base_name if match_case else base_name.lower()
                if not ext_filter or base_cmp_ext.endswith(ext_filter):
                    results.append({"path": path_display, "kind": "file"})

        for root, dirs, files in os.walk(path):
            for dir_name in dirs:
                dir_cmp = dir_name if match_case else dir_name.lower()
                if name_cmp in dir_cmp:
                    results.append(
                        {
                            "path": os.path.normpath(os.path.join(root, dir_name)),
                            "kind": "dir",
                        }
                    )
            for file_name in files:
                file_cmp = file_name if match_case else file_name.lower()
                if name_cmp in file_cmp:
                    if ext_filter:
                        file_cmp_ext = file_name if match_case else file_name.lower()
                        if not file_cmp_ext.endswith(ext_filter):
                            continue
                    results.append(
                        {
                            "path": os.path.normpath(os.path.join(root, file_name)),
                            "kind": "file",
                        }
                    )

        if not results:
            warn(f"No matches found for '{name_pattern}' in '{path}'")
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

        table = Table(title=f"Name Results ({len(results)} found)")
        table.add_column("Path", style="cyan")
        table.add_column("Type", style="yellow")

        for result in results:
            table.add_row(result["path"], result["kind"])

        console.print(table)
        return

    pattern = args[0]
    path = kwargs.get("path", ".")

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
