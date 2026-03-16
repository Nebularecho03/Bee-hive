# Bee-hive
Interconnected network of computers.

## Bee Swarm (TCP prototype)
Minimal 4-bee swarm simulation with a queen authority over TCP sockets. Bees
connect to the queen, register, and exchange messages routed by the queen.

## Structure
- bin: compiled binaries
- cmd/bee: bee entrypoint
- cmd/queen: queen entrypoint
- src/swarm: shared protocol utilities
- include: protocol notes
- configs: example env files
- logs: placeholder for runtime logs
- models/version-1.0.0.2-md: Python model + Docker setup

## Build
```
cd /home/John/PycharmProjects/bee-swarm

go build -o bin/queen ./cmd/queen

go build -o bin/bee ./cmd/bee
```

## Run (single machine)
```
./bin/queen -addr :9000
```

In separate terminals:
```
./bin/bee -id bee1 -queen 127.0.0.1:9000
./bin/bee -id bee2 -queen 127.0.0.1:9000
./bin/bee -id bee3 -queen 127.0.0.1:9000
./bin/bee -id bee4 -queen 127.0.0.1:9000
```

## Run (multiple VMs)
- Start the queen on one VM (note its IP, e.g., 10.0.0.5).
- Start bees on other VMs and point `-queen` to that IP.

Example:
```
./bin/queen -addr :9000
./bin/bee -id bee1 -queen 10.0.0.5:9000
```

## Bee shell
On startup the bee opens a shell but does not connect until you run `start`.
```
help
start
identity
list
send <id> <message>
broadcast <message>
ping <id>
commands
reload
whoami
quit
```

## Custom commands
You can add simple commands in `configs/bee_commands.json`. These are loaded
at startup or via `reload`.

Example file:
```
[
  {"name": "hello", "action": "broadcast", "payload": "hello from {id}"},
  {"name": "status", "action": "broadcast", "payload": "status?"},
  {"name": "pingall", "action": "broadcast", "payload": "ping"}
]
```

Template variables:
- `{id}`: bee unique id
- `{codename}`: bee codename
- `{args}`: arguments after the command name

Helper script:
```
python3 tools/bee_commands.py list
python3 tools/bee_commands.py add hello broadcast "hello from {id}"
python3 tools/bee_commands.py remove hello
```

## Notes
- The queen is the authority: all bee-to-bee messaging routes through the queen.
- Message framing is one JSON object per line. See include/protocol.md.
