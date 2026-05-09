import json
import os
from typing import List, Tuple, Any

from rich.text import Text

from core.state_manager import state_manager
from utils.console import console, error, warn

QUOTES_PATH = "config/quotes.json"
STATE_KEY = "quote_index"


def _load_quotes() -> List[Tuple[str, str]]:
    if not os.path.exists(QUOTES_PATH):
        error("Quotes configuration not found.")
        return []

    try:
        with open(QUOTES_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        error("Invalid quotes configuration.")
        return []
    except Exception as exc:
        error(f"Failed to load quotes: {exc}")
        return []

    if not isinstance(payload, dict) or not payload:
        warn("No quotes available.")
        return []

    return [(str(author), str(text)) for author, text in payload.items()]


def _get_next_quote_index(count: int) -> int:
    raw_index: Any = state_manager.get(STATE_KEY, 0)

    if raw_index is None:
        index = 0
    else:
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            index = 0

    if index < 0 or index >= count:
        index = 0

    next_index = (index + 1) % count
    state_manager.set(STATE_KEY, next_index)

    return index


def print_startup_quote() -> None:
    quotes = _load_quotes()
    if not quotes:
        return

    index = _get_next_quote_index(len(quotes))
    author, quote = quotes[index]

    line = Text('"', style="bright_black")
    line.append(quote, style="white")
    line.append('" - ', style="bright_black")
    line.append(author, style="cyan")
    console.print(line)
