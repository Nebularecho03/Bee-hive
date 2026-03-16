import json
import platform
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from chain import build_entry, validate_entry
from repo_sync import ensure_repo
from terminal import error, info, success, warning


@dataclass
class Message:
    msg_type: str
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    payload: Optional[str] = None
    peers: List[str] = field(default_factory=list)
    ts: Optional[str] = None

    def to_wire(self):
        if self.ts is None:
            self.ts = _utc_rfc3339_nano()
        obj = {
            "type": self.msg_type,
            "from": self.from_id,
            "to": self.to_id,
            "payload": self.payload,
            "peers": self.peers,
            "ts": self.ts,
        }
        return {k: v for k, v in obj.items() if v not in (None, [], "")}

    @staticmethod
    def from_wire(obj):
        return Message(
            msg_type=obj.get("type", ""),
            from_id=obj.get("from"),
            to_id=obj.get("to"),
            payload=obj.get("payload"),
            peers=obj.get("peers") or [],
            ts=obj.get("ts"),
        )


def _utc_rfc3339_nano():
    # Python doesn't support RFC3339Nano directly; this is a close equivalent.
    t = time.time()
    seconds = int(t)
    nanos = int((t - seconds) * 1_000_000_000)
    base = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(seconds))
    return f"{base}.{nanos:09d}Z"


class JsonLineSocket:
    def __init__(self, sock):
        self.sock = sock
        self._lock = threading.Lock()
        self._buffer = b""

    def send(self, msg):
        data = json.dumps(msg).encode("utf-8") + b"\n"
        with self._lock:
            self.sock.sendall(data)

    def recv(self):
        while b"\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("socket closed")
            self._buffer += chunk
        line, self._buffer = self._buffer.split(b"\n", 1)
        return json.loads(line.decode("utf-8"))


class QueenServer:
    def __init__(self, addr, dashboard=None):
        self.addr = addr
        self._clients: Dict[str, JsonLineSocket] = {}
        self._lock = threading.RLock()
        self._running = False
        self._dashboard = dashboard
        self._chain_tip = ""

    def start(self):
        self._running = True
        info(f"queen listening on {self.addr}")
        if self._dashboard:
            self._dashboard.set_addr(self.addr)
            self._dashboard.start()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(self.addr)
            server.listen()
            while self._running:
                conn, _ = server.accept()
                threading.Thread(target=self._handle_conn, args=(conn,), daemon=True).start()

    def _handle_conn(self, conn):
        with conn:
            js = JsonLineSocket(conn)
            try:
                first = Message.from_wire(js.recv())
            except Exception as exc:
                warning(f"register recv failed: {exc}")
                return
            if first.msg_type != "register" or not first.from_id:
                js.send(Message(msg_type="error", payload="first message must be register with from").to_wire())
                return

            if not self._add_client(first.from_id, js):
                js.send(Message(msg_type="error", payload="id already connected").to_wire())
                return

            js.send(Message(msg_type="registered", payload=f"welcome {first.from_id}").to_wire())
            success(f"registered {first.from_id}")
            if self._dashboard:
                self._dashboard.add_event(f"registered {first.from_id}")
                self._dashboard.set_clients(list(self._clients.keys()))

            try:
                while True:
                    msg = Message.from_wire(js.recv())
                    if msg.msg_type == "send":
                        self._handle_send(first.from_id, msg)
                    elif msg.msg_type == "broadcast":
                        self._handle_broadcast(first.from_id, msg)
                    elif msg.msg_type == "list":
                        self._handle_list(first.from_id)
                    elif msg.msg_type == "chain_add":
                        self._handle_chain_add(first.from_id, msg)
                    elif msg.msg_type == "repo_update":
                        self._handle_repo_update(first.from_id, msg)
                    elif msg.msg_type == "repo_status":
                        self._handle_repo_status(first.from_id, msg)
                    elif msg.msg_type == "heartbeat":
                        continue
                    else:
                        js.send(Message(msg_type="error", payload="unknown message type").to_wire())
            except Exception as exc:
                warning(f"client {first.from_id} disconnected: {exc}")
            finally:
                self._remove_client(first.from_id)
                if self._dashboard:
                    self._dashboard.add_event(f"disconnected {first.from_id}")
                    self._dashboard.set_clients(list(self._clients.keys()))

    def _add_client(self, client_id, js):
        with self._lock:
            if client_id in self._clients:
                return False
            self._clients[client_id] = js
            return True

    def _remove_client(self, client_id):
        with self._lock:
            if client_id in self._clients:
                del self._clients[client_id]

    def _handle_send(self, sender_id, msg):
        if not msg.to_id:
            self._safe_send(sender_id, Message(msg_type="error", payload="send requires to"))
            return
        with self._lock:
            target = self._clients.get(msg.to_id)
        if target is None:
            self._safe_send(sender_id, Message(msg_type="error", payload="target not connected"))
            return
        target.send(Message(msg_type="message", from_id=sender_id, payload=msg.payload).to_wire())

    def _handle_broadcast(self, sender_id, msg):
        with self._lock:
            for client_id, js in self._clients.items():
                if client_id == sender_id:
                    continue
                js.send(Message(msg_type="message", from_id=sender_id, payload=msg.payload).to_wire())

    def _handle_list(self, sender_id):
        with self._lock:
            peers = list(self._clients.keys())
        self._safe_send(sender_id, Message(msg_type="peers", peers=peers))

    def _safe_send(self, sender_id, msg):
        with self._lock:
            js = self._clients.get(sender_id)
        if js:
            js.send(msg.to_wire())

    def _handle_chain_add(self, sender_id, msg):
        try:
            payload_obj = json.loads(msg.payload or "{}")
        except Exception:
            warning("invalid chain payload from sender")
            return
        data = payload_obj.get("data", {})
        ts = payload_obj.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = build_entry(sender_id, ts, data, self._chain_tip)
        self._chain_tip = entry["hash"]
        payload = json.dumps(entry, separators=(",", ":"), sort_keys=True)
        with self._lock:
            items = list(self._clients.items())
        for client_id, js in items:
            js.send(Message(msg_type="chain_add", from_id=sender_id, payload=payload).to_wire())
        if self._dashboard:
            self._dashboard.add_event(f"chain add from {sender_id}")

    def _handle_repo_update(self, sender_id, msg):
        with self._lock:
            items = list(self._clients.items())
        for _, js in items:
            js.send(
                Message(msg_type="repo_update", from_id=sender_id, payload=msg.payload).to_wire()
            )
        if self._dashboard:
            self._dashboard.add_event(f"repo update from {sender_id}")

    def _handle_repo_status(self, sender_id, msg):
        if self._dashboard:
            self._dashboard.add_event(f"repo status {sender_id}: {msg.payload}")

    def get_clients(self):
        with self._lock:
            return list(self._clients.keys())

    def create_task(self, target_id, payload):
        if target_id == "all":
            self._broadcast_task(payload)
        else:
            self._send_task(target_id, payload)

    def _send_task(self, target_id, payload):
        with self._lock:
            js = self._clients.get(target_id)
        if not js:
            warning(f"task target not connected: {target_id}")
            return
        js.send(Message(msg_type="task", from_id="queen", payload=payload).to_wire())
        if self._dashboard:
            self._dashboard.inc_tasks()
            self._dashboard.add_event(f"task -> {target_id}: {payload}")

    def _broadcast_task(self, payload):
        with self._lock:
            items = list(self._clients.items())
        for client_id, js in items:
            js.send(Message(msg_type="task", from_id="queen", payload=payload).to_wire())
        if self._dashboard:
            self._dashboard.inc_tasks()
            self._dashboard.add_event(f"task -> all: {payload}")


class BeeClient:
    def __init__(
        self,
        bee_id,
        codename,
        queen_host,
        queen_port,
        heartbeat_interval=5.0,
        reconnect_delay=2.0,
        db=None,
        dashboard=None,
        repo_url="",
        repo_branch="main",
        repo_path="bee_repo",
        update_interval=60.0,
        updater=False,
    ):
        self.bee_id = bee_id
        self.codename = codename
        self.queen_host = queen_host
        self.queen_port = queen_port
        self.heartbeat_interval = heartbeat_interval
        self.reconnect_delay = reconnect_delay
        self._db = db
        self._dashboard = dashboard
        self.repo_url = repo_url
        self.repo_branch = repo_branch
        self.repo_path = repo_path
        self.update_interval = update_interval
        self.updater = updater
        self._socket = None
        self._js = None
        self._listen_thread = None
        self._heartbeat_thread = None
        self._update_thread = None
        self._running = False
        self._connected = False
        self._sent_os_record = False

    def connect(self):
        self._running = True
        if self._dashboard:
            self._dashboard.set_identity(self.bee_id, self.codename)
            self._dashboard.start()
        self._connect_loop()

    def _connect_loop(self):
        while self._running:
            try:
                self._socket = socket.create_connection((self.queen_host, self.queen_port))
                self._js = JsonLineSocket(self._socket)
                self._js.send(Message(msg_type="register", from_id=self.bee_id).to_wire())
                reply = Message.from_wire(self._js.recv())
                if reply.msg_type == "error":
                    raise RuntimeError(reply.payload or "register failed")
                self._connected = True
                success(reply.payload or "registered")
                if self._dashboard:
                    local = None
                    try:
                        local = f"{self._socket.getsockname()[0]}:{self._socket.getsockname()[1]}"
                    except Exception:
                        pass
                    self._dashboard.set_connection(
                        f"{self.queen_host}:{self.queen_port}",
                        local,
                        True,
                    )
                    self._dashboard.add_event("connected")
                if self._db:
                    self._db.set_meta("queen", f"{self.queen_host}:{self.queen_port}")
                self._listen_thread = threading.Thread(target=self._listen, daemon=True)
                self._listen_thread.start()
                self._heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
                self._heartbeat_thread.start()
                if self.updater and self.repo_url:
                    self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
                    self._update_thread.start()
                if not self._sent_os_record:
                    self._send_os_record()
                    self._sent_os_record = True
                return
            except Exception as exc:
                warning(f"connect failed: {exc}")
                time.sleep(self.reconnect_delay)

    def close(self):
        self._running = False
        self._connected = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass

    def _listen(self):
        while self._running and self._connected:
            try:
                msg = Message.from_wire(self._js.recv())
            except Exception:
                self._connected = False
                break
            if msg.msg_type == "message":
                info(f"{msg.from_id}: {msg.payload}")
                if self._db:
                    self._db.log_message("in", msg.from_id, msg.msg_type, msg.payload)
                if self._dashboard:
                    self._dashboard.inc_messages()
                    self._dashboard.add_event(f"msg from {msg.from_id}: {msg.payload}")
            elif msg.msg_type == "peers":
                info(f"peers: {', '.join(msg.peers)}")
                if self._db:
                    self._db.log_peers(msg.peers)
                if self._dashboard:
                    self._dashboard.add_event("peers updated")
            elif msg.msg_type == "error":
                error(msg.payload or "error")
                if self._dashboard:
                    self._dashboard.add_event(f"error: {msg.payload}")
            elif msg.msg_type == "task":
                info(f"task from queen: {msg.payload}")
                if self._db:
                    self._db.log_task(msg.from_id, msg.payload)
                if self._dashboard:
                    self._dashboard.inc_tasks()
                    self._dashboard.add_event(f"task: {msg.payload}")
                self._handle_task(msg.payload or "")
            elif msg.msg_type == "chain_add":
                self._handle_chain_add(msg)
            elif msg.msg_type == "repo_update":
                self._handle_repo_update(msg)
        if self._running and not self._connected:
            warning("connection lost, reconnecting...")
            if self._dashboard:
                self._dashboard.set_connection(f"{self.queen_host}:{self.queen_port}", None, False)
                self._dashboard.add_event("disconnected")
            self._connect_loop()

    def _heartbeat(self):
        while self._running and self._connected:
            try:
                self._js.send(Message(msg_type="heartbeat").to_wire())
            except Exception:
                self._connected = False
                break
            time.sleep(self.heartbeat_interval)

    def send(self, to_id, payload):
        if not self._connected:
            warning("not connected")
            return
        self._js.send(Message(msg_type="send", to_id=to_id, payload=payload).to_wire())
        if self._db:
            self._db.log_message("out", to_id, "send", payload)

    def broadcast(self, payload):
        if not self._connected:
            warning("not connected")
            return
        self._js.send(Message(msg_type="broadcast", payload=payload).to_wire())
        if self._db:
            self._db.log_message("out", "all", "broadcast", payload)

    def list_peers(self):
        if not self._connected:
            warning("not connected")
            return
        self._js.send(Message(msg_type="list").to_wire())

    def _send_os_record(self):
        data = {
            "os": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        }
        prev_hash = self._db.get_chain_tip() if self._db else ""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = build_entry(self.bee_id, ts, data, prev_hash)
        self._broadcast_chain_entry(entry)

    def _broadcast_chain_entry(self, entry):
        payload = json.dumps(entry, separators=(",", ":"), sort_keys=True)
        self._js.send(Message(msg_type="chain_add", payload=payload).to_wire())
        if self._db:
            self._db.log_message("out", "chain", "chain_add", payload)
        if self._dashboard:
            self._dashboard.add_event("chain add sent")

    def _handle_chain_add(self, msg):
        try:
            entry = json.loads(msg.payload or "{}")
        except Exception:
            warning("invalid chain payload")
            return
        if not validate_entry(entry):
            warning("invalid chain hash")
            return
        if self._db:
            tip = self._db.get_chain_tip()
            prev = entry.get("prev_hash", "")
            if tip and prev != tip:
                warning("chain prev_hash mismatch; ignoring")
                return
            if not tip and prev:
                warning("chain prev_hash not empty on genesis; ignoring")
                return
            entry_db = {
                "ts": entry.get("ts", ""),
                "author": entry.get("author", ""),
                "data_json": json.dumps(entry.get("data", {}), separators=(",", ":")),
                "prev_hash": prev,
                "hash": entry.get("hash", ""),
            }
            self._db.append_chain(entry_db)
            if self._dashboard:
                self._dashboard.add_event(f"chain add from {entry.get('author', '-')}")

    def add_chain_note(self, note):
        if not self._connected:
            warning("not connected")
            return
        data = {"note": note}
        prev_hash = self._db.get_chain_tip() if self._db else ""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        entry = build_entry(self.bee_id, ts, data, prev_hash)
        self._broadcast_chain_entry(entry)

    def _update_loop(self):
        while self._running and self._connected:
            try:
                self._perform_repo_update(broadcast=True)
            except Exception as exc:
                warning(f"repo update failed: {exc}")
                if self._dashboard:
                    self._dashboard.add_event("repo update failed")
                self._send_repo_status(False, "", str(exc))
            time.sleep(self.update_interval)

    def _handle_repo_update(self, msg):
        try:
            data = json.loads(msg.payload or "{}")
        except Exception:
            warning("invalid repo update payload")
            return
        url = data.get("url") or self.repo_url
        branch = data.get("branch") or self.repo_branch
        if not url:
            warning("repo update missing url")
            return
        try:
            updated, commit = ensure_repo(url, branch, self.repo_path)
            if updated:
                info(f"repo updated to {commit[:8]}")
                if self._db:
                    self._db.log_message("in", "repo", "repo_update", msg.payload)
                if self._dashboard:
                    self._dashboard.add_event(f"repo pulled {commit[:8]}")
            self._send_repo_status(updated, commit, None)
        except Exception as exc:
            warning(f"repo pull failed: {exc}")
            self._send_repo_status(False, "", str(exc))

    def _perform_repo_update(self, broadcast):
        if not self.repo_url:
            return
        updated, commit = ensure_repo(self.repo_url, self.repo_branch, self.repo_path)
        if broadcast:
            payload = json.dumps(
                {"url": self.repo_url, "branch": self.repo_branch, "commit": commit},
                separators=(",", ":"),
                sort_keys=True,
            )
            self._js.send(Message(msg_type="repo_update", payload=payload).to_wire())
            if self._db:
                self._db.log_message("out", "repo", "repo_update", payload)
            if self._dashboard:
                self._dashboard.add_event(f"repo update {commit[:8]}")
        self._send_repo_status(updated, commit, None)

    def _send_repo_status(self, updated, commit, err):
        status = "updated" if updated else "no_change"
        if err:
            status = "error"
        payload = json.dumps(
            {"status": status, "commit": commit, "error": err or ""},
            separators=(",", ":"),
            sort_keys=True,
        )
        try:
            self._js.send(Message(msg_type="repo_status", payload=payload).to_wire())
        except Exception:
            pass

    def _handle_task(self, payload):
        if payload.strip() == "repo_update_now":
            threading.Thread(target=self._perform_repo_update, args=(True,), daemon=True).start()
