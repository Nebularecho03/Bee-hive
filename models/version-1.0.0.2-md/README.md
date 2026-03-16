# Bee Swarm Python Model (v1.0.0.2-md)

This is a Python model of the Go `bee-swarm` TCP prototype. It mirrors the
protocol and core behavior (register, send, broadcast, list) and adds
heartbeat and reconnect for local testing.

## Install
```
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Run Queen
```
python3 main.py queen --host 127.0.0.1 --port 9000
```

## Run Bee
```
python3 main.py bee --queen-host 127.0.0.1 --queen-port 9000 --commands commands.json --db bee.db
```

## Docker (10 bees)
```
docker compose up --build --scale bee=10
```

## Dashboards
Both queen and bee start a live terminal dashboard by default. Disable with:
- `queen --no-ui`
- `bee --no-ui`

## Queen Admin Console
The queen console can create tasks:
- `task <id|all> <payload>`
- `repo-update <id|all>`
- `spawn <n>` (starts Docker bees via `docker compose up --scale bee=n`)

## Bee REPL
- `help`
- `identity`
- `list`
- `send <id> <message>`
- `broadcast <message>`
- `commands`
- `run <name> [args...]`
- `chain`
- `chain-add <text>`
- `quit`

## Protocol (line-delimited JSON)
Fields: `type`, `from`, `to`, `payload`, `peers`, `ts`
Types: `register`, `registered`, `send`, `broadcast`, `list`, `peers`, `message`, `error`, `heartbeat`, `task`, `chain_add`, `repo_update`, `repo_status`

## Hash Chain (Bitcoin-style idea)
On first connect, each bee creates an OS info entry and broadcasts it as a
`chain_add` message. Every bee validates and appends to its local sqlite
chain (append-only). The queen serializes entries into a single chain by
setting `prev_hash` and broadcasting the finalized entry. No removes are
supported.

## Repo Update Task (Model Only)
One bee can run as an updater that checks a repo for changes and broadcasts
a `repo_update` message to all bees. Each bee then pulls the repo locally.

Example:
```
python3 main.py bee --updater --repo-url https://github.com/Nebularecho03/Bee-hive.git
```
