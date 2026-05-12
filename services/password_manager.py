import json
import os
from typing import Dict, Optional

from rich.table import Table

from utils.console import console, error, info, success, warn

PASSWORDS_PATH = "config/passwords.json"


def _load_passwords() -> Optional[Dict[str, str]]:
    if not os.path.exists(PASSWORDS_PATH):
        return {}

    try:
        with open(PASSWORDS_PATH, "r", encoding="utf-8") as file:
            payload = json.load(file)
    except json.JSONDecodeError:
        error("Invalid passwords configuration.")
        return None
    except Exception as exc:
        error(f"Failed to load passwords: {exc}")
        return None

    if not isinstance(payload, dict):
        error("Invalid passwords configuration.")
        return None

    cleaned: Dict[str, str] = {}
    for key, value in payload.items():
        if key is None:
            continue
        cleaned[str(key)] = "" if value is None else str(value)

    return cleaned


def _save_passwords(passwords: Dict[str, str]) -> bool:
    try:
        with open(PASSWORDS_PATH, "w", encoding="utf-8") as file:
            json.dump(passwords, file, indent=2)
        return True
    except Exception as exc:
        error(f"Failed to save passwords: {exc}")
        return False


def password_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    passwords = _load_passwords()
    if passwords is None:
        return

    if not args:
        if not passwords:
            warn("No passwords saved.")
            return

        table = Table(title="Saved Passwords")
        table.add_column("Key", style="cyan")

        for key in sorted(passwords.keys(), key=str.lower):
            table.add_row(key)

        console.print(table)
        success(f"Total passwords: {len(passwords)}")
        return

    key = str(args[0]).strip()
    if not key:
        error("Usage: password <key_name>")
        return

    if key not in passwords:
        warn(f"Password not found: {key}")
        return

    info(f"{key}: {passwords[key]}")


def add_password_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args or len(args) < 3 or args[0] != "password":
        error("Usage: add password <key_name> <value_name>")
        return

    key = str(args[1]).strip()
    value = " ".join(str(part) for part in args[2:]).strip()

    if not key or not value:
        error("Usage: add password <key_name> <value_name>")
        return

    passwords = _load_passwords()
    if passwords is None:
        return

    if key in passwords:
        warn(f"Password already exists: {key}")
        info("Use: update password <key_name> <value_name>")
        return

    passwords[key] = value
    if _save_passwords(passwords):
        success(f"Password added: {key}")


def delete_password_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args or len(args) < 2 or args[0] != "password":
        error("Usage: delete password <key_name>")
        return

    key = str(args[1]).strip()
    if not key:
        error("Usage: delete password <key_name>")
        return

    passwords = _load_passwords()
    if passwords is None:
        return

    if key not in passwords:
        warn(f"Password not found: {key}")
        return

    del passwords[key]
    if _save_passwords(passwords):
        success(f"Password deleted: {key}")


def update_password_command(args, kwargs=None):
    if kwargs is None:
        kwargs = {}

    if not args or len(args) < 3 or args[0] != "password":
        error("Usage: update password <key_name> <value_name>")
        return

    key = str(args[1]).strip()
    value = " ".join(str(part) for part in args[2:]).strip()

    if not key or not value:
        error("Usage: update password <key_name> <value_name>")
        return

    passwords = _load_passwords()
    if passwords is None:
        return

    if key not in passwords:
        warn(f"Password not found: {key}")
        info("Use: add password <key_name> <value_name>")
        return

    passwords[key] = value
    if _save_passwords(passwords):
        success(f"Password updated: {key}")
