import os
from typing import List, Optional

from rich.table import Table
from rich.text import Text

from utils.console import (
	console,
	error,
	hide_music_widget,
	show_music_widget,
	success,
	update_music_widget,
	warn,
)

MUSIC_DIR = r"C:\Users\reeva\OneDrive\Desktop\music_manager"

_player = None
_current_track: Optional[str] = None


def music_command(args, kwargs=None):
	if kwargs is None:
		kwargs = {}

	if not args:
		_list_songs()
		_show_panel_state()
		return

	action = str(args[0]).strip().lower()
	if action == "pause":
		_stop_playback()
		return

	_play_song(_join_name(args))


def _list_songs() -> None:
	if not _ensure_music_dir():
		return

	try:
		entries = sorted(os.listdir(MUSIC_DIR), key=str.lower)
	except OSError:
		error(f"Failed to read directory: {MUSIC_DIR}")
		return

	songs = [name for name in entries if name.lower().endswith(".mp3")]
	if not songs:
		warn("No mp3 files found.")
		return

	table = Table(title=f"Songs ({len(songs)} found)")
	table.add_column("Song", style="cyan")

	for song in songs:
		table.add_row(song)

	console.print(table)


def _play_song(name: str) -> None:
	if not _ensure_music_dir():
		return

	filename = _normalize_filename(name)
	if not filename:
		error("Usage: music <song_name>")
		return

	path = os.path.join(MUSIC_DIR, filename)
	if not os.path.exists(path):
		warn(f"Song not found: {filename}")
		return

	vlc_module = _get_vlc_module()
	if vlc_module is None:
		return

	_stop_playback(hide_panel=False, quiet=True)

	try:
		player = vlc_module.MediaPlayer(path)
		result = player.play()
	except Exception as exc:
		error(f"Failed to start playback: {exc}")
		return

	if result == -1:
		error("Failed to start playback.")
		return

	_set_active_player(player, filename)
	success(f"Now playing: {filename}")
	_show_panel_state()


def _stop_playback(hide_panel: bool = True, quiet: bool = False) -> None:
	global _player
	global _current_track

	if _player is None or not _current_track:
		if not quiet:
			warn("No music is currently playing.")
		if hide_panel:
			hide_music_widget()
		return

	try:
		_player.stop()
	except Exception:
		pass

	stopped_track = _current_track
	_player = None
	_current_track = None

	if not quiet:
		success(f"Stopped: {stopped_track}")

	if hide_panel:
		hide_music_widget()


def _show_panel_state() -> None:
	if _current_track:
		update_music_widget(Text(f"Now Playing: {_current_track}", style="green"))
	else:
		update_music_widget(Text("No music playing.", style="dim"))
	show_music_widget()


def _set_active_player(player, track_name: str) -> None:
	global _player
	global _current_track
	_player = player
	_current_track = track_name


def _get_vlc_module():
	try:
		import vlc  # type: ignore
	except Exception:
		error(
			"python-vlc is not installed. Install with: pip install python-vlc "
			"(VLC must be installed)."
		)
		return None

	try:
		vlc.Instance()
	except Exception as exc:
		error(f"VLC is not available: {exc}")
		return None

	return vlc


def _join_name(parts: List[str]) -> str:
	if not parts:
		return ""
	return " ".join(str(part) for part in parts).strip()


def _ensure_music_dir() -> bool:
	try:
		os.makedirs(MUSIC_DIR, exist_ok=True)
	except Exception as exc:
		error(f"Failed to access music folder: {exc}")
		return False
	return True


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

	if not filename.lower().endswith(".mp3"):
		filename = f"{filename}.mp3"

	return filename
