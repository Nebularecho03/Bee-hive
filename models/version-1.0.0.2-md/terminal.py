try:
    from rich.console import Console

    _console = Console()
    _use_rich = True
except Exception:
    _console = None
    _use_rich = False


def _print_plain(prefix, txt_input):
    print(f"[{prefix}] {txt_input}")


def info(txt_input):
    """General information in cyan."""
    if _use_rich:
        _console.print(f"[bold cyan][INFO][/] {txt_input}")
    else:
        _print_plain("INFO", txt_input)


def error(txt_input):
    """Critical errors in red."""
    if _use_rich:
        _console.print(f"[bold red][ERROR][/] {txt_input}")
    else:
        _print_plain("ERROR", txt_input)


def success(txt_input):
    """Successful operations in green."""
    if _use_rich:
        _console.print(f"[bold green][SUCCESS][/] {txt_input}")
    else:
        _print_plain("SUCCESS", txt_input)


def warning(txt_input):
    """Warnings in yellow."""
    if _use_rich:
        _console.print(f"[bold yellow][WARNING][/] {txt_input}")
    else:
        _print_plain("WARNING", txt_input)


def status(txt_input, is_loading=True):
    """Status updates with a separator."""
    symbol = "..." if is_loading else "OK"
    if _use_rich:
        _console.print(f"--- [magenta]{symbol} STATUS: {txt_input}[/] ---")
    else:
        _print_plain("STATUS", f"{symbol} {txt_input}")


def ask(question, color="bold yellow"):
    """Displays a styled question and returns the user's input."""
    if _use_rich:
        return _console.input(f"[{color}]? {question}:[/] ")
    return input(f"? {question}: ")
