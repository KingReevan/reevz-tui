from rich.console import Console

console = Console()


def info(msg):
    console.print(f"[cyan]{msg}[/cyan]")


def success(msg):
    console.print(f"[green]{msg}[/green]")


def error(msg):
    console.print(f"[red]{msg}[/red]")


def warn(msg):
    console.print(f"[yellow]{msg}[/yellow]")
