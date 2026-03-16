import sqlite3
import threading
import time


def _utc_ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class BeeDatabase:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._migrate()

    def _migrate(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    peer TEXT,
                    msg_type TEXT NOT NULL,
                    payload TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    from_id TEXT,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'received'
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS peers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    peer TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    name TEXT NOT NULL,
                    args TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chain (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    author TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    hash TEXT NOT NULL
                )
                """
            )

    def close(self):
        with self._lock:
            self._conn.close()

    def set_meta(self, key, value):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def log_message(self, direction, peer, msg_type, payload):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (ts, direction, peer, msg_type, payload) VALUES (?, ?, ?, ?, ?)",
                (_utc_ts(), direction, peer, msg_type, payload),
            )

    def log_task(self, from_id, task):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tasks (ts, from_id, task) VALUES (?, ?, ?)",
                (_utc_ts(), from_id, task),
            )

    def log_peers(self, peers):
        with self._lock, self._conn:
            for peer in peers:
                self._conn.execute(
                    "INSERT INTO peers (ts, peer) VALUES (?, ?)",
                    (_utc_ts(), peer),
                )

    def log_command(self, name, args):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO commands (ts, name, args) VALUES (?, ?, ?)",
                (_utc_ts(), name, args),
            )

    def get_chain_tip(self):
        with self._lock:
            cur = self._conn.execute("SELECT hash FROM chain ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else ""

    def append_chain(self, entry):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO chain (ts, author, data_json, prev_hash, hash) VALUES (?, ?, ?, ?, ?)",
                (entry["ts"], entry["author"], entry["data_json"], entry["prev_hash"], entry["hash"]),
            )

    def chain_count(self):
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM chain")
            return int(cur.fetchone()[0])
