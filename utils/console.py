from typing import Callable, Optional

from rich.console import Console, Group, RenderableType
from rich.text import Text

OutputHandler = Callable[[RenderableType], None]

_output_handler: Optional[OutputHandler] = None
_console = Console()


def set_output_handler(handler: Optional[OutputHandler]) -> None:
    global _output_handler
    _output_handler = handler


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
