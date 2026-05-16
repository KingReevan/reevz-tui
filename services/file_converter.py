import os
from typing import Iterable, List, Optional, Tuple

from utils.console import error, info, hide_converter_widget, show_converter_widget

DEFAULT_OUTPUT_DIR = r"C:\Users\reeva\OneDrive\Desktop"
WORD_PDF_FORMAT = 17


def convert_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if _wants_close(args, kwargs):
        hide_converter_widget()
        info("File converter hidden.")
        return

    if not _is_doc_to_pdf(args):
        error("Usage: convert doc to pdf")
        return

    show_converter_widget()
    info("File converter opened. Drop .doc/.docx files into the panel.")


def convert_word_files(
    paths: Iterable[str],
    output_dir: str = DEFAULT_OUTPUT_DIR,
) -> List[Tuple[str, Optional[str], bool, Optional[str]]]:
    targets = _normalize_paths(paths)
    if not targets:
        return []

    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    try:
        import pythoncom
        import win32com.client
    except Exception as exc:
        raise RuntimeError(
            "pywin32 is required for Word conversion. Install with: pip install pywin32"
        ) from exc

    co_initialized = False
    pythoncom.CoInitialize()
    co_initialized = True
    word = None
    results: List[Tuple[str, Optional[str], bool, Optional[str]]] = []

    try:
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        for path in targets:
            src = os.path.abspath(path)
            if not os.path.exists(src):
                results.append((src, None, False, "File not found"))
                continue

            base_name = os.path.splitext(os.path.basename(src))[0]
            dest = os.path.join(output_dir, f"{base_name}.pdf")
            doc = None

            try:
                doc = word.Documents.Open(src)
                doc.ExportAsFixedFormat(
                    OutputFileName=dest,
                    ExportFormat=WORD_PDF_FORMAT,
                )
                doc.Close(False)
                results.append((src, dest, True, None))
            except Exception as exc:
                if doc is not None:
                    try:
                        doc.Close(False)
                    except Exception:
                        pass
                results.append((src, dest, False, str(exc)))
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        if co_initialized:
            pythoncom.CoUninitialize()

    return results


def _normalize_paths(paths: Iterable[str]) -> List[str]:
    if paths is None:
        return []
    if isinstance(paths, (str, os.PathLike)):
        return [str(paths)]
    return [str(path) for path in paths]


def _is_doc_to_pdf(args) -> bool:
    if not args or len(args) < 3:
        return False
    source = str(args[0]).strip().lower()
    to_token = str(args[1]).strip().lower()
    target = str(args[2]).strip().lower()
    return source in {"doc", "docx"} and to_token == "to" and target == "pdf"


def _wants_close(args, kwargs) -> bool:
    if "hide" in kwargs or "close" in kwargs:
        return True
    if args:
        action = str(args[0]).strip().lower()
        if action in {"hide", "close"}:
            return True
    return False
