import os
import zipfile
from typing import Iterable, List, Optional, Tuple

from utils.console import hide_zip_widget, info, show_zip_widget

DEFAULT_OUTPUT_DIR = r"C:\Users\reeva\OneDrive\Desktop"


def zip_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if _wants_close(args, kwargs):
        hide_zip_widget()
        info("Zip extractor hidden.")
        return

    show_zip_widget()
    info("Zip extractor opened. Drop .zip files into the panel.")


def extract_zip_files(
    paths: Iterable[str],
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> List[Tuple[str, Optional[str], bool, Optional[str]]]:
    targets = _normalize_paths(paths)
    if not targets:
        return []

    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    results: List[Tuple[str, Optional[str], bool, Optional[str]]] = []
    for path in targets:
        src = os.path.abspath(path)
        if not os.path.exists(src):
            results.append((src, None, False, "File not found"))
            continue

        if not src.lower().endswith(".zip"):
            results.append((src, None, False, "Not a .zip file"))
            continue

        base_name = os.path.splitext(os.path.basename(src))[0]
        dest_dir = _unique_folder(output_dir, base_name)
        try:
            os.makedirs(dest_dir, exist_ok=True)
            with zipfile.ZipFile(src, "r") as archive:
                _safe_extract(archive, dest_dir)
            results.append((src, dest_dir, True, None))
        except zipfile.BadZipFile:
            _cleanup_dir(dest_dir)
            results.append((src, dest_dir, False, "Invalid zip file"))
        except Exception as exc:
            _cleanup_dir(dest_dir)
            results.append((src, dest_dir, False, str(exc)))

    return results


def _safe_extract(archive: zipfile.ZipFile, dest_dir: str) -> None:
    base_dir = os.path.abspath(dest_dir)
    for member in archive.infolist():
        member_path = os.path.abspath(os.path.join(base_dir, member.filename))
        if (
            not member_path.startswith(base_dir + os.path.sep)
            and member_path != base_dir
        ):
            raise RuntimeError("Blocked unsafe path in zip file")
    archive.extractall(base_dir)


def _cleanup_dir(path: Optional[str]) -> None:
    if not path or not os.path.isdir(path):
        return
    try:
        if not os.listdir(path):
            os.rmdir(path)
    except Exception:
        return


def _unique_folder(base_dir: str, folder_name: str) -> str:
    name = folder_name.strip() or "extracted"
    candidate = os.path.join(base_dir, name)
    if not os.path.exists(candidate):
        return candidate
    index = 1
    while True:
        candidate = os.path.join(base_dir, f"{name} ({index})")
        if not os.path.exists(candidate):
            return candidate
        index += 1


def _normalize_paths(paths: Iterable[str]) -> List[str]:
    if paths is None:
        return []
    if isinstance(paths, (str, os.PathLike)):
        return [str(paths)]
    return [str(path) for path in paths]


def _wants_close(args, kwargs) -> bool:
    if "hide" in kwargs or "close" in kwargs:
        return True
    if args:
        action = str(args[0]).strip().lower()
        if action in {"hide", "close"}:
            return True
    return False
