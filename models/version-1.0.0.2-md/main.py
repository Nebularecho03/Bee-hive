import argparse
import json
import os
import sys
import threading

from bee_db import BeeDatabase
from code_name import new_codename, now_id
from conect_to_network import BeeClient, QueenServer
from dashboard import BeeDashboard, QueenDashboard
from docker_spawn import spawn_bees
from terminal import info, status, warning


def _parse_args(argv):
    parser = argparse.ArgumentParser(description="Bee swarm model (Python)")
    sub = parser.add_subparsers(dest="role", required=True)

    queen = sub.add_parser("queen", help="start a queen server")
    queen.add_argument("--host", default="0.0.0.0", help="bind host")
    queen.add_argument("--port", default=9000, type=int, help="bind port")
    queen.add_argument("--admin", default=True, action=argparse.BooleanOptionalAction, help="queen admin console")
    queen.add_argument("--ui", default=True, action=argparse.BooleanOptionalAction, help="enable queen dashboard")

    bee = sub.add_parser("bee", help="start a bee client")
    bee.add_argument(
        "--id",
        dest="bee_id",
        default=os.getenv("BEE_ID", os.getenv("HOSTNAME", "")),
        help="bee id (auto if empty)",
    )
    bee.add_argument("--codename", default=os.getenv("BEE_CODENAME", ""), help="bee codename (auto if empty)")
    bee.add_argument("--queen-host", default="127.0.0.1", help="queen host")
    bee.add_argument("--queen-port", default=9000, type=int, help="queen port")
    bee.add_argument("--commands", default="", help="path to commands JSON")
    bee.add_argument("--heartbeat", default=5.0, type=float, help="heartbeat interval seconds")
    bee.add_argument("--reconnect", default=2.0, type=float, help="reconnect delay seconds")
    bee.add_argument("--db", default="", help="path to bee sqlite db")
    bee.add_argument("--ui", default=True, action=argparse.BooleanOptionalAction, help="enable bee dashboard")
    bee.add_argument("--repo-url", default="https://github.com/Nebularecho03/Bee-hive.git", help="repo url")
    bee.add_argument("--repo-branch", default="main", help="repo branch")
    bee.add_argument("--repo-path", default="bee_repo", help="local repo path")
    bee.add_argument("--update-interval", default=60.0, type=float, help="repo update check seconds")
    bee.add_argument("--updater", default=False, action=argparse.BooleanOptionalAction, help="enable repo updater")

    return parser.parse_args(argv)


def _run_queen(args):
    dashboard = QueenDashboard() if args.ui else None
    server = QueenServer((args.host, args.port), dashboard=dashboard)
    status("queen starting...", is_loading=True)
    if args.admin:
        admin = threading.Thread(target=_queen_admin_repl, args=(server,), daemon=True)
        admin.start()
    server.start()


def _run_bee(args):
    bee_id = args.bee_id or now_id()
    codename = args.codename or new_codename()
    db_path = args.db or f"bee_{bee_id}.db"
    db = BeeDatabase(db_path)
    db.set_meta("id", bee_id)
    db.set_meta("codename", codename)
    dashboard = BeeDashboard() if args.ui else None
    client = BeeClient(
        bee_id,
        codename,
        args.queen_host,
        args.queen_port,
        heartbeat_interval=args.heartbeat,
        reconnect_delay=args.reconnect,
        db=db,
        dashboard=dashboard,
        repo_url=args.repo_url,
        repo_branch=args.repo_branch,
        repo_path=args.repo_path,
        update_interval=args.update_interval,
        updater=args.updater,
    )
    info(f"bee id: {bee_id}")
    info(f"codename: {codename}")
    status("connecting to queen...", is_loading=True)
    client.connect()
    status("connected", is_loading=False)
    _repl(client, args.commands, db)
    db.close()


def _repl(client, commands_path, db):
    help_text = (
        "commands:\n"
        "  help\n"
        "  identity\n"
        "  list\n"
        "  send <id> <message>\n"
        "  broadcast <message>\n"
        "  commands\n"
        "  run <name> [args...]\n"
        "  tasks\n"
        "  chain\n"
        "  chain-add <text>\n"
        "  quit\n"
    )
    print(help_text)
    commands = _load_commands(commands_path)
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "help":
            print(help_text)
        elif line == "identity":
            info(f"id: {client.bee_id}, codename: {client.codename}")
        elif line == "list":
            client.list_peers()
        elif line.startswith("send "):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                warning("usage: send <id> <message>")
                continue
            client.send(parts[1], parts[2])
        elif line.startswith("broadcast "):
            msg = line[len("broadcast ") :].strip()
            if not msg:
                warning("usage: broadcast <message>")
                continue
            client.broadcast(msg)
        elif line == "commands":
            _print_commands(commands)
        elif line.startswith("run "):
            parts = line.split(" ", 2)
            name = parts[1] if len(parts) > 1 else ""
            args = parts[2] if len(parts) > 2 else ""
            _run_command(client, commands, name, args, db)
        elif line == "tasks":
            info("tasks are stored in the sqlite db")
        elif line == "chain":
            if db:
                info(f"chain entries: {db.chain_count()}")
            else:
                info("db not enabled")
        elif line.startswith("chain-add "):
            note = line[len("chain-add ") :].strip()
            if not note:
                warning("usage: chain-add <text>")
                continue
            client.add_chain_note(note)
        elif line in ("quit", "exit"):
            break
        else:
            warning("unknown command, type 'help'")
    client.close()


def main(argv=None):
    args = _parse_args(argv or sys.argv[1:])
    if args.role == "queen":
        _run_queen(args)
    elif args.role == "bee":
        _run_bee(args)


def _load_commands(commands_path):
    if not commands_path:
        return []
    try:
        with open(commands_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            warning("commands file must be a list")
            return []
        return data
    except Exception as exc:
        warning(f"failed to load commands: {exc}")
        return []


def _print_commands(commands):
    if not commands:
        info("no commands loaded")
        return
    for cmd in commands:
        name = cmd.get("name", "")
        action = cmd.get("action", "")
        payload = cmd.get("payload", "")
        print(f"- {name}: {action} '{payload}'")


def _run_command(client, commands, name, args, db):
    if not name:
        warning("usage: run <name> [args...]")
        return
    cmd = next((c for c in commands if c.get("name") == name), None)
    if not cmd:
        warning(f"unknown command: {name}")
        return
    action = cmd.get("action")
    payload = cmd.get("payload", "")
    payload = payload.replace("{id}", client.bee_id)
    payload = payload.replace("{codename}", client.codename)
    payload = payload.replace("{args}", args)
    if action == "broadcast":
        client.broadcast(payload)
    elif action == "send":
        to_id = cmd.get("to", "")
        if not to_id:
            warning("send command missing 'to'")
            return
        client.send(to_id, payload)
    else:
        warning(f"unsupported action: {action}")
        return
    if db:
        db.log_command(name, args)


def _queen_admin_repl(server):
    help_text = (
        "queen admin commands:\n"
        "  help\n"
        "  list\n"
        "  task <id|all> <payload>\n"
        "  repo-update <id|all>\n"
        "  spawn <n>\n"
        "  broadcast <payload>\n"
        "  quit\n"
    )
    print(help_text)
    while True:
        try:
            line = input("queen> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "help":
            print(help_text)
        elif line == "list":
            clients = server.get_clients()
            info(f"clients: {', '.join(clients) if clients else '-'}")
        elif line.startswith("task "):
            parts = line.split(" ", 2)
            if len(parts) < 3:
                warning("usage: task <id|all> <payload>")
                continue
            server.create_task(parts[1], parts[2])
        elif line.startswith("repo-update "):
            parts = line.split(" ", 1)
            target = parts[1].strip() if len(parts) > 1 else ""
            if not target:
                warning("usage: repo-update <id|all>")
                continue
            server.create_task(target, "repo_update_now")
        elif line.startswith("spawn "):
            parts = line.split(" ", 1)
            count = parts[1].strip() if len(parts) > 1 else ""
            if not count.isdigit():
                warning("usage: spawn <n>")
                continue
            try:
                spawn_bees(int(count), os.path.dirname(__file__))
            except Exception as exc:
                warning(f"spawn failed: {exc}")
        elif line.startswith("broadcast "):
            payload = line[len("broadcast ") :].strip()
            if not payload:
                warning("usage: broadcast <payload>")
                continue
            server.create_task("all", payload)
        elif line in ("quit", "exit"):
            break
        else:
            warning("unknown command, type 'help'")


if __name__ == "__main__":
    main()
