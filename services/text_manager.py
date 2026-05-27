import os
from typing import List, Optional

from rich.table import Table

from utils.console import (
    console,
    error,
    focus_text_editor_widget,
    show_text_editor_widget,
    success,
    update_text_editor_widget,
    warn,
)

TEXT_EDITOR_DIR = r"C:\Users\reeva\OneDrive\Desktop\text_editor"

_active_text_path: Optional[str] = None


def text_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args:
        _list_text_files()
        return

    action = str(args[0]).strip().lower()
    if action == "new":
        _create_text_file(_join_name(args[1:]))
        return
    if action == "delete":
        _delete_text_file(_join_name(args[1:]))
        return

    _open_text_file(_join_name(args))


def save_active_text(content: str) -> None:
    global _active_text_path

    if not _active_text_path:
        warn("No active text file to save.")
        return

    if not _ensure_editor_dir():
        return

    path = _active_text_path
    try:
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
    except Exception as exc:
        error(f"Failed to save text file: {exc}")
        return

    success(f"Saved: {os.path.basename(path)}")
    _active_text_path = None


def _list_text_files() -> None:
    if not _ensure_editor_dir():
        return

    try:
        entries = sorted(os.listdir(TEXT_EDITOR_DIR), key=str.lower)
    except OSError:
        error(f"Failed to read directory: {TEXT_EDITOR_DIR}")
        return

    files = [name for name in entries if name.lower().endswith(".txt")]
    if not files:
        warn("No text files found.")
        return

    table = Table(title=f"Text Files ({len(files)} found)")
    table.add_column("File", style="cyan")

    for name in files:
        table.add_row(name)

    console.print(table)


def _create_text_file(name: str) -> None:
    if not _ensure_editor_dir():
        return

    path = _build_path(name)
    if not path:
        error("Usage: text new <file_name>")
        return

    if os.path.exists(path):
        error(f"Text file already exists: {os.path.basename(path)}")
        return

    try:
        with open(path, "x", encoding="utf-8"):
            pass
    except FileExistsError:
        error(f"Text file already exists: {os.path.basename(path)}")
        return
    except Exception as exc:
        error(f"Failed to create text file: {exc}")
        return

    _open_text_file(os.path.basename(path))


def _delete_text_file(name: str) -> None:
    if not _ensure_editor_dir():
        return

    path = _build_path(name)
    if not path:
        error("Usage: text delete <file_name>")
        return

    if not os.path.exists(path):
        warn(f"Text file not found: {os.path.basename(path)}")
        return

    try:
        os.remove(path)
    except Exception as exc:
        error(f"Failed to delete text file: {exc}")
        return

    success(f"Deleted: {os.path.basename(path)}")


def _open_text_file(name: str) -> None:
    if not _ensure_editor_dir():
        return

    path = _build_path(name)
    if not path:
        error("Usage: text <file_name>")
        return

    if not os.path.exists(path):
        warn(f"Text file not found: {os.path.basename(path)}")
        return

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as file:
            content = file.read()
    except Exception as exc:
        error(f"Failed to read text file: {exc}")
        return

    _set_active_text_path(path)
    update_text_editor_widget(content)
    show_text_editor_widget()
    focus_text_editor_widget()


def _set_active_text_path(path: Optional[str]) -> None:
    global _active_text_path
    _active_text_path = path


def _join_name(parts: List[str]) -> str:
    if not parts:
        return ""
    return " ".join(str(part) for part in parts).strip()


def _ensure_editor_dir() -> bool:
    try:
        os.makedirs(TEXT_EDITOR_DIR, exist_ok=True)
    except Exception as exc:
        error(f"Failed to create text editor folder: {exc}")
        return False
    return True


def _build_path(name: str) -> Optional[str]:
    filename = _normalize_filename(name)
    if not filename:
        return None
    return os.path.join(TEXT_EDITOR_DIR, filename)


def _normalize_filename(name: str) -> Optional[str]:
    if name is None:
        return None

    filename = str(name).strip()
    if not filename:
        return None

    if os.path.basename(filename) != filename:
        return None

    if os.path.sep in filename:
        return None

    if os.path.altsep and os.path.altsep in filename:
        return None

    if ":" in filename:
        return None

    if not filename.lower().endswith(".txt"):
        filename = f"{filename}.txt"

    return filename
