from typing import Callable, Optional

from rich.console import Console, Group, RenderableType
from rich.text import Text

OutputHandler = Callable[[RenderableType], None]
StatsVisibilityHandler = Callable[[bool], None]
ConverterVisibilityHandler = Callable[[bool], None]
ThemeHandler = Callable[[str], None]

_output_handler: Optional[OutputHandler] = None
_stats_handler: Optional[OutputHandler] = None
_stats_visibility_handler: Optional[StatsVisibilityHandler] = None
_converter_handler: Optional[OutputHandler] = None
_converter_visibility_handler: Optional[ConverterVisibilityHandler] = None
_theme_handler: Optional[ThemeHandler] = None
_console = Console()


def set_output_handler(handler: Optional[OutputHandler]) -> None:
    global _output_handler
    _output_handler = handler


def set_stats_handler(handler: Optional[OutputHandler]) -> None:
    global _stats_handler
    _stats_handler = handler


def set_stats_visibility_handler(handler: Optional[StatsVisibilityHandler]) -> None:
    global _stats_visibility_handler
    _stats_visibility_handler = handler


def set_converter_handler(handler: Optional[OutputHandler]) -> None:
    global _converter_handler
    _converter_handler = handler


def set_converter_visibility_handler(
    handler: Optional[ConverterVisibilityHandler],
) -> None:
    global _converter_visibility_handler
    _converter_visibility_handler = handler


def set_theme_handler(handler: Optional[ThemeHandler]) -> None:
    global _theme_handler
    _theme_handler = handler


def request_theme_change(theme_name: str) -> bool:
    if _theme_handler is None:
        return False
    _theme_handler(theme_name)
    return True


def update_stats_widget(renderable: RenderableType) -> None:
    if _stats_handler is None:
        return
    _stats_handler(renderable)


def show_stats_widget() -> None:
    if _stats_visibility_handler is None:
        return
    _stats_visibility_handler(True)


def hide_stats_widget() -> None:
    if _stats_visibility_handler is None:
        return
    _stats_visibility_handler(False)


def update_converter_widget(renderable: RenderableType) -> None:
    if _converter_handler is None:
        return
    _converter_handler(renderable)


def show_converter_widget() -> None:
    if _converter_visibility_handler is None:
        return
    _converter_visibility_handler(True)


def hide_converter_widget() -> None:
    if _converter_visibility_handler is None:
        return
    _converter_visibility_handler(False)


class ConsoleRouter:
    def print(self, *objects, sep=" ", end="\n", **kwargs):
        if _output_handler is None:
            _console.print(*objects, sep=sep, end=end, **kwargs)
            return

        if not objects:
            if end:
                _output_handler(Text(""))
            return

        if len(objects) == 1:
            renderable = objects[0]
        else:
            if all(isinstance(obj, (str, Text)) for obj in objects):
                parts = []
                for index, obj in enumerate(objects):
                    if index:
                        parts.append(sep)
                    if isinstance(obj, Text):
                        parts.append(obj)
                    else:
                        parts.append(Text(str(obj)))
                renderable = Text.assemble(*parts)
            else:
                renderable = Group(*objects)

        _output_handler(renderable)

        if end and end != "\n":
            _output_handler(Text(end))


console = ConsoleRouter()


def info(msg):
    console.print(Text(str(msg), style="cyan"))


def success(msg):
    console.print(Text(str(msg), style="green"))


def error(msg):
    console.print(Text(str(msg), style="red"))


def warn(msg):
    console.print(Text(str(msg), style="yellow"))
