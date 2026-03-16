import sys
import threading
import time
from collections import deque

try:
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    _RICH_OK = True
except Exception:
    _RICH_OK = False


def _utc_ts():
    return time.strftime("%H:%M:%S", time.gmtime())


class _BaseDashboard:
    def __init__(self, title):
        self.title = title
        self._lock = threading.Lock()
        self._events = deque(maxlen=12)
        self._running = False
        self._thread = None
        self._console = Console()

    def start(self):
        if not _RICH_OK or not sys.stdout.isatty():
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def add_event(self, text):
        with self._lock:
            self._events.appendleft(f"{_utc_ts()} {text}")

    def _run(self):
        with Live(self._render(), console=self._console, refresh_per_second=4) as live:
            while self._running:
                live.update(self._render())
                time.sleep(0.2)

    def _render(self):
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
        )
        layout["header"].update(Panel(Text(self.title, style="bold cyan"), border_style="cyan"))
        body = Layout()
        body.split_row(Layout(name="left"), Layout(name="right"))
        body["left"].update(self._render_info())
        body["right"].update(self._render_events())
        layout["body"].update(body)
        return layout

    def _render_info(self):
        table = Table(show_header=False, box=None, pad_edge=False)
        for key, value in self._info_items():
            table.add_row(f"[bold]{key}[/]", str(value))
        return Panel(table, title="status", border_style="green")

    def _render_events(self):
        with self._lock:
            lines = list(self._events)
        text = Text("\n".join(lines) if lines else "no events yet", style="white")
        return Panel(text, title="events", border_style="yellow")

    def _info_items(self):
        return []


class BeeDashboard(_BaseDashboard):
    def __init__(self):
        super().__init__("Bee Console")
        self._state = {
            "id": "-",
            "codename": "-",
            "queen": "-",
            "local": "-",
            "connected": "no",
            "messages": 0,
            "tasks": 0,
        }

    def set_identity(self, bee_id, codename):
        self._state["id"] = bee_id
        self._state["codename"] = codename

    def set_connection(self, queen_addr, local_addr, connected):
        self._state["queen"] = queen_addr
        self._state["local"] = local_addr or "-"
        self._state["connected"] = "yes" if connected else "no"

    def inc_messages(self):
        self._state["messages"] += 1

    def inc_tasks(self):
        self._state["tasks"] += 1

    def _info_items(self):
        return [
            ("id", self._state["id"]),
            ("codename", self._state["codename"]),
            ("queen", self._state["queen"]),
            ("local", self._state["local"]),
            ("connected", self._state["connected"]),
            ("messages", self._state["messages"]),
            ("tasks", self._state["tasks"]),
        ]


class QueenDashboard(_BaseDashboard):
    def __init__(self):
        super().__init__("Queen Console")
        self._state = {
            "addr": "-",
            "clients": 0,
            "tasks_sent": 0,
        }
        self._clients = []

    def set_addr(self, addr):
        self._state["addr"] = addr

    def set_clients(self, clients):
        self._clients = sorted(clients)
        self._state["clients"] = len(self._clients)

    def inc_tasks(self):
        self._state["tasks_sent"] += 1

    def _render_info(self):
        table = Table(show_header=False, box=None, pad_edge=False)
        table.add_row("[bold]addr[/]", str(self._state["addr"]))
        table.add_row("[bold]clients[/]", str(self._state["clients"]))
        table.add_row("[bold]tasks[/]", str(self._state["tasks_sent"]))
        table.add_row("[bold]client list[/]", ", ".join(self._clients) if self._clients else "-")
        return Panel(table, title="status", border_style="green")
